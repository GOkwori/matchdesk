# Verification, evidence and publication integrity

**Status:** Implemented deterministic claim verifier and scoped event
facts, parity-tested TypeScript port, evidence-linked synthetic feeds,
and disposable producer/publisher domain workflows. Real authenticated
producer publication remains **NOT QUALIFIED**.

## Deterministic truth boundary

The server recomputes registered football metrics using the source match
event window. Claims carry typed subject, window, metric, comparator,
value, precision and evidence references. The verifier also binds the
sentence to the asserted statistic, team/player, time and recorded event
fact. Evidence existence alone cannot prove an unsupported sentence.

Measured values are checked with explicit units and stated precision;
rounding semantics are harmonised between Python and TypeScript. The
browser port repeats the verdict against the compact synthetic event
log, but server-owned evidence digests remain authoritative.

The [24 October deterministic benchmark](../evidence/verifier-benchmark-20261024.md)
contains **810 generated false claims correctly rejected** and **295
generated true variants correctly accepted**; these measure authored
rule coverage only. The benchmark discovered a reversed-substitution
wording bug, which was corrected in server and browser implementations.
Negative sentences, unsupported claims and translation quality are
not universally certified.

## Multi-agent flow

![Evidence-bound workflow](../diagrams/agent-verification-implemented.svg)

Four Foundry specialists propose observations, commentary, editorial
checks and audience variants, but cannot grant themselves verification
or publisher privileges. A failed claim returns to the composer only
within bounded revision limits.

## Producer: distinct three states

1. **Domain logic tested:** digest-bound approval, CAS, audit, outbox,
   replay/stale revocation and PostgreSQL negative paths in disposable CI.
2. **Public demo:** browser-only D-031 approval and simulated delivery
   with timeout/retry, no network-side producer mutation.
3. **Real production:** trusted workforce actor, host-owned grant,
   signed step-up, independent real destination and owner approval
   are not active. The shipped BFF remains fail-closed.

Editing content, changing evidence or adapting language must require a
fresh check/version; a text field saying `verified` or `approved`
does not itself confer authority. See [issue #61](https://github.com/GOkwori/matchdesk/issues/61).

## Test qualification warning

The current integration [run 40129492295](https://github.com/GOkwori/matchdesk/actions/runs/40129492295)
passed **on attempt two**, following an actual colour-contrast failure
in the desktop tactical view on attempt one. Retain both attempts.
Automated axe checks do not substitute for [manual acceptance
issue #52](https://github.com/GOkwori/matchdesk/issues/52).
