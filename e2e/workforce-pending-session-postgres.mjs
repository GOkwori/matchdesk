/** Real disposable PostgreSQL checks for PENDING-only workforce vault.
 *
 * This checks owner-only rows, exact function grants, insertion bounds,
 * permanent revocation and concurrent row-lock serialization. No real
 * bearer/credential is used and no step-up or session activation exists.
 */
import assert from 'node:assert/strict';
import { execFileSync, spawn, spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';

const project = process.env.COMPOSE_PROJECT_NAME ?? '';
if (process.env.CI !== 'true' || !/^matchdesk-it-[0-9]+-[0-9]+$/.test(project)) {
  throw new Error('Pending workforce session database test requires isolated CI compose');
}
const migration = readFileSync(
  'backend/postgres/migrations/008_workforce_pending_sessions.sql', 'utf8',
);
const args = [
  'compose', '--project-name', project, 'exec', '-T', 'postgres',
  'psql', '--no-psqlrc', '-X', '-q', '-A', '-t', '-v', 'ON_ERROR_STOP=1',
  '-U', 'matchdesk', '-d', 'matchdesk', '-f', '-',
];
const role = 'matchdesk_workforce_pending_ci';
const prepareSignature = 'public.matchdesk_prepare_workforce_session(' +
  'text,uuid,text,text,uuid,uuid,bigint,bigint,bytea,bytea,bytea)';
const revokeSignature = 'public.matchdesk_revoke_workforce_session(text)';
const tenant = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee';
const client = 'bbbbbbbb-cccc-dddd-eeee-ffffffffffff';
const subject = 'ci-workforce-person';
const object = 'dddddddd-eeee-ffff-aaaa-bbbbbbbbbbbb';
const issuer = 'https://login.microsoftonline.com/' + tenant + '/v2.0';
const digest = (word) => createHash('sha256').update('pending-ci-' + word).digest('hex');

const result = {
  head: execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim(),
  migration_sha256: createHash('sha256').update(migration).digest('hex'),
  scope: 'PENDING only, restricted role, zero session activation',
  status: 'RUNNING', checks: [],
};

function sql(statement, failurePattern = null) {
  const r = spawnSync('docker', args, {
    input: statement + '\n', encoding: 'utf8', timeout: 30_000, maxBuffer: 1048576,
  });
  if (r.error) throw r.error;
  if (failurePattern !== null) {
    assert.notEqual(r.status, 0, 'Unexpected PostgreSQL authorization success');
    assert.match(r.stderr, failurePattern);
  } else {
    if (r.status !== 0) {
      // Keep runner evidence useful without exposing SQL, connection details,
      // tokens, runner paths or credential-bearing stderr from PostgreSQL.
      const category = /permission denied/i.test(r.stderr) ? 'PRIVILEGE' :
        /syntax error/i.test(r.stderr) ? 'SYNTAX' :
        /invalid input syntax|invalid byte sequence/i.test(r.stderr) ? 'INPUT' :
        /violates check constraint/i.test(r.stderr) ? 'CONSTRAINT' :
        'UNCLASSIFIED';
      throw new Error('SAFE_SQL_' + category);
    }
  }
  return r.stdout.trim();
}

function caller(statement, failurePattern = null) {
  return sql('BEGIN;\nSET LOCAL ROLE ' + role + ';\n' + statement +
    ';\nCOMMIT;', failurePattern);
}

function prepare(value, issuedAtMs) {
  const expires = issuedAtMs + 600_000;
  return 'SELECT public.matchdesk_prepare_workforce_session(' +
    "'" + value + "','" + tenant + "'::uuid,'" +
    "'" + issuer + "','" + subject + "','" + object + "'::uuid," +
    "'" + client + "'::uuid," + issuedAtMs + '::bigint,' +
    expires + '::bigint,' +
    "decode(repeat('a',24),'hex')," +
    "decode(repeat('b',120),'hex')," +
    "decode(repeat('c',32),'hex'))";
}

function revoke(value) {
  return "SELECT public.matchdesk_revoke_workforce_session('" + value + "')";
}

/** Concurrent psql transactions force the first revocation to own the lock. */
function transaction(statements) {
  const proc = spawn('docker', args, { stdio: ['pipe', 'pipe', 'pipe'] });
  let output = '', error = '';
  proc.stdout.setEncoding('utf8');
  proc.stderr.setEncoding('utf8');
  proc.stdout.on('data', (chunk) => { output += chunk; });
  proc.stderr.on('data', (chunk) => { error += chunk; });
  const done = new Promise((resolve, reject) => {
    proc.on('error', reject);
    proc.on('close', (exit) =>
      exit === 0 ? resolve(output) : reject(new Error(error.slice(0, 500))));
  });
  done.catch(() => undefined);
  proc.stdin.end(statements.join(';\n') + ';\n');
  return {
    done,
    async waitFor(marker) {
      const started = Date.now();
      while (!output.includes(marker)) {
        if (proc.exitCode !== null) throw new Error('Lock-holder exited too early');
        if (Date.now() - started > 18_000) {
          proc.kill();
          throw new Error('Timed out waiting for row lock');
        }
        await new Promise((resolve) => setTimeout(resolve, 30));
      }
    },
  };
}

async function check(name, fn) {
  const started = performance.now();
  try {
    await fn();
    result.checks.push({ name, result: 'PASS', ms: Math.round(performance.now() - started) });
  } catch (error) {
    result.checks.push({
      name, result: 'FAIL', ms: Math.round(performance.now() - started),
      // Never include SQL parameter text, tokens or connection strings.
      error_type: error?.constructor?.name ?? 'Error',
      diagnostic: /^SAFE_(SQL|PENDING)_[A-Z_]+$/.test(String(error?.message))
        ? error.message : undefined,
    });
    throw error;
  }
}

try {
  await check('idempotent migration and default PUBLIC EXECUTE denial', () => {
    sql(migration);
    sql(migration);
    sql('CREATE ROLE ' + role + ' NOLOGIN');
    for (const signature of [prepareSignature, revokeSignature]) {
      assert.equal(sql("SELECT has_function_privilege('" + role + "','" +
        signature + "','EXECUTE')"), 'f');
    }
    sql('GRANT USAGE ON SCHEMA public TO ' + role + ';\n' +
      'GRANT EXECUTE ON FUNCTION ' + prepareSignature + ' TO ' + role + ';\n' +
      'GRANT EXECUTE ON FUNCTION ' + revokeSignature + ' TO ' + role + ';');
    for (const signature of [prepareSignature, revokeSignature]) {
      assert.equal(sql("SELECT has_function_privilege('" + role + "','" +
        signature + "','EXECUTE')"), 't');
    }
  });

  await check('least-privilege role has no raw token table permissions', () => {
    for (const privilege of ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE']) {
      assert.equal(sql("SELECT has_table_privilege('" + role +
        "','public.matchdesk_workforce_pending_sessions','" + privilege + "')"), 'f');
    }
    caller('SELECT count(*) FROM public.matchdesk_workforce_pending_sessions',
      /permission denied for table/i);
    caller('DELETE FROM public.matchdesk_workforce_pending_sessions',
      /permission denied for table/i);
  });

  // Each assertion is an independent named gate. The published report records
  // only which security property failed, never SQL parameters or token bytes.
  const onceValue = digest('once');
  // Generate the positive fixture against the database's own clock so host
  // timestamp skew cannot turn this into a false policy-negative test.
  const onceNow = Number(sql(
    "SELECT floor(extract(epoch FROM clock_timestamp()) * 1000)::bigint"
  )) - 1000;
  await check('first pending insert commits successfully', () => {
    const observed = caller(prepare(onceValue, onceNow));
    if (observed === 'f') throw new Error('SAFE_PENDING_REJECTED');
    if (observed !== 't') throw new Error('SAFE_PENDING_OUTPUT_SHAPE');
  });
  await check('duplicate pending digest cannot replace or revive existing row', () => {
    assert.equal(caller(prepare(onceValue, onceNow)), 'f');
  });
  await check('sealed pending token remains protected by IV and GCM tag', () => {
    assert.equal(sql(
      "SELECT octet_length(token_iv)::text || ',' || " +
      "octet_length(token_ciphertext)::text || ',' || " +
      "octet_length(token_tag)::text FROM " +
      "public.matchdesk_workforce_pending_sessions WHERE record_digest='" + onceValue + "'"
    ), '12,60,16');
  });
  await check('there is no privileged workforce session activation function', () => {
    assert.equal(sql(
      "SELECT count(*) FROM pg_proc WHERE pronamespace='public'::regnamespace " +
      "AND proname='matchdesk_activate_workforce_session'"
    ), '0');
  });
  await check('first pending revocation commits a tombstone', () => {
    assert.equal(caller(revoke(onceValue)), 't');
  });
  await check('replayed pending revocation is rejected', () => {
    assert.equal(caller(revoke(onceValue)), 'f');
  });
  await check('revoked pending tombstone remains durable', () => {
    assert.equal(sql(
      "SELECT (revoked_at IS NOT NULL)::text FROM " +
      "public.matchdesk_workforce_pending_sessions WHERE record_digest='" + onceValue + "'"
    ), 'true');
  });

  await check('future-issued or expired records are never persisted', () => {
    const now = Date.now();
    assert.equal(caller(prepare(digest('future'), now + 300_000)), 'f');
    assert.equal(caller(prepare(digest('expired'), now - 1_800_000)), 'f');
    assert.equal(sql(
      "SELECT count(*) FROM public.matchdesk_workforce_pending_sessions " +
      "WHERE record_digest IN ('" + digest('future') + "','" + digest('expired') + "')"
    ), '0');
    assert.equal(caller(revoke(digest('absent'))), 'f');
  });

  await check('concurrent revocations have only one winner and keep a tombstone', async () => {
    const value = digest('race');
    assert.equal(caller(prepare(value, Date.now())), 't');
    const first = transaction([
      'BEGIN', 'SET LOCAL ROLE ' + role, revoke(value),
      "SELECT 'FIRST_REVOCATION_LOCK_HELD'", 'SELECT pg_sleep(2)', 'COMMIT',
    ]);
    await first.waitFor('FIRST_REVOCATION_LOCK_HELD');
    const second = transaction([
      'BEGIN', 'SET LOCAL ROLE ' + role, revoke(value), 'COMMIT',
    ]);
    const [a, b] = await Promise.all([first.done, second.done]);
    assert.match(a, /(^|\n)t\n/);
    assert.equal(b.trim(), 'f');
    assert.equal(caller(revoke(value)), 'f');
  });
  result.status = 'PASS';
} catch (error) {
  result.status = 'FAIL';
  console.error('Pending session PostgreSQL qualification failed:', error?.constructor?.name);
  process.exitCode = 1;
} finally {
  mkdirSync('artifacts/integration', { recursive: true });
  writeFileSync('artifacts/integration/workforce-pending-sessions.json',
    JSON.stringify(result, null, 2) + '\n');
  console.log(JSON.stringify(result, null, 2));
}
