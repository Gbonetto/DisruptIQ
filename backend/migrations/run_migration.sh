#!/bin/bash
# Script pour exécuter les migrations SQL
# Usage: ./run_migration.sh <migration_file.sql>

set -e  # Exit on error

# Couleurs pour output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration par défaut (peut être overridé par .env)
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-disruptiq}"
DB_USER="${DB_USER:-disruptiq}"
DB_PASSWORD="${DB_PASSWORD:-disruptiq}"

# Charger .env si présent
if [ -f "../.env" ]; then
    echo -e "${YELLOW}Loading .env file...${NC}"
    export $(grep -v '^#' ../.env | xargs)

    # Parser DATABASE_URL si présent
    if [ ! -z "$DATABASE_URL" ]; then
        # Format: postgresql+asyncpg://user:pass@host:port/dbname
        # On extrait les infos
        DB_USER=$(echo $DATABASE_URL | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
        DB_PASSWORD=$(echo $DATABASE_URL | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')
        DB_HOST=$(echo $DATABASE_URL | sed -n 's/.*@\([^:]*\):.*/\1/p')
        DB_PORT=$(echo $DATABASE_URL | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
        DB_NAME=$(echo $DATABASE_URL | sed -n 's/.*\/\([^?]*\).*/\1/p')
    fi
fi

# Vérifier qu'un fichier de migration est fourni
if [ -z "$1" ]; then
    echo -e "${RED}Error: No migration file specified${NC}"
    echo "Usage: $0 <migration_file.sql>"
    echo ""
    echo "Available migrations:"
    ls -1 *.sql 2>/dev/null || echo "  No migrations found"
    exit 1
fi

MIGRATION_FILE="$1"

# Vérifier que le fichier existe
if [ ! -f "$MIGRATION_FILE" ]; then
    echo -e "${RED}Error: Migration file not found: $MIGRATION_FILE${NC}"
    exit 1
fi

echo -e "${GREEN}=== DisruptIQ Migration Runner ===${NC}"
echo ""
echo "Migration file: $MIGRATION_FILE"
echo "Database: $DB_NAME"
echo "Host: $DB_HOST:$DB_PORT"
echo "User: $DB_USER"
echo ""

# Demander confirmation
read -p "Execute this migration? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}Migration cancelled${NC}"
    exit 0
fi

# Exécuter la migration
echo -e "${YELLOW}Executing migration...${NC}"

PGPASSWORD="$DB_PASSWORD" psql \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    -f "$MIGRATION_FILE"

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ Migration completed successfully!${NC}"

    # Logger la migration
    MIGRATION_NAME=$(basename "$MIGRATION_FILE" .sql)
    echo "$(date -Iseconds) - $MIGRATION_NAME - SUCCESS" >> migration_history.log
else
    echo ""
    echo -e "${RED}❌ Migration failed with exit code $EXIT_CODE${NC}"

    # Logger l'échec
    MIGRATION_NAME=$(basename "$MIGRATION_FILE" .sql)
    echo "$(date -Iseconds) - $MIGRATION_NAME - FAILED" >> migration_history.log
    exit $EXIT_CODE
fi

echo ""
echo "Next steps:"
echo "  1. Restart backend: docker compose restart backend"
echo "  2. Verify tables: psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c '\dt'"
echo "  3. Verify views: psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c '\dv'"
