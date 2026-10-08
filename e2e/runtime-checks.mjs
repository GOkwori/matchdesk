/** Exercise an explicitly isolated Compose project; never touch a normal local stack. */
import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { execFileSync, spawnSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';

const project = process.env.COMPOSE_PROJECT_NAME ?? '';
if (process.env.CI !== 'true' || !/^matchdesk-it-[0-9]+-[0-9]+$/.test(project)) {
  throw new Error('Runtime probes require CI and an isolated matchdesk-it-<run>-<attempt> project');
}
const report = {
  source_commit: execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim(),
  project, started_at: new Date().toISOString(), status: 'RUNNING', checks: [], containers: [],
  scope: 'Foundation HTTP and PostgreSQL topology only; no application persistence or AI qualification.',
};
const event = {
  event_id: 'integration-e0001', match_id: 'integration-match', sequence: 1,
  period: 1, match_clock_ms: 1000, type: 'pass', team_id: 'fiction-a', player_id: 'a-08',
  possession_id: 1, location: { x: 50, y: 30 }, end_location: { x: 65, y: 35 },
  outcome: 'complete', tags: ['integration_fixture'], synthetic: true,
};

/** Bound external commands and avoid printing container environment variables. */
function docker(...args) {
  return execFileSync('docker', args, { encoding: 'utf8', timeout: 90000 }).trim();
}

/** The project name is explicit on every command, including restarts. */
function compose(...args) {
  return docker('compose', '--project-name', project, ...args);
}

/** Keep each assertion's duration and failure; no failed case is converted to a skip. */
async function check(name, assertion) {
  const started = performance.now();
  try {
    await assertion();
    report.checks.push({ name, status: 'PASS', duration_ms: Math.round(performance.now() - started) });
  } catch (error) {
    report.checks.push({ name, status: 'FAIL', message: String(error), duration_ms: Math.round(performance.now() - started) });
    throw error;
  }
}

/** Probe real HTTP with a finite timeout; no mocks or in-process test client. */
async function request(path, body, origin = 'http://127.0.0.1:8000') {
  return fetch(origin + path, {
    ...(body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body }),
    signal: AbortSignal.timeout(8000),
  });
}

/** Wait for a restart without confusing liveness with the deliberately blocked readiness. */
async function waitHealthy(service) {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    const id = compose('ps', '-q', service);
    if (id && docker('inspect', '--format', '{{.State.Health.Status}}', id) === 'healthy') return;
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`${service} did not become healthy within 30 seconds`);
}

/** Fixed test SQL only, running inside the disposable database via its local socket. */
function sql(statement) {
  return compose('exec', '-T', 'postgres', 'psql', '--no-psqlrc', '--username', 'matchdesk',
    '--dbname', 'matchdesk', '--set', 'ON_ERROR_STOP=1', '--tuples-only', '--no-align', '--command', statement);
}

let digest;
try {
  await check('container isolation and least-privilege runtime', async () => {
    for (const service of ['postgres', 'api', 'web']) {
      const id = compose('ps', '-q', service);
      assert.match(id, /^[0-9a-f]+$/);
      const info = JSON.parse(docker('inspect', id))[0];
      assert.equal(info.Config.Labels['com.docker.compose.project'], project);
      if (service === 'postgres') {
        assert.equal(Object.keys(info.HostConfig.PortBindings ?? {}).length, 0);
      } else {
        assert.notEqual(docker('exec', id, 'id', '-u'), '0');
        assert.equal(info.HostConfig.ReadonlyRootfs, true);
        assert.ok(info.HostConfig.CapDrop.includes('ALL'));
        assert.ok(info.HostConfig.SecurityOpt.includes('no-new-privileges:true'));
        for (const bindings of Object.values(info.HostConfig.PortBindings ?? {})) {
          for (const binding of bindings ?? []) assert.equal(binding.HostIp, '127.0.0.1');
        }
      }
      // Capture image identity and safe settings only; inspect's Env can contain a password.
      report.containers.push({ service, id, image_id: info.Image, image_ref: info.Config.Image,
        user: info.Config.User, command: info.Config.Cmd, read_only: info.HostConfig.ReadonlyRootfs });
    }
    assert.deepEqual(report.containers.find((item) => item.service === 'web').command, ['node', 'server.js']);
    compose('exec', '-T', 'api', '/app/.venv/bin/python', '-c',
      "import importlib.util as u; assert all(u.find_spec(n) is None for n in ('pytest', 'ruff', 'mypy')); print('runtime dependencies only')");
  });
  await check('liveness is 200 while product readiness is 503', async () => {
    const health = await request('/api/health');
    assert.equal(health.status, 200);
    assert.equal((await health.json()).model_mode, 'not_connected');
    const ready = await request('/api/ready');
    assert.equal(ready.status, 503);
    assert.equal((await ready.json()).status, 'not_ready');
  });
  await check('real HTTP validation and stable content identity', async () => {
    const response = await request('/api/contracts/event/validate', JSON.stringify(event));
    assert.equal(response.status, 200);
    const body = await response.json();
    assert.equal(body.structurally_valid, true);
    assert.equal(body.evidence_verified, false);
    assert.match(body.content_digest, /^[0-9a-f]{64}$/);
    digest = body.content_digest;
    const repeat = await request('/api/contracts/event/validate', JSON.stringify(event));
    assert.equal((await repeat.json()).content_digest, digest);
  });
  await check('invalid and oversized HTTP requests fail closed', async () => {
    const invalid = await request('/api/contracts/event/validate', JSON.stringify({ ...event, synthetic: 'private-invalid-marker' }));
    assert.equal(invalid.status, 422);
    assert.equal((await invalid.text()).includes('private-invalid-marker'), false);
    const oversized = await request('/api/contracts/event/validate', JSON.stringify({ ...event, unexpected: 'x'.repeat(70000) }));
    assert.equal(oversized.status, 413);
  });
  await check('standalone web forwards to the real API', async () => {
    const page = await request('/', undefined, 'http://127.0.0.1:3000');
    assert.equal(page.status, 200);
    assert.match(await page.text(), /MatchDesk/);
    const response = await request('/api/contracts/event/validate', JSON.stringify(event), 'http://127.0.0.1:3000');
    assert.equal(response.status, 200);
    assert.equal((await response.json()).content_digest, digest);
    const ready = await request('/api/ready', undefined, 'http://127.0.0.1:3000');
    assert.equal(ready.status, 503);
  });
  await check('PostgreSQL rejects wrong TCP passwords', async () => {
    const result = spawnSync('docker', ['compose', '--project-name', project, 'exec', '-T',
      '--env', `PGPASSWORD=wrong-${randomUUID()}`, 'postgres', 'psql', '--no-psqlrc',
      '--host', '127.0.0.1', '--username', 'matchdesk', '--dbname', 'matchdesk', '--command', 'SELECT 1'],
    { encoding: 'utf8', timeout: 15000 });
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, /password authentication failed/i);
    // The correct generated password is expanded only inside the container, never logged.
    assert.equal(compose('exec', '-T', 'postgres', 'sh', '-c',
      'PGPASSWORD="$POSTGRES_PASSWORD" exec psql --no-psqlrc -h 127.0.0.1 -U matchdesk -d matchdesk -Atc "SELECT 1"'), '1');
  });
  await check('PostgreSQL commits, rolls back and enforces uniqueness', async () => {
    sql('CREATE TABLE integration_probe (id integer PRIMARY KEY, marker text NOT NULL);');
    sql("BEGIN; INSERT INTO integration_probe VALUES (1, 'synthetic-committed'); COMMIT;");
    sql("BEGIN; INSERT INTO integration_probe VALUES (2, 'synthetic-rollback'); ROLLBACK;");
    assert.equal(sql('SELECT count(*) FROM integration_probe;'), '1');
    const duplicate = spawnSync('docker', ['compose', '--project-name', project, 'exec', '-T', 'postgres',
      'psql', '--no-psqlrc', '-U', 'matchdesk', '-d', 'matchdesk', '-v', 'ON_ERROR_STOP=1', '-c',
      "INSERT INTO integration_probe VALUES (1, 'duplicate');"], { encoding: 'utf8', timeout: 15000 });
    assert.notEqual(duplicate.status, 0);
    assert.match(duplicate.stderr, /duplicate key/i);
    assert.equal(sql('SELECT count(*) FROM integration_probe;'), '1');
  });
  await check('PostgreSQL row survives a database container restart', async () => {
    compose('restart', 'postgres');
    await waitHealthy('postgres');
    assert.equal(sql('SELECT marker FROM integration_probe WHERE id=1;'), 'synthetic-committed');
    sql('DROP TABLE integration_probe;');
  });
  await check('API and web recover after an API container restart', async () => {
    compose('restart', 'api');
    await waitHealthy('api');
    const response = await request('/api/contracts/event/validate', JSON.stringify(event), 'http://127.0.0.1:3000');
    assert.equal(response.status, 200);
    assert.equal((await response.json()).content_digest, digest);
    assert.equal((await request('/api/ready')).status, 503);
  });
  report.status = 'PASS';
} catch (error) {
  report.status = 'FAIL';
  console.error(error);
  process.exitCode = 1;
} finally {
  report.completed_at = new Date().toISOString();
  mkdirSync('artifacts/integration', { recursive: true });
  writeFileSync('artifacts/integration/runtime-checks.json', JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify(report, null, 2));
}
