# Database Schema Documentation

This directory contains the PostgreSQL database schema and seed data for Pharma POS AI.

## Files

### 1. init.sql
The main database initialization script that creates:
- All database tables with proper constraints
- ENUM types for role, dosage_form, prescription_status, etc.
- Indexes for query optimization
- Triggers for automatic timestamp updates
- Views for common queries (low stock, expiring products, sales summary)
- Proper foreign key relationships

### 2. seed.sql
Sample data for testing and development:
- no release default users should be assumed
- 12 product categories
- 5 suppliers
- 15 sample products
- Product batches with expiry tracking
- Sample notifications

## Database Schema Overview

### Core Tables

#### users
- User authentication and authorization
- Roles: admin, manager, cashier
- Tracks login activity

#### products
- Complete product catalog
- Pharmaceutical-specific fields (dosage, strength, etc.)
- Pricing and inventory thresholds
- Links to categories and suppliers

#### product_batches
- Batch-level inventory tracking
- Expiry date management
- Quarantine functionality
- FIFO/FEFO support

#### sales & sale_items
- Complete sales transaction tracking
- Multiple payment methods
- Discount and tax calculation
- Links to specific batches

#### categories & suppliers
- Product classification
- Supplier contact information

#### notifications
- Low stock alerts
- Expiry warnings
- System notifications

#### activity_logs
- Complete audit trail
- JSON storage for flexible data

## Running the Schema

### Using Docker (Recommended)

The schema runs automatically when you start the Docker containers:

```bash
docker-compose up -d
```

The init.sql and seed.sql files are automatically executed by PostgreSQL on first startup.

### Manual Execution

If you need to run the schema manually:

```bash
# Connect to PostgreSQL
psql -h localhost -p 5432 -U pharma_user -d pharma_pos

# Run schema
\i init.sql

# Run seed data
\i seed.sql
```

### Reset Database

To reset the database and start fresh:

```bash
# Stop containers and remove volumes
docker-compose down -v

# Start fresh (will run init.sql and seed.sql again)
docker-compose up -d
```

## Database Views

### low_stock_products
Shows products that are at or below their low stock threshold.

```sql
SELECT * FROM low_stock_products;
```

### expiring_products
Shows products with batches expiring within 3 months.

```sql
SELECT * FROM expiring_products;
```

### sales_summary
Daily aggregated sales data.

```sql
SELECT * FROM sales_summary;
```

## Common Queries

### Check Product Stock

```sql
SELECT 
    p.name,
    p.total_stock,
    p.low_stock_threshold,
    pb.batch_number,
    pb.quantity,
    pb.expiry_date
FROM products p
LEFT JOIN product_batches pb ON p.id = pb.product_id
WHERE p.id = 1;
```

### Find Expiring Products

```sql
SELECT 
    p.name,
    pb.batch_number,
    pb.quantity,
    pb.expiry_date,
    EXTRACT(DAY FROM (pb.expiry_date - CURRENT_DATE)) as days_to_expiry
FROM products p
JOIN product_batches pb ON p.id = pb.product_id
WHERE pb.expiry_date <= CURRENT_DATE + INTERVAL '30 days'
    AND pb.quantity > 0
ORDER BY pb.expiry_date ASC;
```

### Sales Report

```sql
SELECT 
    DATE(s.created_at) as date,
    COUNT(s.id) as transactions,
    SUM(s.total) as revenue,
    AVG(s.total) as avg_transaction
FROM sales s
WHERE s.created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE(s.created_at)
ORDER BY date DESC;
```

### Top Selling Products

```sql
SELECT 
    p.name,
    SUM(si.quantity) as total_sold,
    SUM(si.subtotal) as revenue
FROM sale_items si
JOIN products p ON si.product_id = p.id
JOIN sales s ON si.sale_id = s.id
WHERE s.created_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY p.id, p.name
ORDER BY total_sold DESC
LIMIT 10;
```

## Backup and Restore

### Create Backup

```bash
# Full database backup
docker-compose exec db pg_dump -U pharma_user -F c pharma_pos > backup.dump

# SQL format backup
docker-compose exec db pg_dump -U pharma_user pharma_pos > backup.sql

# Data only (no schema)
docker-compose exec db pg_dump -U pharma_user --data-only pharma_pos > data_backup.sql

# Schema only (no data)
docker-compose exec db pg_dump -U pharma_user --schema-only pharma_pos > schema_backup.sql
```

### Restore Backup

```bash
# From custom format
docker-compose exec -T db pg_restore -U pharma_user -d pharma_pos < backup.dump

# From SQL file
docker-compose exec -T db psql -U pharma_user pharma_pos < backup.sql
```

## Database Maintenance

### Vacuum and Analyze

```bash
# Vacuum and analyze all tables
docker-compose exec db psql -U pharma_user -d pharma_pos -c "VACUUM ANALYZE;"

# Vacuum specific table
docker-compose exec db psql -U pharma_user -d pharma_pos -c "VACUUM ANALYZE products;"
```

### Check Database Size

```bash
docker-compose exec db psql -U pharma_user -d pharma_pos -c "
SELECT 
    pg_database.datname,
    pg_size_pretty(pg_database_size(pg_database.datname)) AS size
FROM pg_database;
"
```

### Check Table Sizes

```bash
docker-compose exec db psql -U pharma_user -d pharma_pos -c "
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
"
```

## Indexes

All tables have appropriate indexes for:
- Primary keys (automatic)
- Foreign keys
- Frequently queried columns
- Unique constraints

### Check Index Usage

```bash
docker-compose exec db psql -U pharma_user -d pharma_pos -c "
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan as index_scans
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;
"
```

## Security

### Deployment Credentials

**⚠️ IMPORTANT:** Provision site-specific credentials during deployment.

- **Database User**: pharma_user
- **Database Password**: set in `.env`
- **Admin User**: create with `scripts/provision_admin.py`

### Best Practices

1. Use strong passwords for database and users
2. Limit database access to application only
3. Regular backups
4. Monitor activity_logs table for suspicious activity
5. Use SSL/TLS for database connections in production
6. Implement row-level security for multi-tenant setups

## Troubleshooting

### Connection Issues

```bash
# Test database connection
docker-compose exec backend python -c "
from app.db.base import engine
try:
    conn = engine.connect()
    print('✓ Database connection successful')
    conn.close()
except Exception as e:
    print(f'✗ Database connection failed: {e}')
"
```

### View Active Connections

```bash
docker-compose exec db psql -U pharma_user -d pharma_pos -c "
SELECT 
    pid,
    usename,
    application_name,
    client_addr,
    state,
    query
FROM pg_stat_activity
WHERE datname = 'pharma_pos';
"
```

### Kill Long-Running Queries

```bash
docker-compose exec db psql -U pharma_user -d pharma_pos -c "
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'pharma_pos'
    AND state = 'active'
    AND query_start < NOW() - INTERVAL '5 minutes';
"
```

## Migration Strategy

For schema changes after deployment:

1. Create migration scripts in `database/migrations/`
2. Version your migrations (e.g., `001_add_column.sql`)
3. Test migrations on development first
4. Backup before running migrations
5. Run migrations during maintenance window

Example migration:

```sql
-- database/migrations/001_add_customer_address.sql
BEGIN;

ALTER TABLE sales ADD COLUMN IF NOT EXISTS customer_address TEXT;

COMMENT ON COLUMN sales.customer_address IS 'Customer delivery address';

COMMIT;
```

---

**Last Updated**: November 2024
**Schema Version**: 1.0.0
