# Client User Guide

## Purpose

This guide is for pharmacy staff using Pharma POS AI in daily work.

It is written for:
- admins
- managers
- cashiers

## What The System Does

The system is used to:
- log in staff by role
- sell products through POS
- manage product records
- receive stock in batches
- review sales history
- monitor stock and expiry status
- review backup and system health from `Settings`
- perform manager-approved sale refund or void workflows
- review end-of-day closeout totals

## User Roles

### Admin

Can:
- manage users
- view all modules
- manage products and stock
- configure operations
- review diagnostics and backup status
- approve refunds and voids
- review end-of-day closeout totals

### Manager

Can:
- manage products and stock
- use POS
- view sales and notifications
- manage cashier accounts where permitted
- run backups and review diagnostics
- void or refund sales with a reason
- review end-of-day closeout totals

### Cashier

Can:
- use POS
- view products
- view sales allowed to their role

## Daily Start

1. Start the system from the desktop shortcut or installed launcher.
2. Wait for the application to open.
3. Sign in with your username and password.
4. Confirm the correct pharmacy screen opens.

If login fails:
- check the username carefully
- check CAPS LOCK
- ask an admin to confirm the account is active

## POS Workflow

1. Open the `POS` page.
2. Search for a product by name, SKU, generic name, or barcode.
3. Click the product to add it to the sale.
4. Adjust quantity in the cart if needed.
5. Review the total in the checkout panel.
6. Enter customer details only if needed.
7. Choose payment method.
8. Complete the sale.
9. Print the receipt if required.

Notes:
- out-of-stock items cannot be added
- quarantined stock is not sold
- totals remain visible while building the sale

## Adding A New Product

Use the `Products` page.

When adding a new product:
- enter the product name
- enter or generate the SKU
- optionally enter barcode
- set dosage form
- set strength if the product has one
- enter pricing
- choose category
- optionally choose supplier
- optionally enter manufacturer

If you already have stock on hand, leave `Receive opening stock now` enabled and enter:
- batch number
- quantity
- expiry date
- optional manufacture date
- optional shelf location

If you only want to create the product record first, turn that option off.

## Receiving Stock For An Existing Product

Use the `Receive` action on the `Products` page.

Enter:
- batch number
- quantity received
- expiry date
- cost price
- optional updated selling price
- optional location

This is the correct workflow for adding stock to an existing product.

## Managing Batches

Use the `Batches` action on a product.

You can:
- review batch quantities
- review expiry dates
- update location
- quarantine a batch
- remove quarantine when resolved

Quarantined batches are excluded from sellable stock.

## Sales History

Use the `Sales` page to:
- review completed sales
- search past transactions
- confirm what was sold

Managers and admins should also use sales history when:
- checking invoice details
- investigating a transaction
- preparing to void or refund a completed sale

## Sale Void And Refund Control

Only managers or admins should reverse a completed sale.

Rules:
- a reason is required
- the reversal is audited
- stock is restored through the controlled workflow
- staff should not try to correct a bad sale by hiding it with manual stock edits

Recommended use:
- `Void` for an operator mistake caught the same day
- `Refund` when goods are returned and the transaction is being reversed for the customer

## Backups

Pharmacy staff should not need technical database knowledge.

Expected operating model:
- nightly backup runs automatically
- admin can check backup status
- admin can check local diagnostics
- support technician handles restore when needed

If your installation includes a backup shortcut or button:
- use `Back Up Now` before major updates
- report any backup failure immediately

## Diagnostics And Backup Status

Use the `Settings` page to review:
- database connection status
- backup health
- most recent backup time
- local diagnostics

Escalate immediately if:
- the latest backup is missing
- the backup is stale
- the database connection is shown as failed

## End Of Day Routine

Recommended daily close routine:

1. confirm all expected sales are present
2. review any refunded or voided sales
3. confirm any unusual stock issue is reported
4. check backup health in `Settings`
5. verify the system remains powered for scheduled backup, if that is your local policy
6. lock or sign out of the system

## When To Call Support

Call support or the system administrator if:
- the system does not start
- backup reports failure
- refunded or voided sales do not restore stock correctly
- products disappear unexpectedly
- totals look incorrect
- you cannot log in with a known active account
- restore is required after machine failure

## Important Notes

- do not share passwords
- do not edit database files manually
- do not delete backup files unless instructed by support
- do not continue selling if stock or totals appear obviously wrong
