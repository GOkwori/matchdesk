# Dependency advisory audit: release blocked

Tested source: `15996afa3219020c44dc1ff8f353e87d93e921e6`.
[GitHub run 37755579414](https://github.com/GOkwori/matchdesk/actions/runs/37755579414),
attempt 1: **FAIL**. The Python scanner executed and returned known-advisory findings;
this was not a package-resolution failure. Application and browser-harness npm audits passed.

Artifact 11539138855 was downloaded and verified against SHA-256
`add81776d8553227744a95a6b79d1fae475b751802b6d00832dcdc1d2d09bee8`.
Its recorded source matches the source above. Raw scanner output is preserved in the
artifact, including repeated advisory entries. The table below deduplicates by advisory
ID within each package: **eight distinct IDs across three affected packages**.

## Findings reported by pip-audit 2.10.1

All 35 locked registry packages, including test/quality dependencies, were inspected.
The local virtual project is not a registry package and was explicitly excluded.

| Package | Locked version | Advisory ID | Fixed version reported by scanner |
|---|---|---|---|
| anyio | 4.13.0 | PYSEC-2026-4024 | 4.14.2 |
| anyio | 4.13.0 | PYSEC-2026-4025 | 4.14.2 |
| pytest | 9.0.2 | PYSEC-2026-1845 | 9.0.3 |
| starlette | 0.50.0 | PYSEC-2026-161 | 1.0.1 |
| starlette | 0.50.0 | PYSEC-2026-2281 | 1.1.0 |
| starlette | 0.50.0 | PYSEC-2026-2280 | 1.1.0 |
| starlette | 0.50.0 | PYSEC-2026-248 | 1.3.0 |
| starlette | 0.50.0 | PYSEC-2026-249 | 1.3.1 |

Fixed versions are scanner metadata, not yet tested MatchDesk upgrade recommendations.
A coherent FastAPI/Starlette/AnyIO combination must be resolved and qualified, rather
than forcibly overriding a transitive dependency. Pytest is development tooling, but
its finding remains in the gate. Presence of an advisory is not a demonstrated exploit
against this particular application, and no findings have been waived on that basis.

The existing AnyIO compatibility pin restored functional tests; this later audit shows
that functional compatibility alone was insufficient. The historical compatibility
results remain genuine for their measured scope, but do not certify dependency security.

## JavaScript findings

The application npm lock and isolated browser-test npm lock both reported zero known
vulnerabilities at execution time. Audits used a low-severity failure threshold and
included development dependencies. A clean advisory response is not proof of absence
of vulnerabilities, nor an audit of native/OS libraries in container images.

## Required remediation and retesting

Resolve supported patched versions with genuine lockfiles and record the compatibility
decision. Retain warnings-as-errors, strict types, schema drift checks, numerical and
boolean boundary regressions, all 24 browser cases and all nine runtime groups. Rerun
Foundation CI, Foundation integration and Dependency audit against the same candidate
source. Do not use ignored-advisory lists, `audit fix --force`, warning suppression or
an exemption merely to obtain a passing status.

Native image scanning, secret scanning, static application security analysis and
repository protections remain independent outstanding gates. The production release
and Phase 0 approval remain blocked; no resources have been deployed to Azure.
