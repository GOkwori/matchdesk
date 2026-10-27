# Infrastructure and deployment

Status (26 October 2026): the competition demo is deployed in Azure Container Apps in UK South. A public Next.js studio reaches an internal-only FastAPI app through same-origin `/api`; images are stored in Azure Container Registry and pulled using a managed identity. Application Insights and Log Analytics provide observability. See the [actual demo runbook](../operations/azure-demo.md), [deployment record](../evidence/azure-deployment-20261023.md) and [live checks](../evidence/release-live-checks-20261023.md). The separate [Azure deployment plan](../operations/azure-deployment-plan.md) describes broader proposed production infrastructure.

Compose proposes PostgreSQL 16, a Python 3.12 API and Node 22 web application. Only
loopback API/web ports are published. The database has no host port. Local credentials
are generated into an ignored file with exclusive creation and restricted permissions.
The public demo does not provide production-grade authenticated persistence or external publishing. Disposable PostgreSQL integration tests cover the producer domain, but running local containers alone does not certify production persistence or identity.

Container Apps, Container Registry, a managed identity, Microsoft Foundry access and telemetry are part of the current Azure demo. PostgreSQL Flexible Server, private networking, real producer sign-in, privileged publication and production recovery remain future work. The demo uses GitHub Actions OIDC for deployments, with owner-reviewed cost and rollback controls.
No account email is treated as a tenant or subscription identifier.

Docker builds require reviewed dependency locks. Base image digest pinning, non-root
production images, SBOMs and vulnerability scans remain gates. The image used for the public studio is built and qualified by the Azure demo workflow; it is not certification of an enterprise production deployment.
