# Customer Retention and Sale Ownership

Registered customers are operational records owned by one pharmacy
organization and one branch. A POS sale may link a customer only when all of
the following are true:

- the cashier has an organization and branch assignment;
- the customer belongs to the same organization;
- the customer belongs to the same branch;
- the customer is active.

The backend enforces this in `create_sale()` before product rows are locked or
stock is changed. Invalid, inactive, or out-of-scope customer IDs return the
same not-found response so the API does not disclose customer records from
another scope.

Receipt dispatch and health follow-up scheduling use the customer object that
passed this validation. They remain non-fatal post-sale actions: a messaging
provider failure cannot roll back a completed sale.

This rule is independent of deployment topology. Dedicated databases remove
cross-pharmacy operational queries, but branch ownership still has to be
enforced inside each pharmacy deployment.
