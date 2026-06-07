# Tenancy And Branch Scope

## Model

The product is moving from a single-branch local system toward a scalable multi-client, multi-branch architecture.

Terms:

- organization: one pharmacy client/business tenant
- branch: one physical pharmacy location
- device: one installed local server, till, or workstation identity

## Scope Columns

Many newer tables include:

- `organization_id`
- `branch_id`
- `source_device_id`

Older local tables may still have nullable tenant columns because the product started as a local single-installation system. Production cloud work should continue moving critical rows toward explicit tenant and branch scope.

## Access Rules

Application-level rule:

- users assigned to an organization can access only that organization
- branch-assigned users are scoped to that branch
- role permissions do not expand data scope: a branch-assigned admin remains branch-restricted
- organization-level admins use an organization assignment with no branch and can access all branches in that organization
- organization-unscoped users are rejected from `online_pos` operational queries
- report access requires report permission
- repair and audit operations require admin role

The shared `scope_query_to_user()` helper applies this policy to operational
sales, products, batches, stock adjustments, stock takes, customers, users,
and dashboard aggregates. Direct object access and aggregate reporting use the
same rule, so guessing another branch's row ID cannot bypass list filtering.

## Frontend Scope

The Cloud Dashboard uses the current user organization and selected branch scope. If a user is assigned to a branch, branch scope is forced to that branch.

## Cloud Scope

Cloud reporting tables are scoped by organization and branch. All queries should filter by organization, and branch filters should be applied for branch-level views.

## Tenant Safety Practices

Use these rules for all future work:

- every cloud query must include `organization_id`
- branch-specific views must include `branch_id`
- use `scope_query_to_user()` instead of duplicating endpoint-specific filters
- never trust frontend-sent organization or branch id without checking the authenticated user
- avoid global admin behavior unless it is explicitly a platform operation
- audit sensitive tenant-scoped changes with organization and branch ids
- prefer unique constraints that include organization/branch scope for cloud snapshots
