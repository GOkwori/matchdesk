/** Exercise the default-denied producer grant transaction on disposable PostgreSQL only. */
import assert from 'node:assert/strict';
import { execFile, execFileSync, spawnSync } from 'node:child_process';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { promisify } from 'node:util';

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
async function check(name, fn) {
  try { await fn(); report.checks.push({ name, status: 'PASS' }); }
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
// Use an unprivileged SQL execution role for every positive decision. The
// database owner only creates test grants and performs fixture setup/revocation.
const executeAsRestricted = (statement) => 'SET ROLE matchdesk_grant_ci; ' + statement;
const execAsync = promisify(execFile);
async function concurrentSql(statement) {
  const result = await execAsync('docker', [...args, '-c', statement],
    { encoding: 'utf8', timeout: 30000, maxBuffer: 1048576 });
  return result.stdout.trim();
}
async function waitForHeldTransaction(marker) {
  // Observe an actual active SQL lock-holder instead of assuming CI timing.
  for (let attempt = 0; attempt < 25; attempt += 1) {
    const count = sql("SELECT count(*) FROM pg_catalog.pg_stat_activity WHERE " +
      "state='active' AND wait_event_type='Timeout' AND query LIKE '%" + marker + "%';");
    if (Number(count) >= 1) return;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error('Database lock-holder barrier not observed: ' + marker);
}
function scopedInvocation(id, scopeSession, scopeOutput, command) {
  const candidate = { ...caseDoc, output: { ...caseDoc.output,
    session_id: scopeSession, output_id: scopeOutput } };
  return 'SELECT public.matchdesk_commit_producer_grant(' +
    [id, actor, 'ci-issuer', tenant, scopeSession, scopeOutput, 'create', command]
      .map(x => "'" + x + "'").join(',') +
    ',0,NULL,' + "'" + digest1 + "'," + q(candidate) + ',' + q(entry) + ');';
}
function scopedGrant(id, scopeSession, scopeOutput) {
  // CI fixture issuer is physically separate from restricted execution.
  sql(grantSql(id));
  sql("UPDATE public.matchdesk_producer_action_grants SET session_id='" + scopeSession +
    "',output_id='" + scopeOutput + "' WHERE grant_id='" + id + "';");
}

const grantSql = (id, action = 'create', seconds = 600) =>
  'INSERT INTO public.matchdesk_producer_action_grants ' +
  '(grant_id,tenant_id,session_id,output_id,actor_id,issuer,action,binding,expected_generation,expires_at) VALUES (' +
  [id,tenant,session,output,actor,'ci-issuer',action].map(x => "'" + x + "'").join(',') +
  ',' + q(binding) + ",0,clock_timestamp() + interval '" + seconds + " seconds');";
const invoke = (id, identity = actor, command = 'ci-command-000001') =>
  'SELECT public.matchdesk_commit_producer_grant(' +
  [id,identity,'ci-issuer',tenant,session,output,'create',command].map(x => "'" + x + "'").join(',') +
  ',0,NULL,' + "'" + digest1 + "'," + q(caseDoc) + ',' + q(entry) + ');';
try {
  await check('migration is repeatable and callable only when role is granted', () => {
    const migration = readFileSync('backend/postgres/migrations/006_producer_atomic_grants.sql','utf8');
    sql(migration); sql(migration);
    sql("CREATE ROLE matchdesk_grant_ci LOGIN;");
    assert.equal(sql("SELECT has_function_privilege('matchdesk_grant_ci','public.matchdesk_commit_producer_grant(text,text,text,text,text,text,text,text,bigint,text,text,jsonb,jsonb)','EXECUTE');"), 'f');
    sql("GRANT CONNECT ON DATABASE matchdesk TO matchdesk_grant_ci;");
    sql("GRANT USAGE ON SCHEMA public TO matchdesk_grant_ci;");
    sql("GRANT EXECUTE ON FUNCTION public.matchdesk_commit_producer_grant(text,text,text,text,text,text,text,text,bigint,text,text,jsonb,jsonb) TO matchdesk_grant_ci;");
    assert.equal(sql("SELECT has_function_privilege('matchdesk_grant_ci','public.matchdesk_commit_producer_grant(text,text,text,text,text,text,text,text,bigint,text,text,jsonb,jsonb)','EXECUTE');"), 't');
    assert.equal(sql("SELECT has_table_privilege('matchdesk_grant_ci','public.matchdesk_producer_action_grants','UPDATE');"), 'f');
    assert.equal(sql("SELECT has_table_privilege('matchdesk_grant_ci','public.matchdesk_producer_cases','UPDATE');"), 'f');
  });
  await check('revocation and invalid actor fail before any case write', () => {
    sql(grantSql('ci-revoked-grant-01'));
    sql("UPDATE public.matchdesk_producer_action_grants SET revoked_at=clock_timestamp() WHERE grant_id='ci-revoked-grant-01';");
    assert.equal(sql(executeAsRestricted(invoke('ci-revoked-grant-01'))), 'f');
    sql(grantSql('ci-wrong-actor-01'));
    assert.equal(sql(executeAsRestricted(invoke('ci-wrong-actor-01','forged-actor'))), 'f');
    sql(grantSql('ci-wrong-issuer-01'));
    assert.equal(sql(executeAsRestricted(invoke('ci-wrong-issuer-01').replace("'ci-issuer'", "'other-issuer'"))), 'f');
    assert.equal(sql("SELECT count(*) FROM matchdesk_producer_cases WHERE tenant_id='ci-tenant';"), '0');
  });
  await check('valid grant commits case and audit and cannot replay', () => {
    sql(grantSql(grantId));
    assert.equal(sql(executeAsRestricted(invoke(grantId))), 't');
    assert.equal(sql(executeAsRestricted(invoke(grantId))), 'f');
    assert.equal(sql("SELECT generation FROM matchdesk_producer_cases WHERE tenant_id='ci-tenant';"), '1');
    assert.equal(sql("SELECT count(*) FROM matchdesk_producer_audit WHERE tenant_id='ci-tenant';"), '1');
    assert.equal(sql("SELECT count(*) FROM matchdesk_producer_action_grants WHERE grant_id='" + grantId + "' AND consumed_at IS NOT NULL;"), '1');
  });
  await check('conflicting case insert leaves grant unconsumed', () => {
    sql(grantSql('ci-conflict-grant-01'));
    assert.equal(sql(executeAsRestricted(invoke('ci-conflict-grant-01'))), 'f');
    assert.equal(sql("SELECT count(*) FROM matchdesk_producer_action_grants WHERE grant_id='ci-conflict-grant-01' AND consumed_at IS NULL;"), '1');
  });
  await check('expired grant is denied and cannot spend its capability', () => {
    sql(grantSql('ci-expired-grant-01', 'create', -1));
    assert.equal(sql(executeAsRestricted(invoke('ci-expired-grant-01'))), 'f');
    assert.equal(sql("SELECT count(*) FROM matchdesk_producer_action_grants WHERE grant_id='ci-expired-grant-01' AND consumed_at IS NULL;"), '1');
  });
  await check('restricted role cannot directly forge a case, audit or grant', () => {
    const attempts = [
      "SET ROLE matchdesk_grant_ci; INSERT INTO public.matchdesk_producer_cases (tenant_id) VALUES ('forged');",
      "SET ROLE matchdesk_grant_ci; INSERT INTO public.matchdesk_producer_audit (tenant_id) VALUES ('forged');",
      "SET ROLE matchdesk_grant_ci; UPDATE public.matchdesk_producer_action_grants SET revoked_at=NULL;",
    ];
    for (const attempt of attempts) sql(attempt, /permission denied/i);
    assert.equal(sql("SELECT generation FROM matchdesk_producer_cases WHERE tenant_id='ci-tenant';"), '1');
  });
  await check('audit insertion fault cannot burn grant or advance generation', () => {
    sql(grantSql('ci-audit-fault-01'));
    // The restricted one-use operation must roll back the case insert as well.
    // A fresh tenant/scope is selected to prevent an existing PK conflict.
    const newSession = 'ci-rollback-session';
    const newOutput = 'ci-rollback-output';
    const revisedGrant = { ...binding };
    sql("UPDATE matchdesk_producer_action_grants SET session_id='" + newSession +
        "',output_id='" + newOutput + "' WHERE grant_id='ci-audit-fault-01';");
    const freshCase = { ...caseDoc, output: { ...caseDoc.output, session_id: newSession, output_id: newOutput } };
    sql([
      "CREATE OR REPLACE FUNCTION matchdesk_ci_grant_reject_audit() RETURNS trigger LANGUAGE plpgsql AS $f$",
      "BEGIN IF NEW.session_id='ci-rollback-session' THEN RAISE EXCEPTION 'CI atomic audit rollback'; END IF; RETURN NEW; END; $f$;",
      "CREATE TRIGGER matchdesk_ci_grant_reject_audit BEFORE INSERT ON matchdesk_producer_audit",
      "FOR EACH ROW EXECUTE FUNCTION matchdesk_ci_grant_reject_audit();",
    ].join(' '));
    const candidate = 'SELECT public.matchdesk_commit_producer_grant(' +
      ["ci-audit-fault-01",actor,'ci-issuer',tenant,newSession,newOutput,'create','ci-rollback-command-01']
        .map(x=>"'"+x+"'").join(',') + ',0,NULL,' +
      "'" + digest1 + "'," + q(freshCase) + ',' + q(entry) + ');';
    sql(executeAsRestricted(candidate), /CI atomic audit rollback/);
    assert.equal(sql("SELECT count(*) FROM matchdesk_producer_cases WHERE session_id='ci-rollback-session';"), '0');
    assert.equal(sql("SELECT count(*) FROM matchdesk_producer_action_grants WHERE grant_id='ci-audit-fault-01' AND consumed_at IS NULL;"), '1');
    sql("DROP TRIGGER matchdesk_ci_grant_reject_audit ON matchdesk_producer_audit;");
    sql("DROP FUNCTION matchdesk_ci_grant_reject_audit();");
  });

  await check('two restricted writers cannot consume the same grant twice', async () => {
    const grant = 'ci-parallel-grant-0001';
    const sc = 'ci-parallel-session', out = 'ci-parallel-output';
    scopedGrant(grant, sc, out);
    const call = executeAsRestricted(scopedInvocation(grant, sc, out, 'ci-parallel-command-01'));
    const results = await Promise.all([concurrentSql(call), concurrentSql(call)]);
    assert.deepEqual(results.sort(), ['f', 't']);
    assert.equal(sql("SELECT count(*) FROM matchdesk_producer_cases WHERE session_id='" + sc + "';"), '1');
    assert.equal(sql("SELECT count(*) FROM matchdesk_producer_audit WHERE session_id='" + sc + "';"), '1');
    assert.equal(sql("SELECT count(*) FROM matchdesk_producer_action_grants WHERE grant_id='" +
      grant + "' AND consumed_at IS NOT NULL;"), '1');
  });
  await check('revocation committing first denies a concurrent restricted writer', async () => {
    const grant = 'ci-revoke-before-write-01';
    const sc = 'ci-revoke-first-session', out = 'ci-revoke-first-output';
    scopedGrant(grant, sc, out);
    // Hold the revoked grant row so that the writer must wait for the revocation.
    const revoker = concurrentSql("BEGIN; UPDATE matchdesk_producer_action_grants " +
      "SET revoked_at=clock_timestamp() WHERE grant_id='" + grant + "';" +
      "SELECT pg_sleep(2) /* ci-revoke-first-holding */; COMMIT;");
    await waitForHeldTransaction('ci-revoke-first-holding');
    const writer = concurrentSql(executeAsRestricted(scopedInvocation(grant, sc, out,
      'ci-revoke-first-command')));
    const [, decision] = await Promise.all([revoker, writer]);
    assert.equal(decision, 'f');
    assert.equal(sql("SELECT count(*) FROM matchdesk_producer_cases WHERE session_id='" + sc + "';"), '0');
    assert.equal(sql("SELECT count(*) FROM matchdesk_producer_action_grants WHERE grant_id='" +
      grant + "' AND revoked_at IS NOT NULL AND consumed_at IS NULL;"), '1');
  });
  await check('writer committing first defeats conditional revocation', async () => {
    const grant = 'ci-write-before-revoke-01';
    const sc = 'ci-writer-first-session', out = 'ci-writer-first-output';
    scopedGrant(grant, sc, out);
    // The writer has already locked the grant when this trigger sleeps.
    sql([
      "CREATE FUNCTION matchdesk_ci_grant_writer_barrier() RETURNS trigger LANGUAGE plpgsql AS $f$",
      "BEGIN IF NEW.session_id='ci-writer-first-session' THEN PERFORM pg_sleep(3);",
      "END IF; RETURN NEW; END; $f$;",
      "CREATE TRIGGER matchdesk_ci_grant_writer_barrier BEFORE INSERT ON",
      "matchdesk_producer_cases FOR EACH ROW EXECUTE FUNCTION matchdesk_ci_grant_writer_barrier();"
    ].join(' '));
    const writer = concurrentSql(executeAsRestricted(scopedInvocation(grant, sc, out,
      'ci-writer-first-command-01')));
    await waitForHeldTransaction('ci-writer-first-command-01');
    const revoker = concurrentSql("UPDATE matchdesk_producer_action_grants " +
      "SET revoked_at=clock_timestamp() WHERE grant_id='" + grant +
      "' AND consumed_at IS NULL RETURNING grant_id;");
    const [writerOutcome, revocationOutcome] = await Promise.all([writer, revoker]);
    assert.equal(writerOutcome, 't');
    assert.equal(revocationOutcome, '');
    assert.equal(sql("SELECT count(*) FROM matchdesk_producer_action_grants WHERE grant_id='" +
      grant + "' AND consumed_at IS NOT NULL AND revoked_at IS NULL;"), '1');
    assert.equal(sql("SELECT count(*) FROM matchdesk_producer_audit WHERE session_id='" + sc + "';"), '1');
    sql('DROP TRIGGER matchdesk_ci_grant_writer_barrier ON matchdesk_producer_cases;');
    sql('DROP FUNCTION matchdesk_ci_grant_writer_barrier();');
  });
  await check('a forged approval cannot skip independent reverification', () => {
    const id = 'ci-skip-reverify-approve-01';
    sql(grantSql(id, 'approve'));
    sql("UPDATE matchdesk_producer_action_grants SET expected_generation=1 WHERE grant_id='" + id + "';");
    const approval = { ...entry, action: 'approved', reason: 'unverified approval attempt' };
    const forgedCase = { ...caseDoc, generation: 2,
      review: { ...caseDoc.review, status: 'approved', audit: [entry, approval] } };
    const attempt = 'SELECT public.matchdesk_commit_producer_grant(' +
      [id, actor, 'ci-issuer', tenant, session, output, 'approve', 'ci-skip-reverify-command-01']
        .map(x => "'" + x + "'").join(',') +
      ",1,'" + digest1 + "','" + digest2 + "'," + q(forgedCase) + ',' + q(approval) + ');';
    assert.equal(sql(executeAsRestricted(attempt)), 'f');
    assert.equal(sql("SELECT generation FROM matchdesk_producer_cases WHERE session_id='" +
      session + "';"), '1');
    assert.equal(sql("SELECT count(*) FROM matchdesk_producer_audit WHERE session_id='" +
      session + "';"), '1');
    assert.equal(sql("SELECT count(*) FROM matchdesk_producer_action_grants WHERE grant_id='" +
      id + "' AND consumed_at IS NULL;"), '1');
  });
  await check('a revision without a newer item version is denied', () => {
    const id = 'ci-stale-edit-grant-0001';
    sql(grantSql(id, 'edit'));
    sql("UPDATE matchdesk_producer_action_grants SET expected_generation=1 WHERE grant_id='" + id + "';");
    const badEdit = { ...entry, action: 'revision_opened', reason: 'stale revision' };
    const forgedCase = { ...caseDoc, generation: 2,
      review: { ...caseDoc.review, status: 'pending_verification', audit: [entry, badEdit] } };
    const attempt = 'SELECT public.matchdesk_commit_producer_grant(' +
      [id, actor, 'ci-issuer', tenant, session, output, 'edit', 'ci-stale-edit-command-01']
        .map(x => "'" + x + "'").join(',') +
      ",1,'" + digest1 + "','" + digest2 + "'," + q(forgedCase) + ',' + q(badEdit) + ');';
    assert.equal(sql(executeAsRestricted(attempt)), 'f');
    assert.equal(sql("SELECT generation FROM matchdesk_producer_cases WHERE session_id='" +
      session + "';"), '1');
  });
  await check('reverified generation can then receive one real scoped approval', () => {
    // This is a synthetic state-machine trace; not a live person or MFA grant.
    const revId = 'ci-good-reverify-grant-01';
    sql(grantSql(revId, 'reverify'));
    sql("UPDATE matchdesk_producer_action_grants SET expected_generation=1 WHERE grant_id='" +
      revId + "';");
    const reverified = { ...entry, action: 'reverified', reason: 'synthetic evidence reverified' };
    const reviewedCase = { ...caseDoc, generation: 2,
      review: { ...caseDoc.review, status: 'ready_for_decision', audit: [entry, reverified] } };
    const reverify = 'SELECT public.matchdesk_commit_producer_grant(' +
      [revId, actor, 'ci-issuer', tenant, session, output, 'reverify', 'ci-good-reverify-command-01']
        .map(x => "'" + x + "'").join(',') +
      ",1,'" + digest1 + "','" + digest2 + "'," + q(reviewedCase) + ',' + q(reverified) + ');';
    assert.equal(sql(executeAsRestricted(reverify)), 't');
    const approveId = 'ci-good-approval-grant-01';
    sql(grantSql(approveId, 'approve'));
    sql("UPDATE matchdesk_producer_action_grants SET expected_generation=2 WHERE grant_id='" +
      approveId + "';");
    const approved = { ...entry, action: 'approved', reason: 'synthetic review decision' };
    const approvedCase = { ...caseDoc, generation: 3,
      review: { ...caseDoc.review, status: 'approved', audit: [entry, reverified, approved] } };
    const approval = 'SELECT public.matchdesk_commit_producer_grant(' +
      [approveId, actor, 'ci-issuer', tenant, session, output, 'approve', 'ci-good-approval-command-01']
        .map(x => "'" + x + "'").join(',') +
      ",2,'" + digest2 + "','" + 'c'.repeat(64) + "'," +
      q(approvedCase) + ',' + q(approved) + ');';
    assert.equal(sql(executeAsRestricted(approval)), 't');
    assert.equal(sql(executeAsRestricted(approval)), 'f');
    assert.equal(sql("SELECT generation FROM matchdesk_producer_cases WHERE session_id='" +
      session + "';"), '3');
    assert.equal(sql("SELECT count(*) FROM matchdesk_producer_audit WHERE session_id='" +
      session + "';"), '3');
  });
  report.status = 'PASS';
} catch (error) { report.status = 'FAIL'; console.error(String(error)); process.exitCode = 1; }
finally {
  mkdirSync('artifacts/integration', { recursive: true });
  writeFileSync('artifacts/integration/producer-grant-atomic.json', JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify(report, null, 2));
}
