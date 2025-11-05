#!/bin/bash
# Script d'initialisation Alembic pour DisruptIQ
# Crée le système de migrations de base de données

set -e

echo "🗄️  Initialisation des migrations Alembic pour DisruptIQ"
echo "=================================================="

cd "$(dirname "$0")/.."

# Vérifier si Alembic est déjà initialisé
if [ -d "alembic" ]; then
    echo "⚠️  Alembic déjà initialisé dans ./alembic/"
    read -p "Voulez-vous réinitialiser? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 0
    fi
    rm -rf alembic
fi

# Initialiser Alembic
echo "📦 Initialisation d'Alembic..."
alembic init alembic

# Créer le fichier env.py configuré pour async SQLAlchemy
echo "⚙️  Configuration d'env.py pour async..."
cat > alembic/env.py << 'EOF'
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
import asyncio

# Import app config
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.core.database import Base

# Import all models to ensure they're registered
from app.models import (
    User,
    Email,
    Vendor,
    Document,
    Copropriete,
    Coproprietaire,
    Professionnel,
    ProfessionnelCopropriete,
    Conversation,
    Message
)

# Alembic Config object
config = context.config

# Override sqlalchemy.url from settings
config.set_main_option("sqlalchemy.url", str(settings.database_url))

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata for autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async engine."""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = str(settings.database_url)

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
EOF

# Mettre à jour alembic.ini
echo "📝 Configuration d'alembic.ini..."
cat > alembic.ini << 'EOF'
# Alembic configuration for DisruptIQ

[alembic]
# Path to migration scripts
script_location = alembic

# Template used to generate migration file names
file_template = %%(year)d%%(month).2d%%(day).2d_%%(hour).2d%%(minute).2d_%%(rev)s_%%(slug)s

# Truncate slug to 40 characters
# truncate_slug_length = 40

# Timezone for migration file timestamps
# timezone = UTC

# max length of characters to apply to the "slug" field
# truncate_slug_length = 40

# set to 'true' to run the environment during
# the 'revision' command, regardless of autogenerate
# revision_environment = false

# set to 'true' to allow .pyc and .pyo files without
# a source .py file to be detected as revisions in the
# versions/ directory
# sourceless = false

# version location specification; This defaults
# to alembic/versions.  When using multiple version
# directories, initial revisions must be specified with --version-path.
# The path separator used here should be the separator specified by "version_path_separator" below.
# version_locations = %(here)s/bar:%(here)s/bat:alembic/versions

# version path separator; As mentioned above, this is the character used to split
# version_locations. The default within new alembic.ini files is "os", which uses os.pathsep.
# If this key is omitted entirely, it falls back to the legacy behavior of splitting on spaces and/or commas.
# Valid values for version_path_separator are:
#
# version_path_separator = :
# version_path_separator = ;
# version_path_separator = space
version_path_separator = os  # Use os.pathsep. Default configuration used for new projects.

# The output encoding used when revision files
# are written from script.py.mako
# output_encoding = utf-8

# Database URL - overridden by env.py from settings
sqlalchemy.url = postgresql+asyncpg://disruptiq:disruptiq_password@localhost:5432/disruptiq

[post_write_hooks]
# Post-write hooks to run after migrations
# hooks = black, isort
# black.type = console_scripts
# black.entrypoint = black
# black.options = -l 120 REVISION_SCRIPT_FILENAME
# isort.type = console_scripts
# isort.entrypoint = isort
# isort.options = REVISION_SCRIPT_FILENAME

# Logging configuration
[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
EOF

# Créer la première migration
echo "🏗️  Création de la migration initiale..."
alembic revision --autogenerate -m "initial_schema_with_all_tables"

echo ""
echo "✅ Alembic initialisé avec succès!"
echo ""
echo "📚 Prochaines étapes:"
echo "  1. Vérifier le fichier de migration dans alembic/versions/"
echo "  2. Appliquer la migration:"
echo "     alembic upgrade head"
echo ""
echo "  3. Créer une nouvelle migration après modification de modèles:"
echo "     alembic revision --autogenerate -m \"description_changement\""
echo ""
echo "  4. Annuler une migration:"
echo "     alembic downgrade -1"
echo ""

# Afficher le statut
echo "📊 Statut actuel:"
alembic current

echo ""
echo "✨ Configuration terminée!"
