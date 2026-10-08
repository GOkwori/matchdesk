# Evidence index

Dated subdirectories contain actual local commands, JUnit/coverage results, source-file
hashes, environment metadata and gate status. The `latest.json` pointer identifies the
latest completed collection without erasing prior attempts.

Early attempt logs are retained under `initial-attempts`; those runs preceded the final
local source commit and are not attributed to it. The source-bound qualification run
is recorded separately. No hosted CI, frontend build, cloud deployment, live model
execution or production certification is implied by these local results.
