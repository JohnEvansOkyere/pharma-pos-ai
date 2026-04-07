# Offline Deployment Strategy For Real Pharmacy Use

## Purpose

This document explains the recommended production direction for this system if it is to be sold to pharmacies in Ghana.

The goal is not to build a fancy hospital-grade workflow system. The goal is to build a reliable pharmacy business tool that:

- works without internet
- tracks stock and expiry properly
- helps prevent out-of-stock and dead stock
- is simple enough for attendants to use every day
- can be installed and supported for real clients

## Executive Recommendation

This system should be built as:

- **offline from the internet**
- **online inside the pharmacy's local network when needed**

That means:

- the system should not depend on cloud connectivity
- the pharmacy can continue operating even when internet is down
- one machine in the shop acts as the local server
- other machines in the same shop can connect over LAN if needed

This is the most practical model for Ghana.

## What "Offline" Should Mean Here

There are two different meanings of offline:

### 1. Internet-offline

The pharmacy can work without internet.

This is the recommended model.

### 2. Fully standalone on every machine

Each machine works independently and later syncs with others.

This is much more complex and is not the right first production path for this project.

## Recommended Architecture

### Best production model

Use a **local on-premise deployment**:

- one Windows PC in the pharmacy acts as the main local server
- backend runs locally on that machine
- database runs locally on that machine
- frontend is opened locally on that machine or from other PCs through the shop network
- no internet is required for daily operation

This gives you:

- simple support model
- one source of truth for stock
- proper multi-user control
- easier backup and restore

## Database Recommendation

### Recommended for production: PostgreSQL

Use PostgreSQL for real client deployments.

Reason:

- better reliability than SQLite for concurrent use
- safer for multiple tills or users
- stronger transactional behavior
- better recovery options
- better long-term data integrity

### When SQLite is acceptable

SQLite is acceptable only for:

- development
- demos
- very small single-machine pilot installs

I do **not** recommend SQLite as the standard database for paying pharmacy clients if there may be:

- multiple users
- a cashier and owner using the system together
- stock operations during active sales
- long-term business dependence on the system

### Final database decision

- **Single-terminal only, very small shop:** SQLite can work, but still not my preferred default
- **Real pharmacy deployment:** PostgreSQL should be the default

## Why PostgreSQL Is Better For This Business

Your biggest business problems are:

- expiry losses
- out-of-stock losses
- stock accuracy
- dependable sales records

Those problems depend on trustworthy data.

If stock becomes inaccurate because of weak local DB handling, the whole point of the system is lost. PostgreSQL is the safer choice for that.

## Recommended Product Form

### Near-term practical product

Do **not** try to turn this into a browser app that syncs independently on many devices yet.

Build it as a local business application with:

- local backend service
- local PostgreSQL database
- frontend served locally
- optional LAN access from other machines in the same pharmacy

In simple terms:

- the app is "offline-first"
- but the truth lives in one local server inside the pharmacy

## Recommended Deployment Modes

### Mode A: Single-machine pharmacy

Use one Windows PC:

- backend service runs on the same machine
- PostgreSQL runs on the same machine
- frontend runs locally in browser

Best for:

- small shops
- one till
- owner-operated pharmacies

### Mode B: Small LAN pharmacy

Use one main machine as server:

- PostgreSQL on server machine
- backend on server machine
- one or more client PCs open frontend through LAN

Best for:

- shops with 2 to 5 users
- front counter plus back office
- owner wants reports from another PC

### Mode C: Branch sync system

Not recommended now.

This requires:

- branch sync
- conflict handling
- delayed synchronization
- cross-site identity and backup strategy

That should come later, after the single-branch product is stable.

## Should The System Be Offline Or Online?

### Recommendation

The system should be **offline by default**, not cloud-dependent.

### Why offline is better for your market

- internet is not always stable
- pharmacies cannot stop selling because of network problems
- local operation reduces ongoing hosting dependence
- owners care more about reliability than fancy cloud features
- the business problems you want to solve are inside the shop: stock, expiry, sales, and reporting

### When online can still help

Optional internet-connected features can be added later:

- remote support
- offsite encrypted backups
- remote branch monitoring
- license validation
- software updates

These should be optional, not required for daily sales.

## Core Business Features To Prioritize

Based on your use case, the product should focus on these:

### 1. Stock accuracy

- stock in
- stock out
- stock adjustment
- returns
- damage/expiry write-off

### 2. Expiry control

- track product batches
- show nearest-expiry products
- daily expiry warnings
- value-at-risk reporting
- FEFO selling logic where practical

### 3. Out-of-stock prevention

- low-stock alerts
- reorder suggestions
- fast-moving item tracking
- supplier-based reorder view

### 4. Simple sales flow

- search product fast
- sell fast
- print receipt if needed
- daily summary
- sales history

### 5. User roles

- admin
- manager
- cashier

Do not overcomplicate role logic unless the business demands it.

## What Should Not Be Prioritized Right Now

Avoid spending time first on:

- flashy AI features
- overbuilt prescription workflows
- complex branch sync
- hospital-style approval chains
- excessive dashboards that owners do not actually use

The real value is:

- fewer expired drugs
- fewer out-of-stock situations
- cleaner stock records
- faster sales
- simpler reporting

## Data Model Direction

To support real pharmacy use, the database should revolve around:

- products
- categories
- suppliers
- product batches
- sales
- sale items
- users
- stock adjustments
- notifications

### Important stock rule

Do not rely only on `total_stock`.

You should keep:

- aggregate stock for fast display
- batch-level stock as the real source of truth

Each sale should reduce stock from actual batches.

## Expiry Handling Direction

This is one of your biggest product advantages if done well.

The system should:

- store each batch with expiry date
- show expiring products within 30, 60, and 90 days
- prioritize selling the earliest-expiring valid batch
- block or clearly warn on expired stock
- report stock value tied to expiring inventory

This solves a real pharmacy pain point.

## Installation Recommendation For Clients

### Best installation approach

Use a **Windows installer** that sets up:

- PostgreSQL
- backend service
- frontend static files
- desktop/start-menu shortcuts
- backup directory
- local config

### Installation flow

1. Install PostgreSQL locally.
2. Create pharmacy database.
3. Generate secure app secret.
4. Create first admin user.
5. Install backend as a Windows service.
6. Install frontend as local static app served through backend or local web server.
7. Create desktop shortcut like `Pharmacy POS`.
8. Configure automatic local backups.

### Recommended user experience

The owner should be able to click one shortcut and use the system.

They should not need to:

- run terminal commands
- start multiple services manually
- edit env files

## Suggested Packaging Strategy

### Short-term

Package as:

- FastAPI backend
- PostgreSQL local DB
- frontend built files
- Windows service + installer

### Medium-term

You can later wrap the frontend in Electron if you want a desktop-app look, but that is not required to solve the business problem.

For now, a local browser-based app is enough if:

- startup is simple
- backend is auto-started
- local URL is stable

## Backup Strategy

Backups are mandatory for client deployments.

### Minimum backup plan

- automatic daily database backup
- store backup in local backup folder
- allow backup copy to USB/external drive
- allow manual restore by support technician

### Better backup plan

- daily local backup
- weekly backup exported to external device
- optional encrypted cloud/offsite backup when internet is available

### Production rule

No pharmacy deployment should go live without tested restore steps.

## Support Strategy

Design the system so support is realistic.

### Add these support tools

- health check page
- backup status page
- database size/status page
- log viewer or export
- one-click backup
- restore tool for technician use

## Network Recommendation

For multi-PC use in one pharmacy:

- one main PC acts as server
- all client PCs connect to that machine by LAN
- use a fixed local IP or local hostname

Do not depend on public internet DNS for local operation.

## Security Recommendation

Even offline software still needs security.

Minimum production controls:

- no public self-registration
- strong admin password
- role-based access
- local firewall rules if exposing on LAN
- encrypted backups if leaving the premises
- session timeout

## Recommended Technical Decision Summary

### My recommendation for your product

- **Deployment model:** offline from internet, local on-prem system
- **Database:** PostgreSQL
- **Primary topology:** one local server machine per pharmacy
- **Client access:** same machine or LAN-connected PCs
- **Installer target:** Windows
- **Priority features:** stock, expiry, low-stock alerts, sales, backups

## Implementation Roadmap

### Phase 1: Make the product real

- harden backend security
- remove public registration
- fix stock logic
- make batch stock the true source of inventory
- add proper expiry workflows
- add backup and restore

### Phase 2: Make deployment real

- standardize PostgreSQL deployment
- create Windows installer
- install backend as service
- create first-run setup

### Phase 3: Make support real

- logs
- health checks
- admin diagnostics
- upgrade path

## Final Verdict

Yes, this system **can and should** operate offline for pharmacies.

But the right meaning of offline is:

- offline from the internet
- not disconnected from its own local database/server

That is the ideal path for this business.

For your market and your stated goals, the best product is not a fancy cloud system. It is a stable local pharmacy operations system that protects stock, highlights expiry risk, reduces out-of-stock loss, and keeps sales moving every day.
