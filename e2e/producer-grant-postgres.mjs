/**
 * DEV/CI-only real PostgreSQL qualification of issuer-owned execution grants.
 *
 * Uses a disposable Docker Compose database, an owner for synthetic issuance,
 * and a NOLOGIN restricted test role for grant consumption. This is not
 * Entra/MFA, a production migration, or an HTTP operator authorization test.
 */
import assert from 'node:assert/strict';
import { execFileSync, spawn, spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';

const project = process.env.COMPOSE_PROJECT_NAME ?? '';
if (process.env.CI !== 'true' || !/^matchdesk-it-[0-9]+-[0-9]+$/.test(project)) {
  throw new Error('Grant qualification requires the disposable CI Compose project');
}
const migration = readFileSync('backend/postgres/migrations/006_producer_execution_grants.sql', 'utf8');
const args = [
  'compose', '--project-name', project, 'exec', '-T', 'postgres', 'psql',
  '--no-psqlrc', '-X', '-q', '-A', '-t', '-v', 'ON_ERROR_STOP=1',
  '-U', 'matchdesk', '-d', 'matchdesk', '-f', '-',
];
const report = {
  source_commit: execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim(),
  migration_sha256: createHash('sha256').update(migration).digest('hex'),
  scope: 'disposable PostgreSQL grants, restricted definer EXECUTE, locking and rollback; no identity provider',
  status: 'RUNNING',
  checks: [],
};

/** Execute only fixed, synthetic SQL through the disposable local owner socket. */
function sql(statement, expectedFailure = null) {
  const result = spawnSync('docker', args, {
    input: statement + '\n', encoding: 'utf8', timeout: 30000, maxBuffer: 1048576,
  });
  if (result.error) throw result.error;
  if (expectedFailure) {
    assert.notEqual(result.status, 0, 'Expected PostgreSQL authorization or constraint failure');
    assert.match(result.stderr, expectedFailure);
  } else {
    assert.equal(result.status, 0, 'PostgreSQL: ' + result.stderr);
  }
  return result.stdout.trim();
}

/** A separate process holds a real database transaction until COMMIT. */
function session(statements) {
  const child = spawn('docker', args, { stdio: ['pipe', 'pipe', 'pipe'] });
  let out = '';
  let err = '';
  child.stdout.setEncoding('utf8');
  child.stderr.setEncoding('utf8');
  child.stdout.on('data', (chunk) => { out += chunk; });
  child.stderr.on('data', (chunk) => { err += chunk; });
  const done = new Promise((resolve, reject) => {
    child.on('error', reject);
    child.on('close', (code) => code === 0 ? resolve(out) : reject(new Error(err.slice(0, 800))));
  });
  // Own the rejection even before the caller starts waiting for the marker.
  done.catch(() => undefined);
  child.stdin.end(statements.join('\n') + '\n');
  return {
    done,
    async waitFor(marker) {
      const started = Date.now();
      while (!out.includes(marker)) {
        if (child.exitCode !== null) throw new Error('Transaction exited before ' + marker + ': ' + err);
        if (Date.now() - started > 20000) {
          child.kill();
          throw new Error('PostgreSQL transaction marker timed out: ' + marker);
        }
        await new Promise((resolve) => setTimeout(resolve, 30));
      }
    },
  };
}

async function check(name, run) {
  const started = performance.now();
  try {
    await run();
    report.checks.push({ name, status: 'PASS', duration_ms: Math.round(performance.now() - started) });
  } catch (error) {
    report.checks.push({
      name, status: 'FAIL', duration_ms: Math.round(performance.now() - started),
      detail: String(error).slice(0, 500),
    });
    throw error;
  }
}

// All literals in this script are disposable fixture values, not credentials.
const tenant = 'ci-grant-tenant';
const actor = 'ci-grant-producer';
const issuer = 'https://ci.example.invalid/v2.0';
const sessionId = 'ci-grant-session';
const digest = 'f'.repeat(64);
const uuid = {
  revoked: '11111111-1111-4111-8111-111111111101',
  expired: '11111111-1111-4111-8111-111111111102',
  single: '11111111-1111-4111-8111-111111111103',
  mismatch: '11111111-1111-4111-8111-111111111104',
  rollback: '11111111-1111-4111-8111-111111111105',
  claimFirst: '11111111-1111-4111-8111-111111111106',
  revokeFirst: '11111111-1111-4111-8111-111111111107',
};
const role = 'matchdesk_legacy_grant_ci';
const signature = 'public.matchdesk_consume_producer_execution_grant(uuid,text,text,text,text,text,text,bigint,text)';

/** Only the trusted fixture issuer owns grant-row insertion and revocation. */
function issue(id, output, flags = {}) {
  const issued = flags.expired
    ? "clock_timestamp() - interval '3 minutes'" : 'clock_timestamp()';
  const expiry = flags.expired
    ? "clock_timestamp() - interval '2 minutes'" : "clock_timestamp() + interval '3 minutes'";
  const revoked = flags.revoked ? 'clock_timestamp()' : 'NULL';
  sql(
    'INSERT INTO public.matchdesk_producer_execution_grants ' +
    '(grant_id,tenant_id,actor_subject,actor_issuer,action,session_id,output_id,' +
    'expected_generation,binding_digest,issued_at,expires_at,revoked_at) VALUES (' +
    "'" + id + "','" + tenant + "','" + actor + "','" + issuer + "'," +
    "'create','" + sessionId + "','" + output + "',0,'" + digest + "'," +
    issued + ',' + expiry + ',' + revoked + ');'
  );
}

/** Use the exact fixed-function contract the Python store invokes. */
function grantCall(id, output, actorOverride = actor, digestOverride = digest) {
  return 'public.matchdesk_consume_producer_execution_grant(' +
    "'" + id + "'::uuid,'" + tenant + "','" + actorOverride + "','" + issuer + "'," +
    "'create','" + sessionId + "','" + output + "',0,'" + digestOverride + "')";
}

/** Use only a restricted role for the caller side, never a test issuer role. */
function writer(statement, expectedFailure = null) {
  return sql('BEGIN;\nSET LOCAL ROLE ' + role + ';\n' + statement + '\nCOMMIT;', expectedFailure);
}

function caseInsert(output) {
  return 'INSERT INTO public.matchdesk_producer_cases ' +
    '(tenant_id,session_id,output_id,generation,case_json,audit_digest) VALUES ' +
    "('" + tenant + "','" + sessionId + "','" + output + "',1," +
    "'{\"fixture\":\"grant-execution\"}'::jsonb,'" + digest + "');";
}

function auditInsert(output, good = true) {
  return 'INSERT INTO public.matchdesk_producer_audit ' +
    '(tenant_id,session_id,output_id,generation,entry_json,audit_digest) VALUES ' +
    "('" + tenant + "','" + sessionId + "','" + output + "',1," +
    "'{\"action\":\"review_started\"}'::jsonb,'" + (good ? digest : 'invalid') + "');";
}

function grantState(id) {
  return sql(
    'SELECT (consumed_at IS NOT NULL)::text || \',\' || ' +
    '(revoked_at IS NOT NULL)::text || \',\' || ' +
    '(consumed_at IS NULL OR revoked_at IS NULL OR consumed_at <= revoked_at)::text ' +
    "FROM public.matchdesk_producer_execution_grants WHERE grant_id='" + id + "';"
  );
}

try {
  await check('reapply grant migration without inheriting stale function EXECUTE rights', () => {
    sql(migration);
    sql(migration);
    // Simulate a stale role-specific grant left by a previous DEV build.
    // CREATE OR REPLACE FUNCTION would preserve it even after PUBLIC revoke.
    const staleRole = 'matchdesk_grant_stale_ci';
    sql('CREATE ROLE ' + staleRole + ' NOLOGIN;\n' +
      'GRANT EXECUTE ON FUNCTION ' + signature + ' TO ' + staleRole + ';');
    assert.equal(sql(
      "SELECT has_function_privilege('" + staleRole + "','" + signature + "','EXECUTE');"
    ), 't');
    sql(migration);
    assert.equal(sql(
      "SELECT has_function_privilege('" + staleRole + "','" + signature + "','EXECUTE');"
    ), 'f', 'A reinstalled SECURITY DEFINER must not keep old invokers');
    sql([
      'CREATE ROLE matchdesk_legacy_grant_ci NOLOGIN;',
      'GRANT USAGE ON SCHEMA public TO matchdesk_legacy_grant_ci;',
      'GRANT SELECT, INSERT, UPDATE ON public.matchdesk_producer_cases TO matchdesk_legacy_grant_ci;',
      'GRANT SELECT, INSERT ON public.matchdesk_producer_audit TO matchdesk_legacy_grant_ci;',
      'GRANT EXECUTE ON FUNCTION ' + signature + ' TO matchdesk_legacy_grant_ci;',
    ].join('\n'));
    assert.equal(sql(
      "SELECT has_function_privilege('" + role + "','" + signature + "','EXECUTE');"
    ), 't');
    assert.equal(sql(
      "SELECT has_table_privilege('" + role +
      "','public.matchdesk_producer_execution_grants','SELECT');"
    ), 'f');
    assert.equal(sql(
      "SELECT has_table_privilege('" + role +
      "','public.matchdesk_producer_execution_grants','INSERT');"
    ), 'f');
    assert.equal(sql(
      "SELECT has_column_privilege('" + role +
      "','public.matchdesk_producer_execution_grants','revoked_at','UPDATE');"
    ), 'f');
  });
  await check('grant SECURITY DEFINER runs as column-restricted non-login owner', () => {
    // Reassign the function ONLY inside the disposable CI database. A real
    // environment requires separately approved and reviewed role provisioning.
    const definer = 'matchdesk_legacy_grant_definer_ci';
    const bystander = 'matchdesk_legacy_grant_bystander_ci';
    sql([
      'BEGIN',
      'REVOKE CREATE ON SCHEMA public FROM PUBLIC',
      'CREATE ROLE ' + definer +
        ' NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS',
      'CREATE ROLE ' + bystander +
        ' NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS',
      'GRANT USAGE ON SCHEMA public TO ' + definer,
      'GRANT USAGE ON SCHEMA public TO ' + bystander,
      // Only the referenced equality/expiry predicates and consumed_at
      // are available. Issuance and revocation remain owner-only.
      'GRANT SELECT (grant_id, tenant_id, actor_subject, actor_issuer, ' +
        'action, session_id, output_id, expected_generation, binding_digest, ' +
        'revoked_at, consumed_at, expires_at) ' +
        'ON public.matchdesk_producer_execution_grants TO ' + definer,
      'GRANT UPDATE (consumed_at) ' +
        'ON public.matchdesk_producer_execution_grants TO ' + definer,
      // PostgreSQL requires temporary CREATE for function ownership transfer.
      // The privilege is revoked within this same transaction, before commit.
      'GRANT CREATE ON SCHEMA public TO ' + definer,
      'ALTER FUNCTION ' + signature + ' OWNER TO ' + definer,
      'REVOKE CREATE ON SCHEMA public FROM ' + definer,
      'COMMIT',
    ].join(';\n') + ';');
    assert.equal(sql(
      'SELECT count(*) FROM pg_catalog.pg_proc AS p ' +
      'JOIN pg_catalog.pg_roles AS r ON r.oid=p.proowner ' +
      "WHERE p.oid='" + signature + "'::regprocedure AND p.prosecdef " +
      "AND p.provolatile='v' " +
      "AND p.proconfig @> ARRAY['search_path=pg_catalog']::text[] " +
      "AND r.rolname='" + definer + "' " +
      'AND NOT r.rolcanlogin AND NOT r.rolsuper AND NOT r.rolcreatedb ' +
      'AND NOT r.rolcreaterole AND NOT r.rolinherit ' +
      'AND NOT r.rolreplication AND NOT r.rolbypassrls'
    ), '1');
    assert.equal(sql(
      'SELECT count(*) FROM pg_catalog.pg_auth_members WHERE ' +
      "member='" + definer + "'::regrole OR roleid='" + definer + "'::regrole"
    ), '0');
    assert.equal(sql(
      "SELECT has_schema_privilege('" + definer + "','public','CREATE')"
    ), 'f');
    assert.equal(sql(
      "SELECT has_function_privilege('" + role + "','" + signature + "','EXECUTE')"
    ), 't');
    assert.equal(sql(
      "SELECT has_function_privilege('" + bystander + "','" + signature + "','EXECUTE')"
    ), 'f');
    for (const [column, privilege, expected] of [
      ['grant_id', 'SELECT', 't'],
      ['actor_subject', 'SELECT', 't'],
      ['binding_digest', 'SELECT', 't'],
      ['expires_at', 'SELECT', 't'],
      ['issued_at', 'SELECT', 'f'],
      ['consumed_at', 'UPDATE', 't'],
      ['revoked_at', 'UPDATE', 'f'],
      ['expires_at', 'UPDATE', 'f'],
      ['binding_digest', 'UPDATE', 'f'],
    ]) {
      assert.equal(sql(
        "SELECT has_column_privilege('" + definer +
        "','public.matchdesk_producer_execution_grants','" +
        column + "','" + privilege + "')"
      ), expected, column + ' ' + privilege);
    }
    for (const table of ['matchdesk_producer_cases', 'matchdesk_producer_audit']) {
      for (const privilege of ['SELECT', 'INSERT', 'UPDATE', 'DELETE']) {
        assert.equal(sql(
          "SELECT has_table_privilege('" + definer +
          "','public." + table + "','" + privilege + "')"
        ), 'f', table + ' ' + privilege);
      }
    }
    for (const privilege of ['INSERT', 'DELETE', 'TRUNCATE', 'TRIGGER']) {
      assert.equal(sql(
        "SELECT has_table_privilege('" + definer +
        "','public.matchdesk_producer_execution_grants','" + privilege + "')"
      ), 'f', privilege);
    }
    // Explicit negative execution checks protect against privilege drift.
    sql('BEGIN; SET LOCAL ROLE ' + definer +
      '; UPDATE public.matchdesk_producer_execution_grants ' +
      'SET revoked_at=clock_timestamp(); COMMIT;',
      /permission denied for table/i);
    sql('BEGIN; SET LOCAL ROLE ' + definer +
      '; SELECT count(*) FROM public.matchdesk_producer_cases; COMMIT;',
      /permission denied for table/i);
  });
  await check('writer cannot list, issue or revoke grants directly', () => {
    writer('SELECT count(*) FROM public.matchdesk_producer_execution_grants;',
      /permission denied for table/i);
    writer(
      "UPDATE public.matchdesk_producer_execution_grants SET revoked_at=clock_timestamp();",
      /permission denied for table/i
    );
    writer(
      'INSERT INTO public.matchdesk_producer_execution_grants (grant_id) ' +
      "VALUES ('11111111-1111-4111-8111-111111111199'::uuid);",
      /permission denied for table/i
    );
  });
  await check('revoked and expired grants cannot be consumed', () => {
    issue(uuid.revoked, 'already-revoked', { revoked: true });
    issue(uuid.expired, 'already-expired', { expired: true });
    assert.equal(writer('SELECT ' + grantCall(uuid.revoked, 'already-revoked') + ';'), 'f');
    assert.equal(writer('SELECT ' + grantCall(uuid.expired, 'already-expired') + ';'), 'f');
    assert.equal(grantState(uuid.revoked), 'false,true,true');
    assert.equal(grantState(uuid.expired), 'false,false,true');
  });
  await check('single-use and exact actor/content binding reject replay and retarget', () => {
    issue(uuid.single, 'single-use');
    assert.equal(writer('SELECT ' + grantCall(uuid.single, 'single-use') + ';'), 't');
    assert.equal(writer('SELECT ' + grantCall(uuid.single, 'single-use') + ';'), 'f');
    issue(uuid.mismatch, 'exact-match');
    assert.equal(writer('SELECT ' + grantCall(uuid.mismatch, 'exact-match', 'wrong-actor') + ';'), 'f');
    assert.equal(writer('SELECT ' + grantCall(uuid.mismatch, 'exact-match', actor, 'e'.repeat(64)) + ';'), 'f');
    assert.equal(grantState(uuid.mismatch), 'false,false,true');
  });
  await check('audit insertion error rolls back claimed grant and case', () => {
    issue(uuid.rollback, 'rollback-output');
    writer(
      'SELECT ' + grantCall(uuid.rollback, 'rollback-output') + ';\n' +
      caseInsert('rollback-output') + '\n' + auditInsert('rollback-output', false),
      /violates check constraint/i
    );
    assert.equal(grantState(uuid.rollback), 'false,false,true');
    assert.equal(sql(
      "SELECT count(*) FROM public.matchdesk_producer_cases WHERE tenant_id='" + tenant +
      "' AND output_id='rollback-output';"
    ), '0');
  });
  await check('consume-first race serializes revocation after complete case/audit commit', async () => {
    issue(uuid.claimFirst, 'claim-first');
    const claimant = session([
      'BEGIN;',
      'SET LOCAL ROLE ' + role + ';',
      'SELECT ' + grantCall(uuid.claimFirst, 'claim-first') + ';',
      "SELECT 'CLAIM_LOCK_HELD';",
      'SELECT pg_sleep(2);',
      caseInsert('claim-first'),
      auditInsert('claim-first'),
      'COMMIT;',
    ]);
    await claimant.waitFor('CLAIM_LOCK_HELD');
    const revoker = session([
      'BEGIN;',
      "SELECT 'REVOCATION_ATTEMPT';",
      "UPDATE public.matchdesk_producer_execution_grants SET revoked_at=clock_timestamp() " +
        "WHERE grant_id='" + uuid.claimFirst + "';",
      'COMMIT;',
    ]);
    await revoker.waitFor('REVOCATION_ATTEMPT');
    const results = await Promise.all([claimant.done, revoker.done]);
    assert.match(results[0], /CLAIM_LOCK_HELD/);
    assert.equal(grantState(uuid.claimFirst), 'true,true,true');
    assert.equal(sql(
      "SELECT count(*) FROM public.matchdesk_producer_audit WHERE tenant_id='" + tenant +
      "' AND output_id='claim-first';"
    ), '1');
  });
  await check('revoke-first race blocks later consumer and all case writes', async () => {
    issue(uuid.revokeFirst, 'revoke-first');
    const revoker = session([
      'BEGIN;',
      "UPDATE public.matchdesk_producer_execution_grants SET revoked_at=clock_timestamp() " +
        "WHERE grant_id='" + uuid.revokeFirst + "';",
      "SELECT 'REVOKE_LOCK_HELD';",
      'SELECT pg_sleep(2);',
      'COMMIT;',
    ]);
    await revoker.waitFor('REVOKE_LOCK_HELD');
    const claimant = session([
      'BEGIN;',
      'SET LOCAL ROLE ' + role + ';',
      'SELECT ' + grantCall(uuid.revokeFirst, 'revoke-first') + ';',
      'COMMIT;',
    ]);
    const results = await Promise.all([revoker.done, claimant.done]);
    assert.match(results[1].trim(), /^f$/);
    assert.equal(grantState(uuid.revokeFirst), 'false,true,true');
    assert.equal(sql(
      "SELECT count(*) FROM public.matchdesk_producer_cases WHERE tenant_id='" + tenant +
      "' AND output_id='revoke-first';"
    ), '0');
  });
  report.status = 'PASS';
} catch (error) {
  report.status = 'FAIL';
  console.error('Producer execution grant qualification failed:', String(error));
  process.exitCode = 1;
} finally {
  mkdirSync('artifacts/integration', { recursive: true });
  writeFileSync('artifacts/integration/producer-grant-postgres.json',
    JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify(report, null, 2));
}
