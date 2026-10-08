# Locked dependency advisory audits

The Dependency audit workflow reads the committed Python, web and browser-harness
lockfiles. It does not run `audit fix`, update package versions, ignore advisories,
use production credentials or alter Git refs. All reported vulnerabilities fail the
corresponding gate; network failures are also failures, not clean audit results.

Python uses pip-audit 2.10.1, verified against the upstream release on 8 October 2026.
The scanner runs in an isolated temporary virtual environment, whose actual package
versions are retained. Its own transitive tooling dependencies are not a separately
locked application runtime. Every registry package in `uv.lock`, including test and
quality tooling, is audited using fully pinned and hashed input without invoking pip
to resolve the application's dependencies. The virtual local project is not a PyPI
package and is excluded explicitly. JavaScript audits cover the two committed npm
locks separately and fail at low severity or above. Source hashes and the audit start
time are retained with JSON outputs, including failed runs.

These checks compare resolved package versions with known advisory data at execution
time. They do not prove that code is vulnerability-free. Native/OS image scanning,
secret scanning, static application analysis, browser accessibility and production
identity/authorization qualification are separate outstanding gates. Immutable image
digests establish identity, not security. Package names and versions from this public
repository are sent to the configured public advisory services; no credentials or
private application data are part of the audit input.

A dependency change requires fresh functional, browser and audit qualification.
Historical clean scans must not be reused to certify a different source or lockfile.
