/** Exercise the default-denied producer grant transaction on disposable PostgreSQL only. */
import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';

const project = process.env.COMPOSE_PROJECT_NAME ?? '';
if (process.env.CI !== 'true' || !/^matchdesk-it-[0-9]+-[0-9]+$/.test(project)) {
  throw new Error('Atomic grant qualification requires disposable CI PostgreSQL');
}
const args = ['compose', '--project-name', project, 'exec', '-T', 'postgres',
  'psql', '--no-psqlrc', '-X', '-v', 'ON_ERROR_STOP=1', '-U', 'matchdesk', '-d', 'matchdesk', '-q', '-A', '-t'];
const report = { source_commit: execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim(),
  status: 'RUNNING', scope: 'Disposable SQL only; no live issuer, MFA, or HTTP host', checks: [] };
function sql(query, expectedError = null) {
  const res = spawnSync('docker', [...args, '-f', '-'], { input: query, encoding: 'utf8',
    timeout: 30000, maxBuffer: 1048576 });
  if (res.error) throw res.error;
  if (expectedError) {
    assert.notEqual(res.status, 0);
    assert.match(res.stderr, expectedError);
  } else assert.equal(res.status, 0, res.stderr);
  return res.stdout.trim();
}
function check(name, fn) {
  try { fn(); report.checks.push({ name, status: 'PASS' }); }
  catch (error) { report.checks.push({ name, status: 'FAIL', detail: String(error).slice(0, 450) }); throw error; }
}
const digest1 = 'a'.repeat(64);
const digest2 = 'b'.repeat(64);
const binding = { item_id: 'ci-item', item_version: 1, replay_id: 'ci-replay',
  content_digest: digest1, evidence_digest: digest2, language: 'en', persona: 'analyst' };
const actor = 'ci-actor', tenant = 'ci-tenant', session = 'ci-session', output = 'ci-output';
const grantId = 'ci-create-grant-00001';
const entry = { action: 'review_started', actor_id: actor, binding, reason: 'ci initial review' };
const caseDoc = { tenant_id: tenant, generation: 1,
  output: { session_id: session, output_id: output, binding },
  review: { binding, status: 'pending_verification', audit: [entry] } };
const q = (v) => "'" + JSON.stringify(v).replaceAll("'", "''") + "'::jsonb";
const grantSql = (id, action = 'create', seconds = 600) =>
  'INSERT INTO public.matchdesk_producer_action_grants ' +
  '(grant_id,tenant_id,session_id,output_id,actor_id,issuer,action,binding,expected_generation,expires_at) VALUES (' +
  [id,tenant,session,output,actor,'ci-issuer',action].map(x => "'" + x + "'").join(',') +
  ',' + q(binding) + ",0,clock_timestamp() + interval '" + seconds + " seconds');";
const invoke = (id, identity = actor, command = 'ci-command-000001') =>
  'SELECT public.matchdesk_commit_producer_grant(' +
  [id,identity,tenant,session,output,'create',command].map(x => "'" + x + "'").join(',') +
  ',0,NULL,' + "'" + digest1 + "'," + q(caseDoc) + ',' + q(entry) + ');';
try {
  check('migration is repeatable and callable only when role is granted', () => {
    const migration = readFileSync('backend/postgres/migrations/006_producer_atomic_grants.sql','utf8');
    sql(migration); sql(migration);
    assert.equal(sql("SELECT has_function_privilege('public','public.matchdesk_commit_producer_grant(text,text,text,text,text,text,text,bigint,text,text,jsonb,jsonb)','EXECUTE');"), 'f');
    sql("CREATE ROLE matchdesk_grant_ci LOGIN;");
    sql("GRANT CONNECT ON DATABASE matchdesk TO matchdesk_grant_ci;");
    sql("GRANT USAGE ON SCHEMA public TO matchdesk_grant_ci;");
    sql("GRANT EXECUTE ON FUNCTION public.matchdesk_commit_producer_grant(text,text,text,text,text,text,text,bigint,text,text,jsonb,jsonb) TO matchdesk_grant_ci;");
    assert.equal(sql("SELECT has_function_privilege('matchdesk_grant_ci','public.matchdesk_commit_producer_grant(text,text,text,text,text,text,text,bigint,text,text,jsonb,jsonb)','EXECUTE');"), 't');
    assert.equal(sql("SELECT has_table_privilege('matchdesk_grant_ci','public.matchdesk_producer_action_grants','UPDATE');"), 'f');
    assert.equal(sql("SELECT has_table_privilege('matchdesk_grant_ci','public.matchdesk_producer_cases','UPDATE');"), 'f');
  });
  check('revocation and invalid actor fail before any case write', () => {
    sql(grantSql('ci-revoked-grant-01'));
    sql("UPDATE public.matchdesk_producer_action_grants SET revoked_at=clock_timestamp() WHERE grant_id='ci-revoked-grant-01';");
    assert.equal(sql(invoke('ci-revoked-grant-01')), 'f');
    sql(grantSql('ci-wrong-actor-01'));
    assert.equal(sql(invoke('ci-wrong-actor-01','forged-actor')), 'f');
    assert.equal(sql("SELECT count(*) FROM matchdesk_producer_cases WHERE tenant_id='ci-tenant';"), '0');
  });
  check('valid grant commits case and audit and cannot replay', () => {
    sql(grantSql(grantId));
    assert.equal(sql(invoke(grantId)), 't');
    assert.equal(sql(invoke(grantId)), 'f');
    assert.equal(sql("SELECT generation FROM matchdesk_producer_cases WHERE tenant_id='ci-tenant';"), '1');
    assert.equal(sql("SELECT count(*) FROM matchdesk_producer_audit WHERE tenant_id='ci-tenant';"), '1');
    assert.equal(sql("SELECT count(*) FROM matchdesk_producer_action_grants WHERE grant_id='" + grantId + "' AND consumed_at IS NOT NULL;"), '1');
  });
  check('conflicting case insert leaves grant unconsumed', () => {
    sql(grantSql('ci-conflict-grant-01'));
    assert.equal(sql(invoke('ci-conflict-grant-01')), 'f');
    assert.equal(sql("SELECT count(*) FROM matchdesk_producer_action_grants WHERE grant_id='ci-conflict-grant-01' AND consumed_at IS NULL;"), '1');
  });
  report.status = 'PASS';
} catch (error) { report.status = 'FAIL'; console.error(String(error)); process.exitCode = 1; }
finally {
  mkdirSync('artifacts/integration', { recursive: true });
  writeFileSync('artifacts/integration/producer-grant-atomic.json', JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify(report, null, 2));
}
