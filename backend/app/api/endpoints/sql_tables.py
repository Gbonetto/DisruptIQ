"""
SQL Table Management Endpoints

Provides CRUD operations for SQL tables:
- List all tables with metadata
- View table details (schema, sample data)
- Import CSV to create new tables
- Delete tables
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, inspect
import structlog
import pandas as pd
import io
from typing import List, Dict, Any, Optional
from pathlib import Path
from pydantic import BaseModel

from app.core.database import get_db

router = APIRouter()
logger = structlog.get_logger()


# Models for detailed error reporting
class ImportError(BaseModel):
    """Detailed error for a failed row"""
    row_number: int
    error_type: str  # "missing_required_field", "duplicate_key", "validation_error", "sql_error"
    error_message: str
    row_data: Dict[str, Any]  # Original row data for debugging


class ImportResult(BaseModel):
    """Detailed import result"""
    message: str
    table_name: str
    rows_imported: int
    rows_skipped: int
    errors: List[ImportError] = []  # Detailed errors
    warnings: List[str] = []  # Warnings for user


def get_required_columns(table_name: str) -> List[str]:
    """Get required columns for each table"""
    required_by_table = {
        'professionnels': ['name', 'email'],
        'coproprietaires': ['nom', 'prenom', 'copropriete_id', 'numero_lot'],
        'coproprietes': ['nom', 'adresse', 'ville', 'code_postal']
    }
    return required_by_table.get(table_name, [])


def get_default_values(table_name: str) -> Dict[str, Any]:
    """Get default values for columns that have NOT NULL constraints without defaults"""
    defaults_by_table = {
        'professionnels': {
            'is_indexed': False,  # New professionals start as not indexed
        },
        'coproprietaires': {},
        'coproprietes': {}
    }
    return defaults_by_table.get(table_name, {})


async def get_table_column_types(db: AsyncSession, table_name: str) -> Dict[str, str]:
    """Get column types from database schema"""
    try:
        result = await db.execute(text("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = :table_name
        """), {"table_name": table_name})

        rows = result.fetchall()
        return {row[0]: row[1] for row in rows}
    except Exception as e:
        logger.warning("failed_to_get_column_types", table=table_name, error=str(e))
        return {}


def convert_value_to_column_type(value: Any, column_type: str) -> Any:
    """
    Auto-convert values to match database column types

    This prevents errors like:
    - "expected str, got int" when inserting 782411682 into TEXT column
    - "expected int, got str" when inserting "123" into INTEGER column
    - "invalid input syntax for type json" when inserting "SEO" into JSONB column
    - "invalid date format" when inserting "25/12/2024" into DATE column
    """
    import json
    from dateutil import parser as date_parser
    from datetime import datetime, date

    if pd.isna(value):
        return None

    # Normalize column type
    col_type_lower = column_type.lower()

    # DATE/TIMESTAMP columns → parse multiple formats
    if any(t in col_type_lower for t in ['date', 'timestamp']):
        if isinstance(value, (datetime, date)):
            # Already a date/datetime object
            return value

        if isinstance(value, str):
            try:
                # Try parsing with dateutil (handles many formats)
                parsed_date = date_parser.parse(value, dayfirst=True)  # DD/MM/YYYY priority

                # Return appropriate type based on column
                if 'timestamp' in col_type_lower:
                    return parsed_date  # Keep datetime with time
                else:
                    return parsed_date.date()  # DATE column, only date part
            except (ValueError, TypeError) as e:
                logger.warning("failed_to_parse_date",
                             value=value,
                             column_type=column_type,
                             error=str(e))
                # Return original value, let PostgreSQL try to parse it
                return value

        # For numeric timestamps (Unix epoch)
        if isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(value)
            except (ValueError, OSError):
                return value

    # JSON/JSONB columns → convert to valid JSON
    elif any(t in col_type_lower for t in ['json', 'jsonb']):
        # If already a dict/list, return as-is (will be serialized by SQLAlchemy)
        if isinstance(value, (dict, list)):
            return value

        # If string, try to parse as JSON first
        if isinstance(value, str):
            # Try parsing as JSON
            try:
                return json.loads(value)
            except (json.JSONDecodeError, ValueError):
                # Not valid JSON, check if it's comma-separated values
                if ',' in value:
                    # "SEO, Marketing, Design" → ["SEO", "Marketing", "Design"]
                    return [item.strip() for item in value.split(',')]
                else:
                    # Single value "SEO" → ["SEO"]
                    return [value.strip()]

        # For other types (int, float, bool), wrap in array
        return [value]

    # Text/String columns → always convert to string
    elif any(t in col_type_lower for t in ['text', 'varchar', 'char', 'character']):
        return str(value)

    # Integer columns → convert to int
    elif any(t in col_type_lower for t in ['integer', 'int', 'smallint', 'bigint']):
        try:
            return int(float(value))  # Handle "123.0" from CSV
        except (ValueError, TypeError):
            return value

    # Float/Decimal columns → convert to float
    elif any(t in col_type_lower for t in ['real', 'double', 'float', 'numeric', 'decimal']):
        try:
            return float(value)
        except (ValueError, TypeError):
            return value

    # Boolean columns → convert to bool
    elif 'boolean' in col_type_lower:
        if isinstance(value, str):
            return value.lower() in ['true', '1', 'yes', 'oui', 't']
        return bool(value)

    # Default: return as-is
    return value


@router.get("/tables")
async def list_tables(
    db: AsyncSession = Depends(get_db)
):
    """
    List all SQL tables with metadata

    Returns:
        {
            "tables": [
                {
                    "name": "copropriétaires",
                    "row_count": 42,
                    "columns": ["id", "nom", "email", ...]
                },
                ...
            ],
            "total": 3
        }
    """
    try:
        # Get all table names (exclude alembic and internal tables)
        result = await db.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
            AND table_name NOT LIKE 'alembic_%'
            AND table_name NOT IN ('documents', 'conversations', 'emails')
            ORDER BY table_name;
        """))

        table_names = [row[0] for row in result.fetchall()]

        tables_info = []

        for table_name in table_names:
            # Get row count
            count_result = await db.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
            row_count = count_result.scalar()

            # Get column names
            columns_result = await db.execute(text(f"""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = '{table_name}'
                ORDER BY ordinal_position;
            """))
            columns = [row[0] for row in columns_result.fetchall()]

            tables_info.append({
                "name": table_name,
                "row_count": row_count,
                "columns": columns
            })

        logger.info("tables_listed", count=len(tables_info))

        return {
            "tables": tables_info,
            "total": len(tables_info)
        }

    except Exception as e:
        logger.error("list_tables_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list tables: {str(e)}"
        )


@router.get("/tables/{table_name}")
async def get_table_details(
    table_name: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed information about a table

    Returns:
        {
            "name": "copropriétaires",
            "columns": [
                {"name": "id", "type": "INTEGER", "nullable": false, "default": null},
                {"name": "nom", "type": "VARCHAR(255)", "nullable": true, "default": null},
                ...
            ],
            "row_count": 42,
            "sample_rows": [{...}, {...}, ...]  // First 5 rows
        }
    """
    try:
        # Verify table exists
        check_result = await db.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = :table_name
            );
        """), {"table_name": table_name})

        if not check_result.scalar():
            raise HTTPException(
                status_code=404,
                detail=f"Table '{table_name}' not found"
            )

        # Get column details
        columns_result = await db.execute(text(f"""
            SELECT
                column_name,
                data_type,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_name = '{table_name}'
            ORDER BY ordinal_position;
        """))

        columns = [
            {
                "name": row[0],
                "type": row[1],
                "nullable": row[2] == "YES",
                "default": row[3]
            }
            for row in columns_result.fetchall()
        ]

        # Get row count
        count_result = await db.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
        row_count = count_result.scalar()

        # Get sample rows (first 5)
        sample_result = await db.execute(text(f'SELECT * FROM "{table_name}" LIMIT 5'))
        sample_rows = [dict(row._mapping) for row in sample_result.fetchall()]

        logger.info("table_details_retrieved", table_name=table_name, row_count=row_count)

        return {
            "name": table_name,
            "columns": columns,
            "row_count": row_count,
            "sample_rows": sample_rows
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_table_details_failed", table_name=table_name, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get table details: {str(e)}"
        )


@router.post("/import-csv")
async def import_csv(
    file: UploadFile = File(...),
    table_name: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Import CSV file to create a new SQL table

    Args:
        file: CSV file
        table_name: Name for the new table

    Returns:
        {
            "message": "Table created successfully",
            "table_name": "copropriétaires",
            "rows_imported": 42,
            "columns": ["nom", "email", ...]
        }
    """
    try:
        # Validate file type
        if not file.filename.endswith('.csv'):
            raise HTTPException(
                status_code=400,
                detail="Only CSV files are allowed"
            )

        # Sanitize table name (alphanumeric, underscore only)
        import re
        sanitized_table_name = re.sub(r'[^a-zA-Z0-9_]', '_', table_name.lower())

        if not sanitized_table_name:
            raise HTTPException(
                status_code=400,
                detail="Invalid table name"
            )

        # Check if table already exists
        check_result = await db.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = :table_name
            );
        """), {"table_name": sanitized_table_name})

        if check_result.scalar():
            raise HTTPException(
                status_code=400,
                detail=f"Table '{sanitized_table_name}' already exists. Delete it first or choose a different name."
            )

        # Read CSV file with flexible delimiter detection
        contents = await file.read()

        # Try to detect delimiter by reading first line
        first_line = contents.decode('utf-8', errors='ignore').split('\n')[0]
        comma_count = first_line.count(',')
        semicolon_count = first_line.count(';')
        delimiter = ';' if semicolon_count > comma_count else ','

        df = pd.read_csv(io.BytesIO(contents), delimiter=delimiter)

        if df.empty:
            raise HTTPException(
                status_code=400,
                detail="CSV file is empty"
            )

        # Sanitize column names
        df.columns = [re.sub(r'[^a-zA-Z0-9_]', '_', col.lower().strip()) for col in df.columns]

        # Create table schema
        create_table_sql = f'CREATE TABLE "{sanitized_table_name}" (\n'
        create_table_sql += '    id SERIAL PRIMARY KEY,\n'

        for col in df.columns:
            # Infer SQL type from pandas dtype
            dtype = df[col].dtype
            if pd.api.types.is_integer_dtype(dtype):
                sql_type = "INTEGER"
            elif pd.api.types.is_float_dtype(dtype):
                sql_type = "DOUBLE PRECISION"
            elif pd.api.types.is_bool_dtype(dtype):
                sql_type = "BOOLEAN"
            elif pd.api.types.is_datetime64_any_dtype(dtype):
                sql_type = "TIMESTAMP"
            else:
                sql_type = "TEXT"

            create_table_sql += f'    {col} {sql_type},\n'

        # Remove trailing comma and close
        create_table_sql = create_table_sql.rstrip(',\n') + '\n);'

        logger.info("creating_table_from_csv",
                   table_name=sanitized_table_name,
                   columns=list(df.columns),
                   rows=len(df))

        # Execute CREATE TABLE
        await db.execute(text(create_table_sql))

        # Insert data row by row (batch inserts for production)
        for _, row in df.iterrows():
            columns_str = ', '.join([f'"{col}"' for col in df.columns])
            placeholders = ', '.join([f':col_{i}' for i in range(len(df.columns))])
            insert_sql = f'INSERT INTO "{sanitized_table_name}" ({columns_str}) VALUES ({placeholders})'

            params = {f'col_{i}': (None if pd.isna(val) else val) for i, val in enumerate(row)}

            await db.execute(text(insert_sql), params)

        await db.commit()

        logger.info("csv_imported_successfully",
                   table_name=sanitized_table_name,
                   rows_imported=len(df))

        return {
            "message": "Table created successfully",
            "table_name": sanitized_table_name,
            "rows_imported": len(df),
            "columns": list(df.columns)
        }

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error("csv_import_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to import CSV: {str(e)}"
        )


@router.delete("/tables/{table_name}")
async def delete_table(
    table_name: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a SQL table

    Args:
        table_name: Name of table to delete

    Returns:
        {
            "message": "Table deleted successfully",
            "table_name": "copropriétaires"
        }
    """
    try:
        # Verify table exists
        check_result = await db.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = :table_name
            );
        """), {"table_name": table_name})

        if not check_result.scalar():
            raise HTTPException(
                status_code=404,
                detail=f"Table '{table_name}' not found"
            )

        # Prevent deletion of core tables
        protected_tables = ['documents', 'conversations', 'emails', 'users']
        if table_name in protected_tables:
            raise HTTPException(
                status_code=403,
                detail=f"Cannot delete protected table '{table_name}'"
            )

        # Drop table
        await db.execute(text(f'DROP TABLE IF EXISTS "{table_name}" CASCADE'))
        await db.commit()

        logger.info("table_deleted", table_name=table_name)

        return {
            "message": "Table deleted successfully",
            "table_name": table_name
        }

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error("delete_table_failed", table_name=table_name, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete table: {str(e)}"
        )


@router.post("/append-csv")
async def append_csv(
    file: UploadFile = File(...),
    table_name: str = Form(...),
    column_mapping: str = Form(...),  # JSON string: {"csv_col": "db_col", ...}
    db: AsyncSession = Depends(get_db)
):
    """
    Append CSV data to an existing table with column mapping

    Args:
        file: CSV file
        table_name: Target table (professionnels, coproprietaires, coproprietes)
        column_mapping: JSON mapping of CSV columns to DB columns

    Returns:
        {
            "message": "Data imported successfully",
            "table_name": "professionnels",
            "rows_imported": 10,
            "rows_skipped": 2
        }
    """
    import json

    try:
        # Validate table name (must be one of the allowed tables)
        allowed_tables = ['professionnels', 'coproprietaires', 'coproprietes']
        if table_name not in allowed_tables:
            raise HTTPException(
                status_code=400,
                detail=f"Table must be one of: {', '.join(allowed_tables)}"
            )

        # Validate file type
        if not file.filename.endswith('.csv'):
            raise HTTPException(
                status_code=400,
                detail="Only CSV files are allowed"
            )

        # Parse column mapping
        try:
            mapping = json.loads(column_mapping)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400,
                detail="Invalid column mapping JSON"
            )

        # Read CSV file with flexible delimiter detection
        contents = await file.read()

        # Try to detect delimiter by reading first line
        first_line = contents.decode('utf-8', errors='ignore').split('\n')[0]
        comma_count = first_line.count(',')
        semicolon_count = first_line.count(';')
        delimiter = ';' if semicolon_count > comma_count else ','

        df = pd.read_csv(io.BytesIO(contents), delimiter=delimiter)

        if df.empty:
            raise HTTPException(
                status_code=400,
                detail="CSV file is empty"
            )

        # Get target table schema
        schema_result = await db.execute(text(f"""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = '{table_name}'
            AND column_name != 'id'
            AND column_name NOT IN ('created_at', 'updated_at', 'is_indexed', 'last_indexed_at')
            ORDER BY ordinal_position;
        """))

        db_columns = {row[0]: row[1] for row in schema_result.fetchall()}

        # Validate mapping
        for csv_col, db_col in mapping.items():
            if db_col and db_col not in db_columns:
                raise HTTPException(
                    status_code=400,
                    detail=f"Column '{db_col}' does not exist in table '{table_name}'"
                )

        # Get required columns for validation
        required_columns = get_required_columns(table_name)

        # Get default values for NOT NULL columns
        default_values = get_default_values(table_name)

        # Get column types from database schema for type conversion
        column_types = await get_table_column_types(db, table_name)
        logger.info("table_schema_loaded", table=table_name, columns=list(column_types.keys()))

        # Apply mapping and insert rows WITH DETAILED ERROR TRACKING
        rows_imported = 0
        rows_skipped = 0
        errors: List[ImportError] = []
        warnings: List[str] = []

        for row_idx, row in df.iterrows():
            row_number = int(row_idx) + 2  # +2 because: 0-indexed + header row

            try:
                # Start with default values for NOT NULL columns
                insert_data = default_values.copy()

                # Build insert data from mapping WITH TYPE CONVERSION
                for csv_col, db_col in mapping.items():
                    if db_col and csv_col in df.columns:
                        value = row[csv_col]
                        # Skip if NaN
                        if pd.notna(value):
                            # Auto-convert type to match database column
                            if db_col in column_types:
                                value = convert_value_to_column_type(value, column_types[db_col])

                                # Special handling for JSON/JSONB: serialize to string
                                col_type_lower = column_types[db_col].lower()
                                if any(t in col_type_lower for t in ['json', 'jsonb']):
                                    if isinstance(value, (dict, list)):
                                        import json
                                        value = json.dumps(value)

                            insert_data[db_col] = value

                # VALIDATION 1: Check required fields
                missing_required = [col for col in required_columns if col not in insert_data]
                if missing_required:
                    errors.append(ImportError(
                        row_number=row_number,
                        error_type="missing_required_field",
                        error_message=f"Champs obligatoires manquants: {', '.join(missing_required)}",
                        row_data={k: str(v) if pd.notna(v) else '' for k, v in row.to_dict().items()}
                    ))
                    rows_skipped += 1
                    logger.warning("row_skipped_missing_fields",
                                 row=row_number,
                                 missing=missing_required)
                    continue

                # VALIDATION 2: Empty row check
                if not insert_data:
                    errors.append(ImportError(
                        row_number=row_number,
                        error_type="empty_row",
                        error_message="Ligne vide ou toutes les valeurs sont manquantes",
                        row_data={k: str(v) if pd.notna(v) else '' for k, v in row.to_dict().items()}
                    ))
                    rows_skipped += 1
                    logger.warning("row_skipped_empty", row=row_number)
                    continue

                # VALIDATION 3: Check for duplicates BEFORE inserting (professionnels only)
                if table_name == "professionnels" and "email" in insert_data:
                    duplicate_check = await db.execute(
                        text("SELECT id FROM professionnels WHERE email = :email"),
                        {"email": insert_data["email"]}
                    )
                    if duplicate_check.scalar():
                        errors.append(ImportError(
                            row_number=row_number,
                            error_type="duplicate_key",
                            error_message=f"Email en double: {insert_data['email']} existe déjà dans la base",
                            row_data=insert_data
                        ))
                        rows_skipped += 1
                        logger.warning("row_skipped_duplicate_email",
                                     row=row_number,
                                     email=insert_data["email"])
                        continue

                # Build INSERT query
                columns_str = ', '.join([f'"{col}"' for col in insert_data.keys()])
                placeholders = ', '.join([f':col_{i}' for i in range(len(insert_data))])
                insert_sql = f'INSERT INTO "{table_name}" ({columns_str}) VALUES ({placeholders})'

                params = {f'col_{i}': val for i, val in enumerate(insert_data.values())}

                await db.execute(text(insert_sql), params)
                rows_imported += 1

                logger.info("row_imported_successfully",
                           table=table_name,
                           row=row_number,
                           name=insert_data.get('name') or insert_data.get('nom', 'N/A'))

            except Exception as e:
                error_message = str(e)

                # Classify error type
                if "duplicate key" in error_message.lower():
                    error_type = "duplicate_key"
                elif "violates" in error_message.lower():
                    error_type = "constraint_violation"
                else:
                    error_type = "sql_error"

                errors.append(ImportError(
                    row_number=row_number,
                    error_type=error_type,
                    error_message=error_message[:200],  # Truncate long error messages
                    row_data=insert_data if insert_data else {k: str(v) if pd.notna(v) else '' for k, v in row.to_dict().items()}
                ))

                logger.error("row_import_failed",
                            table=table_name,
                            row=row_number,
                            error_type=error_type,
                            error=error_message[:200])
                rows_skipped += 1
                continue

        await db.commit()

        # Build user-friendly message
        if rows_imported > 0 and rows_skipped == 0:
            message = f"✅ {rows_imported} ligne{'s' if rows_imported > 1 else ''} importée{'s' if rows_imported > 1 else ''} avec succès"
        elif rows_imported > 0 and rows_skipped > 0:
            message = f"⚠️ {rows_imported} ligne{'s' if rows_imported > 1 else ''} importée{'s' if rows_imported > 1 else ''}, {rows_skipped} ignorée{'s' if rows_skipped > 1 else ''} (voir détails)"
        else:
            message = f"❌ Aucune ligne importée. {rows_skipped} ligne{'s' if rows_skipped > 1 else ''} ignorée{'s' if rows_skipped > 1 else ''} (voir erreurs ci-dessous)"

        logger.info("csv_appended_with_details",
                   table_name=table_name,
                   rows_imported=rows_imported,
                   rows_skipped=rows_skipped,
                   error_count=len(errors))

        return ImportResult(
            message=message,
            table_name=table_name,
            rows_imported=rows_imported,
            rows_skipped=rows_skipped,
            errors=errors,
            warnings=warnings
        )

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error("csv_append_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to import CSV: {str(e)}"
        )


@router.delete("/purge/{table_name}")
async def purge_table(
    table_name: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Purge all data from a table (TRUNCATE)

    Args:
        table_name: Name of table to purge

    Returns:
        {
            "message": "Table purged successfully",
            "table_name": "professionnels"
        }
    """
    try:
        # Validate table name (must be one of the allowed tables)
        allowed_tables = ['professionnels', 'coproprietaires', 'coproprietes']
        if table_name not in allowed_tables:
            raise HTTPException(
                status_code=400,
                detail=f"Table must be one of: {', '.join(allowed_tables)}"
            )

        # Verify table exists
        check_result = await db.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = :table_name
            );
        """), {"table_name": table_name})

        if not check_result.scalar():
            raise HTTPException(
                status_code=404,
                detail=f"Table '{table_name}' not found"
            )

        # Truncate table (keeps structure, removes all data, resets sequences)
        await db.execute(text(f'TRUNCATE TABLE "{table_name}" RESTART IDENTITY CASCADE'))
        await db.commit()

        logger.info("table_purged", table_name=table_name)

        return {
            "message": "Table purged successfully",
            "table_name": table_name
        }

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error("purge_table_failed", table_name=table_name, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to purge table: {str(e)}"
        )


@router.get("/download-template/{table_name}")
async def download_template(
    table_name: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Download CSV template for a table with correct column headers

    Args:
        table_name: Table name (professionnels, coproprietaires, coproprietes)

    Returns:
        CSV file with column headers
    """
    try:
        # Validate table name
        allowed_tables = ['professionnels', 'coproprietaires', 'coproprietes']
        if table_name not in allowed_tables:
            raise HTTPException(
                status_code=400,
                detail=f"Table must be one of: {', '.join(allowed_tables)}"
            )

        # Get column names (exclude id, created_at, updated_at, internal fields)
        columns_result = await db.execute(text(f"""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = '{table_name}'
            AND column_name != 'id'
            AND column_name NOT IN ('created_at', 'updated_at', 'is_indexed', 'last_indexed_at')
            ORDER BY ordinal_position;
        """))

        columns = [row[0] for row in columns_result.fetchall()]

        if not columns:
            raise HTTPException(
                status_code=404,
                detail=f"Table '{table_name}' not found or has no columns"
            )

        # Create empty DataFrame with column headers
        df = pd.DataFrame(columns=columns)

        # Convert to CSV
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)

        # Return as downloadable file
        return StreamingResponse(
            io.BytesIO(csv_buffer.getvalue().encode()),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={table_name}_template.csv"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("download_template_failed", table_name=table_name, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate template: {str(e)}"
        )
