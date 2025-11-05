#!/bin/bash
# Script de setup pour les composants Foundation
# Exécute la migration et vérifie l'installation

set -e  # Exit on error

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}DisruptIQ Foundation Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Vérifier que nous sommes dans le bon répertoire
if [ ! -f "migrations/foundation_views_and_observability.sql" ]; then
    echo -e "${RED}Erreur: Fichier de migration non trouvé${NC}"
    echo "Assurez-vous d'exécuter ce script depuis backend/"
    exit 1
fi

# Charger .env
if [ -f ".env" ]; then
    echo -e "${YELLOW}Chargement de .env...${NC}"
    export $(grep -v '^#' .env | xargs)
else
    echo -e "${YELLOW}Fichier .env non trouvé, utilisation des valeurs par défaut${NC}"
fi

# Parser DATABASE_URL
if [ ! -z "$DATABASE_URL" ]; then
    DB_USER=$(echo $DATABASE_URL | sed -n 's/.*:\/\/\([^:]*\):.*/\1/p')
    DB_PASSWORD=$(echo $DATABASE_URL | sed -n 's/.*:\/\/[^:]*:\([^@]*\)@.*/\1/p')
    DB_HOST=$(echo $DATABASE_URL | sed -n 's/.*@\([^:]*\):.*/\1/p')
    DB_PORT=$(echo $DATABASE_URL | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
    DB_NAME=$(echo $DATABASE_URL | sed -n 's/.*\/\([^?]*\).*/\1/p')
else
    # Valeurs par défaut
    DB_HOST="${DB_HOST:-localhost}"
    DB_PORT="${DB_PORT:-5432}"
    DB_NAME="${DB_NAME:-disruptiq}"
    DB_USER="${DB_USER:-disruptiq}"
    DB_PASSWORD="${DB_PASSWORD:-disruptiq}"
fi

echo ""
echo -e "${GREEN}Configuration:${NC}"
echo "  Host: $DB_HOST:$DB_PORT"
echo "  Database: $DB_NAME"
echo "  User: $DB_USER"
echo ""

# Fonction pour exécuter psql
run_psql() {
    PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" "$@"
}

# Étape 1: Vérifier connexion BDD
echo -e "${YELLOW}[1/5] Vérification connexion base de données...${NC}"
if run_psql -c "SELECT version();" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Connexion réussie${NC}"
else
    echo -e "${RED}✗ Impossible de se connecter à la base de données${NC}"
    echo ""
    echo "Vérifiez que:"
    echo "  - PostgreSQL est démarré"
    echo "  - Les identifiants dans .env sont corrects"
    echo "  - Le port $DB_PORT est accessible"
    exit 1
fi

# Étape 2: Exécuter la migration
echo ""
echo -e "${YELLOW}[2/5] Exécution de la migration...${NC}"
if run_psql -f migrations/foundation_views_and_observability.sql > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Migration exécutée avec succès${NC}"
    echo "$(date -Iseconds) - foundation_views_and_observability - SUCCESS" >> migrations/migration_history.log
else
    echo -e "${RED}✗ Erreur lors de la migration${NC}"
    echo "$(date -Iseconds) - foundation_views_and_observability - FAILED" >> migrations/migration_history.log
    exit 1
fi

# Étape 3: Vérifier les views
echo ""
echo -e "${YELLOW}[3/5] Vérification des views SQL...${NC}"

EXPECTED_VIEWS=(
    "vw_professionnels_min"
    "vw_professionnels_full"
    "vw_coproprietaires_contact"
    "vw_emails_urgents"
    "vw_coproprietes_stats"
    "vw_documents_active"
)

VIEWS_OK=0
for view in "${EXPECTED_VIEWS[@]}"; do
    if run_psql -c "\d $view" > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} $view"
        ((VIEWS_OK++))
    else
        echo -e "  ${RED}✗${NC} $view (manquante)"
    fi
done

if [ $VIEWS_OK -eq ${#EXPECTED_VIEWS[@]} ]; then
    echo -e "${GREEN}✓ Toutes les views sont créées${NC}"
else
    echo -e "${RED}✗ Certaines views sont manquantes${NC}"
    exit 1
fi

# Étape 4: Vérifier les tables observabilité
echo ""
echo -e "${YELLOW}[4/5] Vérification des tables observabilité...${NC}"

EXPECTED_TABLES=(
    "agent_runs"
    "agent_steps"
)

TABLES_OK=0
for table in "${EXPECTED_TABLES[@]}"; do
    if run_psql -c "\d $table" > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} $table"
        ((TABLES_OK++))
    else
        echo -e "  ${RED}✗${NC} $table (manquante)"
    fi
done

if [ $TABLES_OK -eq ${#EXPECTED_TABLES[@]} ]; then
    echo -e "${GREEN}✓ Toutes les tables observabilité sont créées${NC}"
else
    echo -e "${RED}✗ Certaines tables sont manquantes${NC}"
    exit 1
fi

# Étape 5: Vérifier les index
echo ""
echo -e "${YELLOW}[5/5] Vérification des index...${NC}"

# Compter les index sur agent_runs
AGENT_RUNS_INDEXES=$(run_psql -tAc "SELECT COUNT(*) FROM pg_indexes WHERE tablename = 'agent_runs';")
echo "  agent_runs: $AGENT_RUNS_INDEXES index"

# Compter les index sur agent_steps
AGENT_STEPS_INDEXES=$(run_psql -tAc "SELECT COUNT(*) FROM pg_indexes WHERE tablename = 'agent_steps';")
echo "  agent_steps: $AGENT_STEPS_INDEXES index"

if [ "$AGENT_RUNS_INDEXES" -ge 5 ] && [ "$AGENT_STEPS_INDEXES" -ge 4 ]; then
    echo -e "${GREEN}✓ Index créés${NC}"
else
    echo -e "${YELLOW}⚠ Nombre d'index inférieur à l'attendu${NC}"
fi

# Résumé
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✓ Installation Foundation terminée !${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Composants installés:"
echo "  • 6 views SQL canoniques (read-only)"
echo "  • 2 tables observabilité (agent_runs, agent_steps)"
echo "  • $((AGENT_RUNS_INDEXES + AGENT_STEPS_INDEXES)) index pour performances"
echo ""
echo "Prochaines étapes:"
echo "  1. Redémarrer le backend: docker compose restart backend"
echo "  2. Exécuter les tests: pytest tests/agents/"
echo "  3. Consulter la doc: cat FOUNDATION_INTEGRATION.md"
echo ""
echo "Queries utiles:"
echo "  • Lister les views: psql -c '\\dv'"
echo "  • Lister les tables: psql -c '\\dt agent_*'"
echo "  • Voir un agent run: psql -c 'SELECT * FROM agent_runs LIMIT 1;'"
echo ""

# Test optionnel: Insérer un agent run de test
read -p "Voulez-vous créer un agent run de test ? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo -e "${YELLOW}Création d'un agent run de test...${NC}"

    TEST_SQL="
INSERT INTO agent_runs (
    conversation_id,
    intent,
    source,
    confidence,
    plan_json,
    status,
    cost_tokens,
    evaluator_passed
) VALUES (
    'test-setup-$(date +%s)',
    'SQL_ONLY',
    'SQL',
    0.95,
    '{\"goal\": \"Test setup\", \"steps\": [], \"success_criteria\": \"Setup OK\"}',
    'success',
    100,
    true
) RETURNING id;
"

    RUN_ID=$(run_psql -tAc "$TEST_SQL")
    echo -e "${GREEN}✓ Agent run de test créé (ID: $RUN_ID)${NC}"
    echo ""
    echo "Pour le voir:"
    echo "  psql -c 'SELECT * FROM agent_runs WHERE id = $RUN_ID;'"
fi

echo ""
echo -e "${GREEN}Setup terminé avec succès ! 🎉${NC}"
