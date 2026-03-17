-- ============================================================================
-- Momodu SaaS Database Setup Script
-- PostgreSQL 14+
-- ============================================================================

-- ============================================================================
-- 1. CONNECT TO POSTGRES AS SUPERUSER
-- ============================================================================

-- Connect to default postgres database
\c postgres

-- ============================================================================
-- 2. CREATE DATABASE USER (ROLE)
-- ============================================================================

-- Create a dedicated user for the application
-- Replace 'momodu_password' with a strong password
CREATE ROLE momodu WITH LOGIN PASSWORD 'momodu_password';

-- Allow the user to create databases (needed for tests)
ALTER ROLE momodu CREATEDB;

-- Set a connection limit (optional - set to -1 for unlimited)
ALTER ROLE momodu CONNECTION LIMIT 50;

-- ============================================================================
-- 3. CREATE DATABASE
-- ============================================================================

-- Create the database with UTF-8 encoding
CREATE DATABASE momodu
    WITH OWNER = momodu
    ENCODING = 'UTF8'
    LC_COLLATE = 'en_US.UTF-8'
    LC_CTYPE = 'en_US.UTF-8'
    TEMPLATE = template0;

-- ============================================================================
-- 4. GRANT PRIVILEGES
-- ============================================================================

-- Grant all privileges on the database to the user
GRANT ALL PRIVILEGES ON DATABASE momodu TO momodu;

-- ============================================================================
-- 5. CONNECT TO NEW DATABASE AND SETUP EXTENSIONS
-- ============================================================================

\c momodu

-- Enable UUID extension for Django's UUIDField
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pg_trgm extension for better full-text search (optional but useful)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================================
-- 6. GRANT SCHEMA ACCESS
-- ============================================================================

-- Grant usage on public schema
GRANT USAGE ON SCHEMA public TO momodu;

-- Grant all privileges on public schema
GRANT ALL ON SCHEMA public TO momodu;

-- ============================================================================
-- 7. VERIFY SETUP
-- ============================================================================

-- Show current grants
\dp public.*

-- Show database size
SELECT
    pg_size_pretty(pg_database_size('momodu')) AS database_size;

-- Show extensions
SELECT * FROM pg_extension;

-- ============================================================================
-- CONNECTION STRING FOR .env FILE
-- ============================================================================
--
-- Use this format for your DATABASE_URL in .env:
--
-- postgresql://momodu:momodu_password@localhost:5432/momodu
--
-- Or if using async:
-- postgresql+asyncpg://momodu:momodu_password@localhost:5432/momodu
-- ============================================================================


-- ============================================================================
-- ALTERNATIVE: DOCKER POSTGRES SETUP (Optional)
-- ============================================================================
--
-- If using Docker, run:
--
-- docker run --name momodu-postgres \
--   -e POSTGRES_USER=momodu \
--   -e POSTGRES_PASSWORD=momodu_password \
--   -e POSTGRES_DB=momodu \
--   -p 5432:5432 \
--   -v momodu_pgdata:/var/lib/postgresql/data \
--   -d postgres:15-alpine
--
-- ============================================================================


-- ============================================================================
-- MAINTENANCE QUERIES (Useful for production)
-- ============================================================================

-- Check active connections
SELECT
    datname AS database_name,
    numbackends AS active_connections
FROM pg_stat_database
WHERE datname = 'momodu';

-- Show table sizes
SELECT
    schemaname,
    relname AS table_name,
    pg_size_pretty(pg_relation_size(relid)) AS size
FROM pg_stat_user_tables
ORDER BY pg_relation_size(relid) DESC;

-- Show index sizes
SELECT
    schemaname,
    relname AS table_name,
    indexrelname AS index_name,
    pg_size_pretty(pg_relation_size(relid)) AS size
FROM pg_stat_user_indexes
ORDER BY pg_relation_size(relid) DESC;


-- ============================================================================
-- BACKUP & RESTORE COMMANDS
-- ============================================================================

-- Backup (run from command line):
-- pg_dump -U momodu -Fc momodu > momodu_backup.dump

-- Restore (run from command line):
-- pg_restore -U momodu -d momodu -c momodu_backup.dump
