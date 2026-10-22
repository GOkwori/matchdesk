// Example parameters. Replace every placeholder before a what-if; never commit real e-mail lists or IDs
// that you would rather keep private.
using './main.bicep'

param location = 'uksouth'
param namePrefix = 'mdesk'
param postgresAdminGroupObjectId = '00000000-0000-0000-0000-000000000000'
param postgresAdminGroupName = 'MatchDesk PostgreSQL admins'
param monthlyBudget = 40
param budgetContactEmails = [ 'owner@example.com' ]
param budgetStartDate = '2026-11-01'
param logDailyCapGb = '0.1'
