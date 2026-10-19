/** Disposable PostgreSQL single-use confirmation issuer smoke/negative paths. */
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';

const project = process.env.COMPOSE_PROJECT_NAME ?? '';
if (process.env.CI !== 'true' || !/^matchdesk-it-[0-9]+-[0-9]+$/.test(project))
  throw new Error('Issuer qualification requires disposable CI');
function sql(query) {
  const r = spawnSync('docker', ['compose','--project-name',project,'exec','-T',
    'postgres','psql','-X','-v','ON_ERROR_STOP=1','-U','matchdesk','-d',
    'matchdesk','-q','-A','-t','-f','-'],
    { input: query, encoding: 'utf8', timeout: 30000 });
  if (r.error) throw r.error;
  assert.equal(r.status, 0, r.stderr);
  return r.stdout.trim();
}
sql(readFileSync('backend/postgres/migrations/007_producer_confirmation_issuance.sql','utf8'));
sql(readFileSync('backend/postgres/migrations/007_producer_confirmation_issuance.sql','utf8'));
const cid = 'b'.repeat(32), digest = 'a'.repeat(64), audit = 'd'.repeat(64);
const binding = "'{}'::jsonb";
const issue = (grant, actor='ci-human') =>
  "SELECT public.matchdesk_issue_confirmed_producer_grant('"+cid+"','"+grant+
  "','ci-tenant','ci-session','ci-output','"+actor+"','ci-issuer','create',0,"+
  binding+",'"+digest+"','"+audit+"');";
sql("INSERT INTO public.matchdesk_producer_confirmations "+
  "(confirmation_id,tenant_id,session_id,output_id,actor_id,issuer,action,"+
  "expected_generation,binding,authorized_case_sha256,authorized_audit_digest,"+
  "proof_digest,confirmed_at,expires_at) VALUES ('"+cid+
  "','ci-tenant','ci-session','ci-output','ci-human','ci-issuer','create',0,"+
  binding+",'"+digest+"','"+audit+"','"+digest+
  "',clock_timestamp(),clock_timestamp()+interval '90 seconds');");
assert.equal(sql(issue('ci-issued-grant-0001','forged-user')), 'f');
assert.equal(sql(issue('ci-issued-grant-0001')), 't');
assert.equal(sql(issue('ci-replayed-grant-0002')), 'f');
assert.equal(sql("SELECT count(*) FROM public.matchdesk_producer_confirmations "+
  "WHERE confirmation_id='"+cid+"' AND issued_grant_id='ci-issued-grant-0001' "+
  "AND consumed_at IS NOT NULL;"), '1');
assert.equal(sql("SELECT count(*) FROM public.matchdesk_producer_action_grants "+
  "WHERE confirmation_id='"+cid+"';"), '1');
sql("REVOKE ALL ON FUNCTION public.matchdesk_issue_confirmed_producer_grant("+
  "text,text,text,text,text,text,text,text,bigint,jsonb,text,text) FROM PUBLIC;");
sql("CREATE ROLE matchdesk_untrusted_issuer_ci NOLOGIN;");
const denied = spawnSync('docker', ['compose','--project-name',project,'exec','-T',
  'postgres','psql','-X','-v','ON_ERROR_STOP=1','-U','matchdesk','-d',
  'matchdesk','-q','-A','-t','-c',
  'SET ROLE matchdesk_untrusted_issuer_ci; '+issue('ci-untrusted-grant-003')],
  { encoding: 'utf8', timeout: 30000 });
assert.notEqual(denied.status, 0, 'untrusted role must not execute issuer');
assert.match(denied.stderr, /permission denied/i);
console.log('MATCHDESK_CONFIRMED_ISSUER_CI_PASS: exact scope, single use, ACL');
