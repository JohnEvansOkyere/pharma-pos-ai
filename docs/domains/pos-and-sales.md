# POS And Sales

## Purpose

The POS route is the most important operator workflow. It must stay fast, predictable, and safe.

## Current Capabilities

- product search by name/SKU/barcode
- paginated catalog responses for POS and product management include retail and wholesale prices
- cart workflow
- retail and wholesale pricing mode support
- backend sale total calculation
- payment method capture
- customer and prescription metadata fields
- batch-aware sale items
- FEFO stock deduction
- sale history
- sale summaries
- void and refund workflow
- end-of-day closeout totals

## Sale Safety

Sale creation validates:

- product exists
- product is active
- sellable stock is available
- valid batch allocation exists
- wholesale price exists when wholesale pricing is selected

The backend locks rows and performs stock reduction inside a transaction.

## Sale Reversal

Voids and refunds:

- require specific permissions
- require a reason
- restore stock
- create a reversal record
- update sale status
- record inventory movements
- write sync event
- write audit log

## Pharmaceutical Metadata

Products include:

- dosage form
- strength
- generic name
- active ingredient
- manufacturer
- prescription status
- controlled/narcotic flags
- ID requirement flag
- storage conditions
- usage/side effect/contraindication text

Sales include:

- prescription number
- doctor name
- has prescription flag
- customer ID number

## Important Remaining Hardening

The schema supports prescription and controlled-drug metadata, but deeper server-side enforcement should still be added.

Examples:

- block prescription-required products unless prescription fields are present
- require customer ID where `requires_id=true`
- require stronger audit for controlled/narcotic sale attempts
- optionally require manager override with reason for certain products
