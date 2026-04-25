-- Script SQL à exécuter une seule fois sur PostgreSQL
-- Crée un utilisateur en lecture seule pour le microservice Reporting
-- À lancer avec : psql -U postgres -d accounting_db -f scripts/create_readonly_user.sql

-- 1. Créer l'utilisateur
CREATE USER reporting_ro WITH PASSWORD 'reporting_ro';

-- 2. Autoriser la connexion à la base
GRANT CONNECT ON DATABASE accounting_db TO reporting_ro;

-- 3. Accès au schéma public
GRANT USAGE ON SCHEMA public TO reporting_ro;

-- 4. SELECT sur toutes les tables existantes
GRANT SELECT ON ALL TABLES IN SCHEMA public TO reporting_ro;

-- 5. SELECT automatique sur les futures tables (migrations Alembic)
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO reporting_ro;

-- Vérification
\echo '--- Permissions accordées à reporting_ro ---'
\du reporting_ro
