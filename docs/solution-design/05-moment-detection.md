# Deterministic moment detection

Status: planned for Phase 1.

The required initial detectors are goal, big chance, momentum swing, pressing spell
and counter-attack goal. Card and substitution context extend the same evidence contract.

A detector receives the accepted event revision and an explicit period window. It
returns a moment type, triggering sequence, feature values, threshold configuration
version and evidence IDs. It never asks an LLM to count shots or identify the score.

A pressing spell uses a named proxy and a documented baseline. A substitution can
precede improved results without proving causation. Changing a seed must not force
an expected narrative; the detector must succeed because the generated events meet
the rule, with separate counterexamples that do not trigger.

Debounce keys include replay generation, team, moment type and window. A correction
recomputes affected moments and invalidates dependent evidence. Fault tests must
cover duplicates, out-of-order arrivals, missed sequence gaps and replay resets.
