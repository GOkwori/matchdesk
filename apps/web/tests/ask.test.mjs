/** Ask MatchDesk: every factual answer is computed by the engine and verified before it is shown.
 *
 * Run: node --experimental-strip-types --test apps/web/tests/ask.test.mjs
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { expandLog, computeMetric } from '../src/studio/verifier.ts';
import { HELP, SUGGESTIONS, answerPlan, ask, parseQuestion, resolveWindow, validatePlan } from '../src/studio/ask.ts';

const here = dirname(fileURLToPath(import.meta.url));
const read = (path) => JSON.parse(readFileSync(join(here, path), 'utf8'));
const data = read('../src/studio/generated/nbr-riv.json');
const ctx = {
  events: expandLog(read('../src/studio/generated/nbr-riv-events.json')),
  names: data.display_names,
  teams: { nbr: 'Northbridge', riv: 'Riverside' },
  replayEndMs: data.replay_end_ms,
  matchId: data.match_id,
};
const answer = (q) => ask(q, ctx, ctx).answer;
const statuses = (a) => a.lines.map((l) => l.result.status);

test('every suggested question gets a real answer, and every factual line verifies', () => {
  for (const q of SUGGESTIONS) {
    const a = answer(q);
    assert.notEqual(a.kind, 'unknown', q);
    if (a.kind === 'match') {
      assert.ok(a.lines.length > 0, q);
      assert.deepEqual(new Set(statuses(a)), new Set(['verified']), `${q}: ${a.lines.map((l) => `${l.claim.text} -> ${l.result.reason}`).join(' | ')}`);
    }
  }
});

test('the score and the scorers match the canonical log', () => {
  const score = answer("What's the score?");
  assert.equal(score.kind, 'match');
  assert.deepEqual(score.lines.map((l) => l.claim.text), ['Northbridge scored 2 goals up to 67:12.', 'Riverside scored 1 goal up to 67:12.']);
  assert.equal(score.derived, 'Northbridge lead 2–1.');
  const scorers = answer('Who scored?');
  assert.deepEqual(scorers.lines.map((l) => l.claim.text), [
    'Okafor scored for Northbridge at 34:18.',
    'Lindqvist scored for Riverside at 41:03.',
    'Okafor scored for Northbridge at 58:17.',
  ]);
  assert.deepEqual(scorers.lines.map((l) => l.result.query_id), Array(3).fill('event-goal-scorer-v1'));
  const firstHalf = answer('who scored in the second half');
  assert.deepEqual(firstHalf.lines.map((l) => l.claim.fact.event_id), ['E-1366']);
});

test('figures agree with the studio and with direct recomputation', () => {
  const possession = answer('Northbridge possession');
  assert.equal(possession.lines[0].claim.text, 'Northbridge had 58% possession up to 67:12.');
  const shots = answer('how many shots did each team have');
  assert.deepEqual(shots.lines.map((l) => l.claim.assertion.value), [data.statistics.nbr.shots, data.statistics.riv.shots]);
  assert.equal(shots.derived, 'Northbridge had more shots than Riverside.');
  const second = answer('Who had more shots in the second half?');
  for (const line of second.lines) {
    const w = line.claim.assertion.window;
    assert.equal(w.period, 2);
    assert.equal(line.claim.assertion.value, computeMetric('shots.v1', ctx.events, line.claim.assertion.subject, w));
    assert.equal(line.claim.evidence_event_ids.length, line.claim.assertion.value, 'a count cites exactly the counted events');
  }
});

test('players, windows and every registered metric produce verified sentences', () => {
  const questions = [
    'How many shots did Okafor take?', 'Okafor goals', 'Riverside pass accuracy in the first half', 'xG for both teams',
    'final third entries after 60 minutes', 'possession between 30 and 45 minutes', 'shots in the last 15 minutes',
    'Northbridge xG before half-time', 'Riverside shots since the 50th minute', 'possession in the first 20 minutes',
  ];
  for (const q of questions) {
    const a = answer(q);
    assert.equal(a.kind, 'match', q);
    assert.deepEqual(new Set(statuses(a)), new Set(['verified']), `${q}: ${a.lines.map((l) => `${l.claim.text} -> ${l.result.reason}`).join(' | ')}`);
  }
  assert.match(answer('How many shots did Okafor take?').lines[0].claim.text, /^Okafor took \d+ shots? up to 67:12\.$/);
  assert.match(answer('possession between 30 and 45 minutes').lines[0].claim.text, /between 30′ and 45′/);
});

test('a sentence that misstates its figure is caught by the same verifier', () => {
  const line = answer('Northbridge possession').lines[0];
  const forged = { ...line.claim, text: 'Northbridge had 59% possession up to 67:12.' };
  const result = answerPlan({ intent: 'metric', metric: 'possession_time.v1', subjects: ['nbr'], window: {} }, ctx).lines[0].result;
  assert.equal(result.status, 'verified');
  // The engine never emits a forged sentence, but the check it relies on rejects one.
  return import('../src/studio/verifier.ts').then(({ verifyClaim }) => {
    const evidence = { match_id: ctx.matchId, event_ids: ctx.events.map((e) => e.event_id), window: { from_ms: 0, to_ms: ctx.replayEndMs } };
    assert.equal(verifyClaim(forged, evidence, ctx.events, ctx.names).status, 'needs_revision');
  });
});

test('naming a team or player alone gives a short verified summary', () => {
  for (const [q, n] of [['Tell me about Okafor', 4], ['How did Riverside do in the first half?', 4], ['Mensah', 4]]) {
    const a = answer(q);
    assert.equal(a.kind, 'match', q);
    assert.equal(a.lines.length, n, q);
    assert.deepEqual(new Set(statuses(a)), new Set(['verified']), `${q}: ${a.lines.map((l) => `${l.claim.text} -> ${l.result.reason}`).join(' | ')}`);
  }
  assert.deepEqual(validatePlan({ intent: 'summary', subject: 'riv-11', window: {} }, ctx), { intent: 'summary', subject: 'riv-11', window: {} });
  assert.equal(validatePlan({ intent: 'summary', subject: 'ars-14', window: {} }, ctx), null);
});

test('guidance comes from the help index, with links', () => {
  const eligible = answer('What does Eligible mean?');
  assert.equal(eligible.kind, 'help');
  assert.match(eligible.text, /human producer/);
  assert.equal(eligible.link.href, '/producer/queue');
  assert.equal(answer('start the tour').link.href, '/match/nbr-riv?tour=1');
  assert.equal(answer('how do I approve a draft').link.href, '/producer/publish/D-031');
  assert.equal(answer('is this real data?').link.href, '/about');
  for (const topic of HELP) assert.ok(topic.text.length < 420, `${topic.id} stays short`);
});

test('it declines what it cannot check, and says why', () => {
  assert.equal(answer('Who will win?').kind, 'decline');
  assert.match(answer('How did Arsenal do last season?').text, /only know this synthetic match/);
  assert.match(answer('Okafor possession').text, /measured for teams, not players/);
  assert.match(answer('shots after 80 minutes').text, /replay stops at 67:12/);
  assert.match(answer('shots between 50 and 40 minutes').text, /start must come before the end/);
  assert.equal(answer('tell me a joke about cheese').kind, 'unknown');
  assert.equal(answer('who is the best player').kind, 'unknown');
  assert.equal(answer('').kind, 'unknown');
});

test('windows resolve to the verifier windows the sentences describe', () => {
  const end = ctx.replayEndMs;
  assert.deepEqual(resolveWindow({ period: 1 }, end).window, { period: 1, from_ms: 0, to_ms: end });
  assert.deepEqual(resolveWindow({ from_minute: 60 }, end).window, { from_ms: 3_600_000, to_ms: end });
  assert.deepEqual(resolveWindow({ last_minutes: 10 }, end).window, { from_ms: end - 600_000, to_ms: end });
  assert.deepEqual(parseQuestion('possession after half-time', ctx), { intent: 'metric', metric: 'possession_time.v1', subjects: [], window: { period: 2 } });
});

test('plans from a model are accepted only in the exact schema', () => {
  const good = { intent: 'metric', metric: 'shots.v1', subjects: ['nbr-09'], window: { period: 2 } };
  assert.deepEqual(validatePlan(good, ctx), good);
  const bad = [
    null, 'shots', [], { intent: 'metric' }, { ...good, metric: 'tackles.v1' }, { ...good, subjects: ['ars-14'] },
    { ...good, subjects: ['nbr', 'riv', 'nbr-09'] }, { ...good, window: { period: 3 } }, { ...good, window: { from_minute: -5 } },
    { ...good, window: { from_minute: 1.5 } }, { ...good, text: 'Northbridge had 99 shots' }, { ...good, window: { sql: 'drop' } },
    { intent: 'help', topic: 'not-a-topic' }, { intent: 'out_of_scope', reason: 'whatever' }, { intent: 'execute', command: 'approve' },
  ];
  for (const plan of bad) assert.equal(validatePlan(plan, ctx), null, JSON.stringify(plan));
  assert.deepEqual(validatePlan({ intent: 'scorers' }, ctx), { intent: 'scorers', window: {} });
});

test('help and declines work before the event log has loaded', () => {
  assert.equal(ask('What does Eligible mean?', null, ctx).answer.kind, 'help');
  assert.match(ask("What's the score?", null, ctx).answer.text, /still loading/);
});
