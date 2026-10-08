# ADR-0006: Built foundation containers and revision-bound browser results

Date: 8 October 2026. Status: implemented for qualification, not a release approval.

## Context and decision

I want the foundation checks to exercise the same built application that a visitor
would run, rather than only a development server or an in-process API test client.
The local topology therefore uses standalone Next.js and a minimal Python runtime,
immutable base-image digests, committed dependency locks and non-root processes.
The API and web use read-only filesystems, no-new-privileges and dropped capabilities.
Only loopback ports are published; PostgreSQL stays on the Compose network.

The standalone web build compiles the non-secret API upstream into Next rewrites.
The upstream must be supplied when building for another topology. This foundation
choice does not claim that a runtime-configurable authenticated production BFF exists.

## Browser correctness

Source review identified a race: editing the input cleared an existing result, but a
pending response could later display acceptance for the previous text. A monotonically
increasing local input revision now binds success and error rendering to the submitted
revision. Editing invalidates the pending result without presenting the new text as
accepted. The browser suite controls delivery of a real HTTP response to test this
ordering, then validates the new text normally. This is a controlled transport test,
not evidence of a spontaneous service failure or an implemented publication verifier.

## Evidence and limits

The [integration method](../testing/integration-foundation.md) defines the assertions
and the safe disposable database scope. Runtime/browser results must identify their
exact source before this decision is described as qualified. Database probes test the
PostgreSQL topology, transactions and restart durability; application persistence,
SQLAlchemy migrations, distributed replay and production disaster recovery remain open.
Screenshots are retained for inspection, not automatically approved as visual baselines.
