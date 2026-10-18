/** Migrate the unmounted producer confirmation-staging boundary in disposable CI.
 * This tests database resource presence, idempotency and default-denied ACL;
 * it does not mint verified approvals, prove MFA or deploy the migration.
 */
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';

const project = process.env.COMPOSE_PROJECT_NAME ?? '';
if (process.env.CI !== 'true' || !/^matchdesk-it-[0-9]+-[0-9]+$/.test(project)) {
  throw new Error('Confirmation staging migration is restricted to isolated CI');
}
function sql(statement) {
  const result = spawnSync('docker', ['compose', '--project-name', project,
    'exec', '-T', 'postgres', 'psql', '-X', '-v', 'ON_ERROR_STOP=1',
    '-U', 'matchdesk', '-d', 'matchdesk', '-q', '-A', '-t', '-f', '-'],
  { input: statement, encoding: 'utf8', timeout: 30000, maxBuffer: 1048576 });
  if (result.error) throw result.error;
  assert.equal(result.status, 0, result.stderr);
  return result.stdout.trim();
}
const migration = readFileSync(
  'backend/postgres/migrations/008_producer_confirmation_staging.sql', 'utf8'
);
// Idempotent application before any workload ACL is provisioned. A candidate
// migration must fail closed if the staging function cannot be created twice.
sql(migration);
sql(migration);
const fn = 'public.matchdesk_stage_producer_confirmation(' +
  'text,text,text,text,text,text,text,bigint,jsonb,text,text,text,timestamptz)';
assert.equal(sql("SELECT has_function_privilege('public', '" + fn +
  "', 'EXECUTE');"), 'f');
assert.equal(sql("SELECT count(*) FROM pg_catalog.pg_proc WHERE oid='" +
  fn + "'::regprocedure AND prosecdef;"), '1');
console.log('MATCHDESK_P4_STAGING_MIGRATION_PASS: idempotent, definer, PUBLIC denied');
