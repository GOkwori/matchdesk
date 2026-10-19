/** Disposable real PostgreSQL proof for PENDING-bound, one-use step-up state.
 *
 * Restricted roles prove default denial, sealed ciphertext/tombstones and
 * serialization against parent revocation. This is NOT a live Entra/CA test.
 * No credentials, token bodies, SQL arguments or connection errors are logged.
 */
import assert from 'node:assert/strict';
import { execFileSync, spawn, spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';

const project = process.env.COMPOSE_PROJECT_NAME ?? '';
if (process.env.CI !== 'true' || !/^matchdesk-it-[0-9]+-[0-9]+$/.test(project)) {
  throw new Error('Step-up PostgreSQL proof requires isolated CI compose');
}
const migration = readFileSync(
  'backend/postgres/migrations/009_workforce_step_up_challenges.sql', 'utf8',
);
const args = [
  'compose', '--project-name', project, 'exec', '-T', 'postgres',
  'psql', '--no-psqlrc', '-X', '-q', '-A', '-t', '-v', 'ON_ERROR_STOP=1',
  '-U', 'matchdesk', '-d', 'matchdesk', '-f', '-',
];
const role = 'matchdesk_workforce_stepup_ci';
const revoker = 'matchdesk_workforce_stepup_revoker_ci';
const createSig = 'public.matchdesk_create_workforce_step_up_challenge(' +
  'text,text,uuid,uuid,uuid,text,text,bigint,bigint,bytea,bytea,bytea)';
const consumeSig = 'public.matchdesk_consume_workforce_step_up_challenge(text,text)';
const revokeSig = 'public.matchdesk_revoke_workforce_session(text)';
const tenant = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee';
const client = 'bbbbbbbb-cccc-dddd-eeee-ffffffffffff';
const actor = 'dddddddd-eeee-ffff-aaaa-bbbbbbbbbbbb';
const subject = 'ci-workforce-person';
const issuer = 'https://login.microsoftonline.com/' + tenant + '/v2.0';
const digest = (name) => createHash('sha256').update('step-up-ci-' + name).digest('hex');
const result = {
  head: execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim(),
  migration_sha256: createHash('sha256').update(migration).digest('hex'),
  scope: 'restricted offline PENDING step-up, no session or MFA authority',
  status: 'RUNNING', checks: [],
};

function sql(statement, failure = null) {
  const response = spawnSync('docker', args, {
    input: statement + '\n', encoding: 'utf8', timeout: 30_000, maxBuffer: 1048576,
  });
  if (response.error) throw new Error('SAFE_STEPUP_RUNNER_FAILURE');
  if (failure) {
    assert.notEqual(response.status, 0, 'Unexpected privileged SQL success');
    assert.match(response.stderr, failure);
  } else if (response.status !== 0) {
    throw new Error(/permission denied/i.test(response.stderr) ?
      'SAFE_STEPUP_PRIVILEGE' : /syntax error/i.test(response.stderr) ?
      'SAFE_STEPUP_SQL_SYNTAX' : 'SAFE_STEPUP_SQL_FAILURE');
  }
  return response.stdout.trim();
}
function caller(who, statement, failure = null) {
  return sql('BEGIN; SET LOCAL ROLE ' + who + ';\n' + statement + '; COMMIT;', failure);
}
const q = (v) => "'" + v + "'"; // Synthetic, allowlisted fixed CI fixtures only.
const now = () => Number(sql(
  'SELECT floor(extract(epoch FROM clock_timestamp()) * 1000)::bigint',
));
function prepare(parent, issued, duration = 600_000) {
  return 'SELECT public.matchdesk_prepare_workforce_session(' +
    q(parent) + ',' + q(tenant) + '::uuid,' + q(issuer) + ',' + q(subject) +
    ',' + q(actor) + '::uuid,' + q(client) + '::uuid,' +
    issued + '::bigint,' + (issued + duration) + '::bigint,' +
    "decode(repeat('a',24),'hex'),decode(repeat('b',120),'hex')," +
    "decode(repeat('c',32),'hex'))";
}
function create(state, parent, issued, actorId = actor) {
  return 'SELECT public.matchdesk_create_workforce_step_up_challenge(' +
    q(state) + ',' + q(parent) + ',' + q(tenant) + '::uuid,' +
    q(client) + '::uuid,' + q(actorId) + '::uuid,' + q(subject) +
    ",'c1'," + issued + '::bigint,' + (issued + 300_000) +
    "::bigint,decode(repeat('d',24),'hex')," +
    "decode(repeat('e',86),'hex'),decode(repeat('f',32),'hex'))";
}
function consume(state, parent) {
  return 'SELECT COALESCE((SELECT state_digest FROM ' +
    'public.matchdesk_consume_workforce_step_up_challenge(' +
    q(state) + ',' + q(parent) + ") LIMIT 1),'none')";
}
function revoke(parent) {
  return 'SELECT public.matchdesk_revoke_workforce_session(' + q(parent) + ')';
}
function transaction(lines) {
  const proc = spawn('docker', args, { stdio: ['pipe', 'pipe', 'pipe'] });
  let output = '';
  proc.stdout.setEncoding('utf8');
  proc.stderr.resume(); // Do not expose stderr with connection details.
  proc.stdout.on('data', (chunk) => { output += chunk; });
  const done = new Promise((resolve, reject) => {
    proc.on('error', () => reject(new Error('SAFE_STEPUP_CHILD_FAILURE')));
    proc.on('close', (exit) => exit === 0 ? resolve(output) :
      reject(new Error('SAFE_STEPUP_CHILD_SQL')));
  });
  done.catch(() => undefined);
  proc.stdin.end(lines.join(';\n') + ';\n');
  return {
    done,
    async waitFor(marker) {
      const start = Date.now();
      while (!output.includes(marker)) {
        if (proc.exitCode !== null) throw new Error('SAFE_STEPUP_EARLY_EXIT');
        if (Date.now() - start > 18_000) {
          proc.kill();
          throw new Error('SAFE_STEPUP_LOCK_TIMEOUT');
        }
        await new Promise((resolve) => setTimeout(resolve, 30));
      }
    },
  };
}
async function check(name, test) {
  const start = performance.now();
  try {
    await test();
    result.checks.push({ name, result: 'PASS', ms: Math.round(performance.now() - start) });
  } catch (error) {
    result.checks.push({ name, result: 'FAIL',
      error_type: error?.constructor?.name ?? 'Error',
      diagnostic: /^SAFE_STEPUP_[A-Z_]+$/.test(String(error?.message)) ?
        error.message : undefined,
    });
    throw error;
  }
}

try {
  await check('idempotent SQL migration and no default application EXECUTE', () => {
    sql(migration);
    sql(migration);
    sql('CREATE ROLE ' + role + ' NOLOGIN; CREATE ROLE ' + revoker + ' NOLOGIN;');
    for (const sig of [createSig, consumeSig]) {
      assert.equal(sql('SELECT has_function_privilege(' + q(role) + ',' +
        q(sig) + ",'EXECUTE')"), 'f');
    }
    sql('GRANT USAGE ON SCHEMA public TO ' + role + ',' + revoker + '; ' +
      'GRANT EXECUTE ON FUNCTION ' + createSig + ' TO ' + role + '; ' +
      'GRANT EXECUTE ON FUNCTION ' + consumeSig + ' TO ' + role + '; ' +
      'GRANT EXECUTE ON FUNCTION ' + revokeSig + ' TO ' + revoker + ';');
    for (const sig of [createSig, consumeSig]) {
      assert.equal(sql('SELECT has_function_privilege(' + q(role) + ',' +
        q(sig) + ",'EXECUTE')"), 't');
    }
    assert.equal(sql('SELECT has_function_privilege(' + q(role) + ',' +
      q(revokeSig) + ",'EXECUTE')"), 'f');
  });
  await check('restricted caller cannot read, alter or enumerate sealed state', () => {
    for (const table of [
      'public.matchdesk_workforce_pending_sessions',
      'public.matchdesk_workforce_step_up_challenges',
    ]) {
      for (const privilege of ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'TRUNCATE']) {
        assert.equal(sql('SELECT has_table_privilege(' + q(role) + ',' +
          q(table) + ',' + q(privilege) + ')'), 'f');
      }
      caller(role, 'SELECT count(*) FROM ' + table, /permission denied for table/i);
    }
  });
  const parent = digest('parent');
  const initial = now() - 1_000;
  const state = digest('state');
  await check('owner prepares parent; restricted role issues single challenge', () => {
    assert.equal(sql(prepare(parent, initial)), 't');
    assert.equal(caller(role, create(state, parent, initial + 2_000)), 't');
    assert.equal(caller(role, create(state, parent, initial + 2_000)), 'f');
  });
  await check('sealed row stores ciphertext and no session activation primitive', () => {
    assert.equal(sql('SELECT octet_length(nonce_iv)::text || \',\' || ' +
      'octet_length(nonce_ciphertext)::text || \',\' || ' +
      'octet_length(nonce_tag)::text FROM public.matchdesk_workforce_step_up_challenges ' +
      'WHERE state_digest=' + q(state)), '12,43,16');
    assert.equal(sql('SELECT count(*) FROM pg_proc WHERE ' +
      "pronamespace='public'::regnamespace AND " +
      "proname='matchdesk_activate_workforce_session'"), '0');
  });
  await check('foreign actor, absent parent and short parent TTL deny issue', () => {
    assert.equal(caller(role, create(digest('bad-actor'), parent, initial + 3_000,
      'ffffffff-ffff-ffff-ffff-ffffffffffff')), 'f');
    assert.equal(caller(role, create(digest('no-parent'), digest('missing'), initial + 3_000)), 'f');
    const short = digest('short-parent');
    assert.equal(sql(prepare(short, now() - 100, 120_000)), 't');
    assert.equal(caller(role, create(digest('short'), short, now())), 'f');
    assert.equal(caller(role, create(digest('future'), parent, now() + 200_000)), 'f');
  });
  await check('atomic consume retains replay tombstone', () => {
    assert.equal(caller(role, consume(state, parent)), state);
    assert.equal(caller(role, consume(state, parent)), 'none');
    assert.equal(sql('SELECT (consumed_at IS NOT NULL)::text FROM ' +
      'public.matchdesk_workforce_step_up_challenges WHERE state_digest=' + q(state)), 'true');
  });
  await check('revoked pending record denies challenge and future issue', () => {
    const p = digest('revoke-first-parent'), s = digest('revoke-first-state');
    const t = now() - 500;
    assert.equal(sql(prepare(p, t)), 't');
    assert.equal(caller(role, create(s, p, t)), 't');
    assert.equal(caller(revoker, revoke(p)), 't');
    assert.equal(caller(role, consume(s, p)), 'none');
    assert.equal(caller(role, create(digest('after-revoke'), p, now())), 'f');
  });
  await check('two concurrent consumes have exactly one winner', async () => {
    const p = digest('concurrent-parent'), s = digest('concurrent-state');
    const t = now() - 500;
    assert.equal(sql(prepare(p, t)), 't');
    assert.equal(caller(role, create(s, p, t)), 't');
    const first = transaction(['BEGIN', 'SET LOCAL ROLE ' + role,
      consume(s, p), "SELECT 'STEPUP_FIRST_LOCK_HELD'", 'SELECT pg_sleep(2)', 'COMMIT']);
    await first.waitFor('STEPUP_FIRST_LOCK_HELD');
    const second = transaction(['BEGIN', 'SET LOCAL ROLE ' + role, consume(s, p), 'COMMIT']);
    const [a, b] = await Promise.all([first.done, second.done]);
    assert.match(a, new RegExp(s));
    assert.equal(b.trim(), 'none');
  });
  await check('revocation winning parent lock first denies consume', async () => {
    const p = digest('revocation-winner-parent'), s = digest('revocation-winner-state');
    const t = now() - 500;
    assert.equal(sql(prepare(p, t)), 't');
    assert.equal(caller(role, create(s, p, t)), 't');
    const first = transaction(['BEGIN', 'SET LOCAL ROLE ' + revoker,
      revoke(p), "SELECT 'STEPUP_REVOCATION_LOCK_HELD'", 'SELECT pg_sleep(2)', 'COMMIT']);
    await first.waitFor('STEPUP_REVOCATION_LOCK_HELD');
    const second = transaction(['BEGIN', 'SET LOCAL ROLE ' + role, consume(s, p), 'COMMIT']);
    const [a, b] = await Promise.all([first.done, second.done]);
    assert.match(a, /(^|\n)t\n/);
    assert.equal(b.trim(), 'none');
  });
  await check('consume winning first still permits subsequent revocation', async () => {
    const p = digest('consumption-winner-parent'), s = digest('consumption-winner-state');
    const t = now() - 500;
    assert.equal(sql(prepare(p, t)), 't');
    assert.equal(caller(role, create(s, p, t)), 't');
    const first = transaction(['BEGIN', 'SET LOCAL ROLE ' + role,
      consume(s, p), "SELECT 'STEPUP_CONSUMPTION_LOCK_HELD'", 'SELECT pg_sleep(2)', 'COMMIT']);
    await first.waitFor('STEPUP_CONSUMPTION_LOCK_HELD');
    const second = transaction(['BEGIN', 'SET LOCAL ROLE ' + revoker, revoke(p), 'COMMIT']);
    const [a, b] = await Promise.all([first.done, second.done]);
    assert.match(a, new RegExp(s));
    assert.equal(b.trim(), 't');
    // Future activation must recheck this parent under lock; none exists now.
    assert.equal(caller(role, consume(s, p)), 'none');
  });
  result.status = 'PASS';
} catch (error) {
  result.status = 'FAIL';
  console.error('Step-up database qualification failed:', error?.constructor?.name);
  process.exitCode = 1;
} finally {
  mkdirSync('artifacts/integration', { recursive: true });
  writeFileSync('artifacts/integration/workforce-step-up-postgres.json',
    JSON.stringify(result, null, 2) + '\n');
  console.log(JSON.stringify(result, null, 2));
}
