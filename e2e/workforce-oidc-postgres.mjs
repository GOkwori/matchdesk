/** Disposable real PostgreSQL qualification for workforce OIDC state functions.
 *
 * This proves the isolated schema, strict role permissions, one-time claims,
 * expiry decisions and a concurrent replay race. The Node store crypto path
 * has separate unit coverage; no real Entra session/token or live route exists.
 */
import assert from 'node:assert/strict';
import { execFileSync, spawn, spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';

const project = process.env.COMPOSE_PROJECT_NAME ?? '';
if (process.env.CI !== 'true' || !/^matchdesk-it-[0-9]+-[0-9]+$/.test(project)) {
  throw new Error('Workforce OIDC PostgreSQL qualification requires the disposable CI project');
}
const migration = readFileSync('backend/postgres/migrations/007_workforce_oidc_attempts.sql', 'utf8');
const args = [
  'compose', '--project-name', project, 'exec', '-T', 'postgres', 'psql',
  '--no-psqlrc', '-X', '-q', '-A', '-t', '-v', 'ON_ERROR_STOP=1',
  '-U', 'matchdesk', '-d', 'matchdesk', '-f', '-',
];
const report = {
  source_commit: execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim(),
  migration_sha256: createHash('sha256').update(migration).digest('hex'),
  scope: 'disposable single-use workforce state, grants, replay and concurrency; no live Entra',
  status: 'RUNNING', checks: [],
};

function sql(statement, expectedFailure = null) {
  const result = spawnSync('docker', args, {
    input: statement + '\n', encoding: 'utf8', timeout: 30000, maxBuffer: 1048576,
  });
  if (result.error) throw result.error;
  if (expectedFailure) {
    assert.notEqual(result.status, 0, 'Expected PostgreSQL failure did not occur');
    assert.match(result.stderr, expectedFailure);
  } else {
    assert.equal(result.status, 0, 'PostgreSQL: ' + result.stderr);
  }
  return result.stdout.trim();
}

/** A restricted role has no direct access to the workforce state table. */
const role = 'matchdesk_workforce_oidc_ci';
function caller(statement, expectedFailure = null) {
  return sql('BEGIN;\nSET LOCAL ROLE ' + role + ';\n' + statement + '\nCOMMIT;', expectedFailure);
}

function session(statements) {
  const child = spawn('docker', args, { stdio: ['pipe', 'pipe', 'pipe'] });
  let output = '';
  let error = '';
  child.stdout.setEncoding('utf8');
  child.stderr.setEncoding('utf8');
  child.stdout.on('data', (chunk) => { output += chunk; });
  child.stderr.on('data', (chunk) => { error += chunk; });
  const done = new Promise((resolve, reject) => {
    child.on('error', reject);
    child.on('close', (status) =>
      status === 0 ? resolve(output) : reject(new Error(error.slice(0, 700))));
  });
  done.catch(() => undefined);
  child.stdin.end(statements.join('\n') + '\n');
  return {
    done,
    async waitFor(marker) {
      const started = Date.now();
      while (!output.includes(marker)) {
        if (child.exitCode !== null) throw new Error('Transaction exited before lock marker');
        if (Date.now() - started > 18000) {
          child.kill();
          throw new Error('Timed out waiting for transaction lock marker');
        }
        await new Promise((resolve) => setTimeout(resolve, 30));
      }
    },
  };
}

async function check(name, fn) {
  const start = performance.now();
  try {
    await fn();
    report.checks.push({ name, status: 'PASS', ms: Math.round(performance.now() - start) });
  } catch (e) {
    report.checks.push({
      name, status: 'FAIL', ms: Math.round(performance.now() - start),
      detail: String(e).slice(0, 300),
    });
    throw e;
  }
}

// Only fixture strings, never credentials or dynamic SQL from a browser.
const issuer = 'https://login.microsoftonline.com/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/v2.0';
const client = 'bbbbbbbb-cccc-dddd-eeee-ffffffffffff';
const redirect = 'https://operator.example.test/api/workforce/oidc/callback';
const binding = createHash('sha256').update('ci-workforce-browser-binding').digest('hex');
const state = Object.fromEntries(
  ['once', 'race', 'expired', 'future'].map((v) =>
    [v, createHash('sha256').update('ci-workforce-' + v).digest('hex')])
);
const signatureIssue = 'public.matchdesk_create_workforce_oidc_attempt(' +
  'text,text,text,text,text,bigint,bigint,bytea,bytea,bytea)';
const signatureConsume = 'public.matchdesk_consume_workforce_oidc_attempt(text)';

function issue(digest, issuedAtMs) {
  return 'SELECT public.matchdesk_create_workforce_oidc_attempt(' +
    "'" + digest + "','" + binding + "','" + issuer + "','" + client + "','" +
    redirect + "'," + issuedAtMs + '::bigint,' + (issuedAtMs + 300000) + '::bigint,' +
    "decode(repeat('a',24),'hex'),decode(repeat('b',174),'hex')," +
    "decode(repeat('c',32),'hex'));";
}

function consume(digest) {
  return "SELECT count(*) FROM public.matchdesk_consume_workforce_oidc_attempt('" +
    digest + "');";
}

try {
  await check('migration is repeatable and functions are default-deny', () => {
    sql(migration);
    sql(migration);
    sql('CREATE ROLE ' + role + ' NOLOGIN;');
    assert.equal(sql(
      "SELECT has_table_privilege('" + role +
      "','public.matchdesk_workforce_oidc_attempts','SELECT');"
    ), 'f');
    assert.equal(sql(
      "SELECT has_function_privilege('" + role + "','" + signatureIssue + "','EXECUTE');"
    ), 'f');
    sql(
      'GRANT USAGE ON SCHEMA public TO ' + role + ';\n' +
      'GRANT EXECUTE ON FUNCTION ' + signatureIssue + ' TO ' + role + ';\n' +
      'GRANT EXECUTE ON FUNCTION ' + signatureConsume + ' TO ' + role + ';'
    );
    assert.equal(sql(
      "SELECT has_function_privilege('" + role + "','" + signatureIssue + "','EXECUTE');"
    ), 't');
    assert.equal(sql(
      "SELECT has_function_privilege('" + role + "','" + signatureConsume + "','EXECUTE');"
    ), 't');
    for (const privilege of ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE']) {
      assert.equal(sql(
        "SELECT has_table_privilege('" + role +
        "','public.matchdesk_workforce_oidc_attempts','" + privilege + "');"
      ), 'f');
    }
  });
  await check('restricted role cannot inspect, mutate or erase any grant tombstone', () => {
    caller('SELECT count(*) FROM public.matchdesk_workforce_oidc_attempts;',
      /permission denied for table/i);
    caller('UPDATE public.matchdesk_workforce_oidc_attempts ' +
      'SET consumed_at = clock_timestamp();', /permission denied for table/i);
    caller('DELETE FROM public.matchdesk_workforce_oidc_attempts;',
      /permission denied for table/i);
  });
  await check('opaque encrypted state is issued once and replay cannot consume twice', () => {
    const now = Date.now();
    assert.equal(caller(issue(state.once, now)), 't');
    assert.equal(caller(issue(state.once, now)), 'f');
    const lengths = sql(
      'SELECT octet_length(secret_iv)::text || \',\' || ' +
      'octet_length(secret_ciphertext)::text || \',\' || ' +
      'octet_length(secret_tag)::text FROM public.matchdesk_workforce_oidc_attempts ' +
      "WHERE state_digest='" + state.once + "';"
    );
    assert.equal(lengths, '12,87,16');
    assert.equal(caller(consume(state.once)), '1');
    assert.equal(caller(consume(state.once)), '0');
    assert.equal(sql(
      "SELECT (consumed_at IS NOT NULL)::text FROM public.matchdesk_workforce_oidc_attempts " +
      "WHERE state_digest='" + state.once + "';"
    ), 'true');
  });
  await check('expired and future-issued rows never return a one-use exchange', () => {
    const now = Date.now();
    assert.equal(caller(issue(state.expired, now - 900000)), 't');
    assert.equal(caller(issue(state.future, now + 100000)), 't');
    assert.equal(caller(consume(state.expired)), '0');
    assert.equal(caller(consume(state.future)), '0');
    assert.equal(sql(
      'SELECT count(*) FROM public.matchdesk_workforce_oidc_attempts ' +
      'WHERE consumed_at IS NOT NULL AND state_digest IN (' +
      "'" + state.expired + "','" + state.future + "');"
    ), '0');
  });
  await check('concurrent consumers serialize behind one PostgreSQL row lock', async () => {
    assert.equal(caller(issue(state.race, Date.now())), 't');
    const first = session([
      'BEGIN;',
      'SET LOCAL ROLE ' + role + ';',
      consume(state.race),
      "SELECT 'FIRST_CLAIM_LOCK_HELD';",
      'SELECT pg_sleep(2);',
      'COMMIT;',
    ]);
    await first.waitFor('FIRST_CLAIM_LOCK_HELD');
    const second = session([
      'BEGIN;',
      'SET LOCAL ROLE ' + role + ';',
      consume(state.race),
      'COMMIT;',
    ]);
    const [a, b] = await Promise.all([first.done, second.done]);
    assert.match(a, /(^|\n)1\n/);
    assert.equal(b.trim(), '0');
    assert.equal(caller(consume(state.race)), '0');
  });
  report.status = 'PASS';
} catch (e) {
  report.status = 'FAIL';
  console.error('Workforce OIDC PostgreSQL qualification failed:', String(e).slice(0, 700));
  process.exitCode = 1;
} finally {
  mkdirSync('artifacts/integration', { recursive: true });
  writeFileSync('artifacts/integration/workforce-oidc-postgres.json',
    JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify(report, null, 2));
}
