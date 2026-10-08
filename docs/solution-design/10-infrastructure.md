# Infrastructure and deployment

Status: local Compose files authored, unexecuted; Azure resources not provisioned.

Compose proposes PostgreSQL 16, a Python 3.12 API and Node 22 web application. Only
loopback API/web ports are published. The database has no host port. Local credentials
are generated into an ignored file with exclusive creation and restricted permissions.
The API does not yet use the database; starting both containers is not an integration test.

Container Apps, PostgreSQL Flexible Server, Foundry and telemetry are proposed cloud
components. Resource/region/model availability, identities, private networking, migration
execution, OIDC trust, costs and rollback must be discovered and qualified before use.
No account email is treated as a tenant or subscription identifier.

Docker builds require reviewed dependency locks. Base image digest pinning, non-root
production images, SBOMs and vulnerability scans remain gates. The frontend Dockerfile
is explicitly a development image, not a production deployment image.
