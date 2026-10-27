// MatchDesk on Azure: API and web on Container Apps, private PostgreSQL, Key Vault, logs and a budget.
//
// PLAN ONLY. Nothing here has been deployed. Deploy only after the owner approves
// docs/operations/azure-deployment-plan.md, and always run a what-if first:
//   az deployment group what-if -g <rg> -f infra/azure/main.bicep -p infra/azure/main.bicepparam
//
// Scope: one resource group. Region default: UK South.

targetScope = 'resourceGroup'

@description('Azure region for every resource.')
param location string = 'uksouth'

@description('Short lowercase prefix for resource names, e.g. "mdesk".')
@minLength(3)
@maxLength(12)
param namePrefix string = 'mdesk'

@description('API container image, e.g. <registry>.azurecr.io/matchdesk-api:<git-sha>. Leave the default for a first deploy before any image is pushed.')
param apiImage string = 'mcr.microsoft.com/k8se/quickstart:latest'

@description('Web container image, e.g. <registry>.azurecr.io/matchdesk-web:<git-sha>.')
param webImage string = 'mcr.microsoft.com/k8se/quickstart:latest'

@description('Object ID of the Entra group that administers PostgreSQL (owner group, not a person).')
param postgresAdminGroupObjectId string

@description('Display name of that Entra group.')
param postgresAdminGroupName string

@description('Monthly budget for the resource group, in the billing currency.')
param monthlyBudget int = 40

@description('Addresses that receive budget alerts.')
param budgetContactEmails array

@description('Budget start date: the first day of a month, yyyy-MM-01.')
param budgetStartDate string

@description('Daily log ingestion cap in GB; ingestion stops for the day when reached.')
param logDailyCapGb string = '0.1'

var suffix = uniqueString(resourceGroup().id)
var names = {
  logs: '${namePrefix}-logs'
  vnet: '${namePrefix}-vnet'
  identity: '${namePrefix}-api-id'
  vault: take('${namePrefix}kv${suffix}', 24)
  registry: take('${namePrefix}acr${suffix}', 50)
  postgres: '${namePrefix}-pg-${suffix}'
  environment: '${namePrefix}-env'
  api: '${namePrefix}-api'
  web: '${namePrefix}-web'
}

// ---------- Logs: capped so a noisy service cannot run up cost ----------
resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: names.logs
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
    workspaceCapping: { dailyQuotaGb: json(logDailyCapGb) }
  }
}

// ---------- Network: Container Apps and PostgreSQL share a private VNet ----------
resource vnet 'Microsoft.Network/virtualNetworks@2024-01-01' = {
  name: names.vnet
  location: location
  properties: {
    addressSpace: { addressPrefixes: [ '10.40.0.0/16' ] }
    subnets: [
      {
        name: 'apps'
        properties: {
          addressPrefix: '10.40.0.0/23'
          delegations: [ { name: 'apps', properties: { serviceName: 'Microsoft.App/environments' } } ]
        }
      }
      {
        name: 'postgres'
        properties: {
          addressPrefix: '10.40.2.0/28'
          delegations: [ { name: 'postgres', properties: { serviceName: 'Microsoft.DBforPostgreSQL/flexibleServers' } } ]
        }
      }
    ]
  }
}

resource postgresDns 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: 'privatelink.postgres.database.azure.com'
  location: 'global'
}

resource postgresDnsLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  parent: postgresDns
  name: '${names.vnet}-link'
  location: 'global'
  properties: { registrationEnabled: false, virtualNetwork: { id: vnet.id } }
}

// ---------- Identity used by the API: no passwords anywhere ----------
resource apiIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: names.identity
  location: location
}

// ---------- Key Vault: RBAC only, purge protection on ----------
resource vault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: names.vault
  location: location
  properties: {
    tenantId: subscription().tenantId
    sku: { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 30
    enablePurgeProtection: true
    // Public endpoint with RBAC; a private endpoint would add a monthly charge.
    // The plan records this trade-off for the owner.
    publicNetworkAccess: 'Enabled'
  }
}

var vaultReaderRole = '4633458b-17de-408a-b874-0445c86b69e6'
resource vaultReader 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(vault.id, apiIdentity.id, vaultReaderRole)
  scope: vault
  properties: {
    principalId: apiIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', vaultReaderRole)
  }
}

// ---------- Container registry: admin user off, pulls by managed identity ----------
resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: names.registry
  location: location
  sku: { name: 'Basic' }
  properties: { adminUserEnabled: false }
}

var registryPullRole = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
resource registryPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, apiIdentity.id, registryPullRole)
  scope: registry
  properties: {
    principalId: apiIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', registryPullRole)
  }
}

// ---------- PostgreSQL 16: private access, Entra authentication only ----------
resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2022-12-01' = {
  name: names.postgres
  location: location
  sku: { name: 'Standard_B1ms', tier: 'Burstable' }
  properties: {
    version: '16'
    storage: { storageSizeGB: 32 }
    backup: { backupRetentionDays: 7, geoRedundantBackup: 'Disabled' }
    highAvailability: { mode: 'Disabled' }
    // A delegated subnet means private access: the server has no public endpoint.
    network: {
      delegatedSubnetResourceId: vnet.properties.subnets[1].id
      privateDnsZoneArmResourceId: postgresDns.id
    }
    authConfig: {
      activeDirectoryAuth: 'Enabled'
      passwordAuth: 'Disabled'
      tenantId: subscription().tenantId
    }
  }
  dependsOn: [ postgresDnsLink ]
}

resource postgresAdmin 'Microsoft.DBforPostgreSQL/flexibleServers/administrators@2022-12-01' = {
  parent: postgres
  name: postgresAdminGroupObjectId
  properties: {
    principalType: 'Group'
    principalName: postgresAdminGroupName
    tenantId: subscription().tenantId
  }
}

resource database 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2022-12-01' = {
  parent: postgres
  name: 'matchdesk'
}

// ---------- Container Apps: both scale to zero ----------
resource environment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: names.environment
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
    vnetConfiguration: { infrastructureSubnetId: vnet.properties.subnets[0].id, internal: false }
    workloadProfiles: [ { name: 'Consumption', workloadProfileType: 'Consumption' } ]
  }
}

// The API is internal: only the web app inside the environment can reach it.
resource api 'Microsoft.App/containerApps@2024-03-01' = {
  name: names.api
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${apiIdentity.id}': {} } }
  properties: {
    environmentId: environment.id
    workloadProfileName: 'Consumption'
    configuration: {
      ingress: { external: false, targetPort: 8000, transport: 'http', allowInsecure: false }
      registries: [ { server: registry.properties.loginServer, identity: apiIdentity.id } ]
    }
    template: {
      containers: [
        {
          name: 'api'
          image: apiImage
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: [
            { name: 'AZURE_CLIENT_ID', value: apiIdentity.properties.clientId }
            { name: 'MATCHDESK_POSTGRES_HOST', value: postgres.properties.fullyQualifiedDomainName }
            { name: 'MATCHDESK_POSTGRES_DATABASE', value: database.name }
            { name: 'MATCHDESK_KEY_VAULT_URI', value: vault.properties.vaultUri }
            // Live agents stay off until the owner approves on-demand model spend.
            { name: 'MATCHDESK_FOUNDRY_ENABLED', value: 'false' }
            { name: 'MATCHDESK_ASSISTANT_FOUNDRY_ENABLED', value: 'false' }
          ]
          probes: [
            { type: 'Liveness', httpGet: { path: '/api/health', port: 8000 }, periodSeconds: 30 }
          ]
        }
      ]
      scale: { minReplicas: 0, maxReplicas: 2 }
    }
  }
  dependsOn: [ registryPull, vaultReader ]
}

resource web 'Microsoft.App/containerApps@2024-03-01' = {
  name: names.web
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${apiIdentity.id}': {} } }
  properties: {
    environmentId: environment.id
    workloadProfileName: 'Consumption'
    configuration: {
      ingress: { external: true, targetPort: 3000, transport: 'http', allowInsecure: false }
      registries: [ { server: registry.properties.loginServer, identity: apiIdentity.id } ]
    }
    template: {
      containers: [
        {
          name: 'web'
          image: webImage
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: [
            // Server-side only: the browser never receives this address.
            { name: 'MATCHDESK_API_ORIGIN', value: 'https://${api.properties.configuration.ingress.fqdn}' }
          ]
        }
      ]
      scale: { minReplicas: 0, maxReplicas: 3 }
    }
  }
  dependsOn: [ registryPull ]
}

// ---------- Budget: email at 50%, 80% and 100% of the monthly amount ----------
resource budget 'Microsoft.Consumption/budgets@2023-11-01' = {
  name: '${namePrefix}-monthly'
  properties: {
    category: 'Cost'
    amount: monthlyBudget
    timeGrain: 'Monthly'
    timePeriod: { startDate: budgetStartDate }
    notifications: {
      half: { enabled: true, operator: 'GreaterThanOrEqualTo', threshold: 50, contactEmails: budgetContactEmails, thresholdType: 'Actual' }
      most: { enabled: true, operator: 'GreaterThanOrEqualTo', threshold: 80, contactEmails: budgetContactEmails, thresholdType: 'Actual' }
      over: { enabled: true, operator: 'GreaterThanOrEqualTo', threshold: 100, contactEmails: budgetContactEmails, thresholdType: 'Forecasted' }
    }
  }
}

output webUrl string = 'https://${web.properties.configuration.ingress.fqdn}'
output registryLoginServer string = registry.properties.loginServer
output apiIdentityClientId string = apiIdentity.properties.clientId
output postgresHost string = postgres.properties.fullyQualifiedDomainName
output keyVaultUri string = vault.properties.vaultUri
