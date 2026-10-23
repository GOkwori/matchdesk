// MatchDesk competition demo on Azure: the studio and the API on Container Apps.
//
// Smaller than main.bicep on purpose: no private network, database, Key Vault or sign-in, because
// the demo has none of them. The studio is the same image CI builds and scans; the API serves
// health and, when switched on, the Ask MatchDesk planner on Microsoft Foundry. The planner only
// reads a question into a query plan; the studio computes and verifies every answer.
//
// Two passes, run by .github/workflows/azure-demo.yml:
//   1. deployApps=false creates logs, the pull identity, the registry and the environment.
//   2. After the images are pushed, deployApps=true creates or updates both apps.
// Always preview with what-if first. Rollback: delete the resource group.

targetScope = 'resourceGroup'

@description('Azure region for every resource.')
param location string = 'uksouth'

@description('Short lowercase prefix for resource names.')
@minLength(3)
@maxLength(12)
param namePrefix string = 'mdesk'

@description('Create or update the two container apps. False on the first pass, before images exist.')
param deployApps bool = false

@description('Studio image in this registry, e.g. <registry>.azurecr.io/matchdesk-web:<git-sha>.')
param webImage string = ''

@description('API image in this registry, e.g. <registry>.azurecr.io/matchdesk-api:<git-sha>.')
param apiImage string = ''

@description('Switch on Microsoft Foundry (tier 2): the Ask MatchDesk planner and live, rate-limited agent runs.')
param assistantEnabled bool = false

@description('Microsoft Foundry project endpoint used by the planner. Not a secret.')
param foundryProjectEndpoint string = ''

@description('Microsoft Foundry model deployment name used by the planner.')
param foundryModel string = ''

@description('Addresses for budget alerts. Empty skips the budget.')
param budgetContactEmails array = []

@description('Monthly budget for the resource group, in the billing currency.')
param monthlyBudget int = 25

@description('Budget start date: the first day of a month, yyyy-MM-01.')
param budgetStartDate string = '2026-10-01'

@description('Daily log ingestion cap in GB; ingestion stops for the day when reached.')
param logDailyCapGb string = '0.1'

var suffix = uniqueString(resourceGroup().id)
var names = {
  logs: '${namePrefix}-demo-logs'
  identity: '${namePrefix}-demo-id'
  registry: take('${namePrefix}demo${suffix}', 50)
  environment: '${namePrefix}-demo-env'
  api: '${namePrefix}-api'
  web: '${namePrefix}-web'
  insights: '${namePrefix}-demo-insights'
}

// ---------- Logs, capped so a noisy app cannot run up cost ----------
resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: names.logs
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
    workspaceCapping: { dailyQuotaGb: json(logDailyCapGb) }
  }
}

// ---------- One identity: pulls images, and (tier 2) calls Foundry. No keys anywhere ----------
// Application Insights on the same workspace: traces and metrics from the API's planner,
// live agent runs (Agent Framework's generative-AI spans included) and live replay streams.
resource insights 'Microsoft.Insights/components@2020-02-02' = {
  name: names.insights
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logs.id
    IngestionMode: 'LogAnalytics'
    RetentionInDays: 30
  }
}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: names.identity
  location: location
}

// ---------- Registry: admin user off, pulls by managed identity ----------
resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: names.registry
  location: location
  sku: { name: 'Basic' }
  properties: { adminUserEnabled: false }
}

var registryPullRole = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
resource registryPull 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(registry.id, identity.id, registryPullRole)
  scope: registry
  properties: {
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', registryPullRole)
  }
}

// ---------- Container Apps environment: Consumption, public ----------
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
  }
}

// The API is internal: only the studio, inside the environment, can reach it. The studio calls
// it as http://<api app name>, so plain HTTP is allowed on this internal-only ingress.
resource api 'Microsoft.App/containerApps@2024-03-01' = if (deployApps) {
  name: names.api
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${identity.id}': {} } }
  properties: {
    environmentId: environment.id
    configuration: {
      ingress: { external: false, targetPort: 8000, transport: 'http', allowInsecure: true }
      registries: [ { server: registry.properties.loginServer, identity: identity.id } ]
      secrets: [ { name: 'appinsights-connection', value: insights.properties.ConnectionString } ]
    }
    template: {
      containers: [
        {
          name: 'api'
          image: apiImage
          resources: { cpu: json('0.5'), memory: '1Gi' }
          env: [
            // DefaultAzureCredential picks this identity for Foundry.
            { name: 'AZURE_CLIENT_ID', value: identity.properties.clientId }
            { name: 'MATCHDESK_FOUNDRY_ENABLED', value: assistantEnabled ? 'true' : 'false' }
            { name: 'MATCHDESK_LIVE_AGENTS_ENABLED', value: assistantEnabled ? 'true' : 'false' }
            { name: 'MATCHDESK_ASSISTANT_FOUNDRY_ENABLED', value: assistantEnabled ? 'true' : 'false' }
            { name: 'MATCHDESK_LIVE_REPLAY_ENABLED', value: 'true' }
            { name: 'MATCHDESK_MCP_ENABLED', value: 'true' }
            { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', secretRef: 'appinsights-connection' }
            { name: 'FOUNDRY_PROJECT_ENDPOINT', value: foundryProjectEndpoint }
            { name: 'FOUNDRY_MODEL', value: foundryModel }
          ]
          probes: [
            { type: 'Liveness', httpGet: { path: '/api/health', port: 8000 }, periodSeconds: 30 }
            { type: 'Readiness', httpGet: { path: '/api/health', port: 8000 }, periodSeconds: 10 }
          ]
        }
      ]
      // One warm replica: no cold start for judges, and the planner's per-replica call caps
      // (20 a minute, 400 a day) are also the totals.
      scale: { minReplicas: 1, maxReplicas: 1 }
    }
  }
  dependsOn: [ registryPull ]
}

resource web 'Microsoft.App/containerApps@2024-03-01' = if (deployApps) {
  name: names.web
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${identity.id}': {} } }
  properties: {
    environmentId: environment.id
    configuration: {
      ingress: { external: true, targetPort: 3000, transport: 'http', allowInsecure: false }
      registries: [ { server: registry.properties.loginServer, identity: identity.id } ]
    }
    template: {
      containers: [
        {
          name: 'web'
          image: webImage
          resources: { cpu: json('0.5'), memory: '1Gi' }
          probes: [
            { type: 'Readiness', httpGet: { path: '/', port: 3000 }, periodSeconds: 10 }
          ]
        }
      ]
      // Always warm, so the first judge never waits for a cold start; a second replica under load.
      scale: { minReplicas: 1, maxReplicas: 2 }
    }
  }
  dependsOn: [ registryPull, api ]
}

// ---------- Budget: email at 50%, 80% and a forecast of 100% ----------
resource budget 'Microsoft.Consumption/budgets@2023-11-01' = if (!empty(budgetContactEmails)) {
  name: '${namePrefix}-demo-monthly'
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

output registryLoginServer string = registry.properties.loginServer
output registryName string = registry.name
output environmentDefaultDomain string = environment.properties.defaultDomain
output webAppName string = names.web
output apiAppName string = names.api
output webUrl string = 'https://${names.web}.${environment.properties.defaultDomain}'
output identityPrincipalId string = identity.properties.principalId
output identityClientId string = identity.properties.clientId
output insightsName string = insights.name
