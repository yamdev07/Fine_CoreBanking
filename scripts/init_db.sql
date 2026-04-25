-- Création de l'utilisateur en lecture seule pour le reporting service.
-- Exécuté automatiquement par PostgreSQL au premier démarrage du conteneur.

-- Créer le user s'il n'existe pas déjà
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'reporting_ro') THEN
        CREATE ROLE reporting_ro LOGIN PASSWORD 'reporting_ro';
    END IF;
END
$$;

-- Accès à la base
GRANT CONNECT ON DATABASE accounting_db TO reporting_ro;

-- Accès au schéma public
GRANT USAGE ON SCHEMA public TO reporting_ro;

-- SELECT uniquement sur toutes les tables existantes
GRANT SELECT ON ALL TABLES IN SCHEMA public TO reporting_ro;

-- SELECT automatique sur les futures tables créées par postgres
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO reporting_ro;
