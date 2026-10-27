#!/usr/bin/env bash
# Workforce (producer) sign-in for MatchDesk in the owner's Entra ID tenant.
#
# PLAN ONLY: run this yourself, signed in with `az login` to the tenant that will host producers,
# after approving docs/operations/azure-deployment-plan.md. It creates directory objects (no Azure
# resources and no charges), and it prints the IDs the web app needs. It never prints a secret.
#
# Matches apps/web/src/workforce: OIDC code + PKCE, callback /api/workforce/oidc/callback, an ID token
# for the studio app, an access token for a separate producer API, and step-up through an
# authentication context (the `acrs` claim) before approve or reject.
#
# Usage: WEB_ORIGIN=https://<your web app> ./infra/azure/entra-workforce.sh
set -euo pipefail

: "${WEB_ORIGIN:?Set WEB_ORIGIN to the deployed web app origin, e.g. https://mdesk-web.<region>.azurecontainerapps.io}"
case "$WEB_ORIGIN" in https://*) ;; *) echo "WEB_ORIGIN must be https" >&2; exit 1 ;; esac

TENANT_ID=$(az account show --query tenantId -o tsv)

# 1. The producer API: exposes one delegated scope, issues v2 access tokens.
API_APP_ID=$(az ad app create --display-name "MatchDesk Producer API" \
  --sign-in-audience AzureADMyOrg --query appId -o tsv)
az ad app update --id "$API_APP_ID" --identifier-uris "api://$API_APP_ID" \
  --set api.requestedAccessTokenVersion=2
SCOPE_ID=$(python3 -c 'import uuid; print(uuid.uuid4())')
az ad app update --id "$API_APP_ID" --set "api.oauth2PermissionScopes=[{
  \"id\": \"$SCOPE_ID\", \"value\": \"producer.decide\", \"type\": \"User\", \"isEnabled\": true,
  \"adminConsentDisplayName\": \"Decide on MatchDesk drafts\",
  \"adminConsentDescription\": \"Lets the MatchDesk studio submit a producer decision on the signed-in user's behalf.\",
  \"userConsentDisplayName\": \"Decide on MatchDesk drafts\",
  \"userConsentDescription\": \"Submit producer decisions in MatchDesk as you.\"}]"
az ad sp create --id "$API_APP_ID" >/dev/null

# 2. The studio web app: confidential client, signs in with a certificate (added in step 4), no secret.
WEB_APP_ID=$(az ad app create --display-name "MatchDesk Producer Studio" \
  --sign-in-audience AzureADMyOrg \
  --web-redirect-uris "$WEB_ORIGIN/api/workforce/oidc/callback" \
  --enable-id-token-issuance false --query appId -o tsv)
az ad app permission add --id "$WEB_APP_ID" --api "$API_APP_ID" --api-permissions "$SCOPE_ID=Scope"
WEB_SP=$(az ad sp create --id "$WEB_APP_ID" --query id -o tsv)
# Only members of the producer group may sign in at all.
az ad sp update --id "$WEB_SP" --set appRoleAssignmentRequired=true

# 3. The producer group: membership is the only way to be a producer.
GROUP_ID=$(az ad group create --display-name "MatchDesk producers" \
  --mail-nickname matchdesk-producers --query id -o tsv)
az rest --method POST \
  --url "https://graph.microsoft.com/v1.0/servicePrincipals/$WEB_SP/appRoleAssignedTo" \
  --body "{\"principalId\":\"$GROUP_ID\",\"resourceId\":\"$WEB_SP\",\"appRoleId\":\"00000000-0000-0000-0000-000000000000\"}" >/dev/null

cat <<EOF

Created (no secrets printed):
  Tenant ID ............ $TENANT_ID
  Studio app (client) .. $WEB_APP_ID
  Producer API app ..... $API_APP_ID   scope: api://$API_APP_ID/producer.decide
  Producer group ....... $GROUP_ID     (add producers to this group)

Still to do by hand (see docs/operations/azure-deployment-plan.md):
  4. Create a certificate in Key Vault and upload its public part to the studio app
     (Certificates & secrets). The web app signs client assertions with it; no client secret.
  5. Grant admin consent for the studio app's producer.decide permission.
  6. Authentication context: Entra ID > Protection > Conditional Access > Authentication contexts,
     add c1 "MatchDesk producer decision"; then a Conditional Access policy targeting c1 that
     requires MFA. Conditional Access needs Microsoft Entra ID P1.
EOF
