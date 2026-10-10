/**
 * Exercise real P3-05 PostgreSQL audit/CAS controls in the isolated CI topology.
 * No identity adapter, production driver, publishing authority or cloud resources.
 */
import assert from 'node:assert/strict';
import { execFile, execFileSync, spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { promisify } from 'node:util';

const project = process.env.COMPOSE_PROJECT_NAME ?? '';
if (process.env.CI !== 'true' || !/^matchdesk-it-[0-9]+-[0-9]+$/.test(project)) {
  throw new Error('Producer database qualification requires an isolated CI Compose project');
}
const migration = readFileSync('backend/postgres/migrations/001_producer_review.sql', 'utf8');
const args = ['compose', '--project-name', project, 'exec', '-T', 'postgres',
  'psql', '--no-psqlrc', '-X', '-v', 'ON_ERROR_STOP=1',
  '-U', 'matchdesk', '-d', 'matchdesk', '-q', '-A', '-t'];
const execAsync = promisify(execFile);
const report = {
  source_commit: execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim(),
  migration_sha256: createHash('sha256').update(migration).digest('hex'),
  scope: 'Real disposable PostgreSQL DDL/atomic CAS/audit/restart; no live Python driver or OIDC',
  started_at: new Date().toISOString(), status: 'RUNNING', checks: [],
};

/** Pass fixed synthetic SQL via stdin; never interpolate credentials or use shell. */
function sql(command, expectedFailure = null) {
  const result = spawnSync('docker', [...args, '-f', '-'], {
    input: command, encoding: 'utf8', timeout: 30000, maxBuffer: 1048576,
  });
  if (result.error) throw result.error;
  if (expectedFailure) {
    assert.notEqual(result.status, 0, 'Expected database rejection');
    assert.match(result.stderr, expectedFailure);
  } else {
    assert.equal(result.status, 0, 'PostgreSQL failed: ' + result.stderr);
  }
  return result.stdout.trim();
}

/** A separate psql connection for each contender exercises actual MVCC row locks. */
async function concurrentSql(command) {
  const result = await execAsync('docker', [...args, '-c', command], {
    encoding: 'utf8', timeout: 30000, maxBuffer: 1048576,
  });
  return result.stdout.trim();
}

/** Emit a source-bound report even if one asserted invariant fails. */
async function check(name, action) {
  const start = performance.now();
  try {
    await action();
    report.checks.push({ name, status: 'PASS', duration_ms: Math.round(performance.now() - start) });
  } catch (error) {
    report.checks.push({
      name, status: 'FAIL', duration_ms: Math.round(performance.now() - start),
      detail: String(error).slice(0, 500),
    });
    throw error;
  }
}

/** Require the existing isolated database to recover rather than building a new one. */
async function restart() {
  const result = spawnSync('docker', ['compose', '--project-name', project, 'restart', 'postgres'], {
    encoding: 'utf8', timeout: 60000,
  });
  if (result.error) throw result.error;
  assert.equal(result.status, 0, 'PostgreSQL restart failed: ' + result.stderr);
  for (let i = 0; i < 60; i += 1) {
    const id = execFileSync('docker', [
      'compose', '--project-name', project, 'ps', '-q', 'postgres',
    ], { encoding: 'utf8', timeout: 10000 }).trim();
    if (id) {
      const state = execFileSync('docker', [
        'inspect', '--format', '{{.State.Health.Status}}', id,
      ], { encoding: 'utf8', timeout: 10000 }).trim();
      if (state === 'healthy') return;
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error('PostgreSQL did not return to healthy after restart');
}

const where = "tenant_id='integration-tenant' AND session_id='integration-session' AND output_id='integration-output'";
const version = 'SELECT generation FROM matchdesk_producer_cases WHERE ' + where + ';';
const digest = 'SELECT left(audit_digest,1) FROM matchdesk_producer_cases WHERE ' + where + ';';
const audits = 'SELECT count(*) FROM matchdesk_producer_audit WHERE ' + where + ';';

try {
  await check('migration applies twice and installs append-only trigger', () => {
    sql(migration);
    sql(migration);
    assert.equal(sql("SELECT count(*) FROM pg_class WHERE relname IN ('matchdesk_producer_cases','matchdesk_producer_audit') AND relkind='r';"), '2');
    assert.equal(sql("SELECT tgenabled FROM pg_trigger WHERE tgname='matchdesk_audit_is_immutable' AND NOT tgisinternal;"), 'O');
  });
  await check('initial case and audit rows persist in one transaction', () => {
    sql([
      'BEGIN;',
      "INSERT INTO matchdesk_producer_cases (tenant_id,session_id,output_id,generation,case_json,audit_digest) VALUES ('integration-tenant','integration-session','integration-output',1,'{\"fixture\":\"synthetic\",\"generation\":1}'::jsonb,repeat('a',64));",
      "INSERT INTO matchdesk_producer_audit (tenant_id,session_id,output_id,generation,entry_json,audit_digest) VALUES ('integration-tenant','integration-session','integration-output',1,'{\"action\":\"review_started\"}'::jsonb,repeat('a',64));",
      'COMMIT;',
    ].join('\n'));
    assert.equal(sql(version), '1');
    assert.equal(sql(audits), '1');
  });
  await check('generation compare-and-swap updates case and audit transactionally', () => {
    const outcome = sql([
      'BEGIN;',
      "UPDATE matchdesk_producer_cases SET generation=2, case_json='{\"fixture\":\"synthetic\",\"generation\":2}'::jsonb, audit_digest=repeat('b',64) WHERE " + where + " AND generation=1 AND audit_digest=repeat('a',64) RETURNING generation;",
      "INSERT INTO matchdesk_producer_audit (tenant_id,session_id,output_id,generation,entry_json,audit_digest) VALUES ('integration-tenant','integration-session','integration-output',2,'{\"action\":\"reverified\"}'::jsonb,repeat('b',64));",
      'COMMIT;',
    ].join('\n'));
    assert.equal(outcome, '2');
    assert.equal(sql(version), '2');
    assert.equal(sql(digest), 'b');
    assert.equal(sql(audits), '2');
  });
  await check('stale writes and cross-tenant writes fail closed', () => {
    const stale = "WITH changed AS (UPDATE matchdesk_producer_cases SET generation=99 WHERE " +
      where + " AND generation=1 AND audit_digest=repeat('a',64) RETURNING generation) SELECT count(*) FROM changed;";
    assert.equal(sql(stale), '0');
    const foreign = "WITH changed AS (UPDATE matchdesk_producer_cases SET generation=99 WHERE " +
      "tenant_id='foreign-tenant' AND session_id='integration-session' AND output_id='integration-output' " +
      "AND generation=2 RETURNING generation) SELECT count(*) FROM changed;";
    assert.equal(sql(foreign), '0');
    sql([
      'BEGIN;',
      "INSERT INTO matchdesk_producer_cases (tenant_id,session_id,output_id,generation,case_json,audit_digest) VALUES ('second-tenant','integration-session','integration-output',1,'{}'::jsonb,repeat('d',64));",
      "INSERT INTO matchdesk_producer_audit (tenant_id,session_id,output_id,generation,entry_json,audit_digest) VALUES ('second-tenant','integration-session','integration-output',1,'{}'::jsonb,repeat('d',64));",
      'COMMIT;',
    ].join('\n'));
    assert.equal(sql("SELECT generation FROM matchdesk_producer_cases WHERE tenant_id='second-tenant' AND session_id='integration-session' AND output_id='integration-output';"), '1');
    assert.equal(sql(version), '2');
  });
  await check('audit insertion failure rolls back an updated generation', () => {
    sql([
      'BEGIN;',
      "UPDATE matchdesk_producer_cases SET generation=3,audit_digest=repeat('c',64) WHERE " + where + " AND generation=2 AND audit_digest=repeat('b',64);",
      "INSERT INTO matchdesk_producer_audit (tenant_id,session_id,output_id,generation,entry_json,audit_digest) VALUES ('integration-tenant','integration-session','integration-output',2,'{}'::jsonb,repeat('c',64));",
      'COMMIT;',
    ].join('\n'), /duplicate key value violates unique constraint/i);
    assert.equal(sql(version), '2');
    assert.equal(sql(digest), 'b');
    assert.equal(sql(audits), '2');
  });
  await check('audit UPDATE DELETE and TRUNCATE are prohibited', () => {
    sql("UPDATE matchdesk_producer_audit SET entry_json='{}'::jsonb WHERE " + where + ';',
      /MatchDesk producer audit is append-only/);
    sql('DELETE FROM matchdesk_producer_audit WHERE ' + where + ';',
      /MatchDesk producer audit is append-only/);
    sql('TRUNCATE matchdesk_producer_audit;',
      /MatchDesk producer audit is append-only/);
    assert.equal(sql(audits), '2');
  });
  await check('concurrent writers permit exactly one CAS and one new audit', async () => {
    const race = [
      'WITH changed AS (UPDATE matchdesk_producer_cases',
      "SET generation=3,case_json='{\"fixture\":\"synthetic\",\"generation\":3}'::jsonb,audit_digest=repeat('c',64)",
      'WHERE ' + where + " AND generation=2 AND audit_digest=repeat('b',64)",
      'RETURNING tenant_id,session_id,output_id,generation,audit_digest)',
      'INSERT INTO matchdesk_producer_audit (tenant_id,session_id,output_id,generation,entry_json,audit_digest)',
      "SELECT tenant_id,session_id,output_id,generation,'{\"action\":\"reverified\"}'::jsonb,audit_digest FROM changed",
      'RETURNING generation;',
    ].join('\n');
    const results = await Promise.all([concurrentSql(race), concurrentSql(race)]);
    assert.deepEqual(results.sort(), ['', '3']);
    assert.equal(sql(version), '3');
    assert.equal(sql(audits), '3');
    assert.equal(sql(digest), 'c');
  });
  await check('committed generation and append-only history survive database restart', async () => {
    await restart();
    assert.equal(sql(version), '3');
    assert.equal(sql(audits), '3');
    assert.equal(sql(digest), 'c');
    assert.equal(sql(
      "SELECT string_agg(generation::text, ',' ORDER BY generation) FROM matchdesk_producer_audit WHERE " + where + ';',
    ), '1,2,3');
  });
  report.status = 'PASS';
} catch (error) {
  report.status = 'FAIL';
  console.error('Real PostgreSQL producer qualification failed:', String(error));
  process.exitCode = 1;
} finally {
  report.completed_at = new Date().toISOString();
  mkdirSync('artifacts/integration', { recursive: true });
  writeFileSync('artifacts/integration/producer-store-postgres.json', JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify(report, null, 2));
}
