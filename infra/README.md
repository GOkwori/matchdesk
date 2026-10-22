# Infrastructure status

`azure/` holds the proposed Azure deployment: Bicep for Container Apps, PostgreSQL Flexible Server,
Key Vault, a container registry, capped logs and a budget, plus a script for producer sign-in in
Entra ID. **Nothing has been provisioned.** Read the
[Azure deployment plan](../docs/operations/azure-deployment-plan.md) first; deployment needs the
owner's approval.

The local Compose definition is at the repository root.

See [infrastructure design](../docs/solution-design/10-infrastructure.md).
