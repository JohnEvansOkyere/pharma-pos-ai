# User And Operator Workflows

## Roles

Current roles:

- admin
- manager
- cashier

Admins have all default permissions. Managers have operational management permissions. Cashiers have minimal defaults.

## Granular Permissions

Permission flags include:

- manage products
- manage suppliers
- manage categories
- manage users
- view reports
- void sale
- refund sale
- adjust stock
- perform stock take
- trigger backup

Explicit user permissions override role defaults when present.

## Cashier Workflows

Cashiers primarily use:

- POS
- sales visibility as allowed
- product lookup
- notifications

Sensitive reversals and stock changes should not be cashier-owned without explicit permission.

## Manager Workflows

Managers use:

- cloud dashboard
- reports
- stock adjustments
- stock takes
- backup visibility/settings where permission allows
- sale reversals where permission allows

## Admin Workflows

Admins use:

- user management
- audit logs
- cloud reconciliation repair
- AI provider policy
- delivery settings
- diagnostics
- sensitive operational controls

## Provisioning Rule

Public self-registration must not exist in release builds. Users should be provisioned by an admin-controlled workflow or installer provisioning script.
