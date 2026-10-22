/** Control vs chaos phases and player focus: labels follow the published rule and every sentence verifies. */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { expandLog } from '../src/studio/verifier.ts';
import {
  CHAOS_RECOVERIES_PER_MINUTE, CONTROL_ACCURACY, CONTROL_POSSESSION, controlPhases, playerFocus, readWindows,
} from '../src/studio/insight-engine.ts';

const here = dirname(fileURLToPath(import.meta.url));
const read = (path) => JSON.parse(readFileSync(join(here, path), 'utf8'));
const exportData = read('../src/studio/generated/nbr-riv.json');
const ctx = {
  events: expandLog(read('../src/studio/generated/nbr-riv-events.json')),
  names: exportData.display_names,
  teams: { nbr: 'Northbridge', riv: 'Riverside' },
  replayEndMs: exportData.replay_end_ms,
  matchId: exportData.match_id,
};

test('windows tile the replay and each label follows the rule', () => {
  const windows = readWindows(ctx);
  assert.equal(windows[0].fromMs, 0);
  assert.equal(windows.at(-1).toMs, ctx.replayEndMs);
  for (let i = 1; i < windows.length; i += 1) assert.equal(windows[i].fromMs, windows[i - 1].toMs);
  for (const w of windows) {
    const perMinute = (w.recoveries.nbr + w.recoveries.riv) / ((w.toMs - w.fromMs) / 60000);
    if (w.kind === 'chaos') assert.ok(perMinute >= CHAOS_RECOVERIES_PER_MINUTE);
    else assert.ok(perMinute < CHAOS_RECOVERIES_PER_MINUTE);
    if (w.kind === 'control') {
      const share = w.team === 'nbr' ? w.possession : 1 - w.possession;
      assert.ok(share >= CONTROL_POSSESSION && w.accuracy[w.team] >= CONTROL_ACCURACY);
    }
  }
  const kinds = new Set(windows.map((w) => `${w.kind}:${w.team}`));
  for (const k of ['control:nbr', 'control:riv', 'chaos:null', 'contested:null']) assert.ok(kinds.has(k), k);
});

test('phases join neighbours and every justifying sentence verifies', () => {
  const phases = controlPhases(ctx);
  for (let i = 1; i < phases.length; i += 1) {
    assert.equal(phases[i].fromMs, phases[i - 1].toMs);
    assert.ok(phases[i].kind !== phases[i - 1].kind || phases[i].team !== phases[i - 1].team);
  }
  for (const phase of phases) {
    assert.ok(phase.lines.length >= 2);
    for (const line of phase.lines) assert.equal(line.result.status, 'verified', `${line.claim.text} → ${line.result.reason}`);
  }
  const chaos = phases.find((p) => p.kind === 'chaos');
  assert.equal(chaos.scope, '45:00 to 60:00');
});

test('player focus states every registered figure as a verified sentence', () => {
  const okafor = playerFocus(ctx, 'nbr-09', 'nbr');
  assert.equal(okafor.name, 'Okafor');
  const goals = okafor.lines.find((l) => l.claim.assertion.metric === 'goals.v1');
  assert.equal(goals.claim.text, 'Okafor scored 2 goals up to 67:12.');
  for (const line of okafor.lines) assert.equal(line.result.status, 'verified', `${line.claim.text} → ${line.result.reason}`);
  for (const squad of Object.values(exportData.squads)) {
    for (const player of squad) {
      const focus = playerFocus(ctx, player.player_id, player.player_id.slice(0, 3));
      for (const line of focus.lines) assert.equal(line.result.status, 'verified', `${line.claim.text} → ${line.result.reason}`);
      if (focus.passes === 0) assert.ok(focus.skipped.includes('pass_accuracy.v1'));
    }
  }
});
