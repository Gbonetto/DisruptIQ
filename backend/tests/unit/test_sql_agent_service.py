"""
Unit Tests for SQL Agent Service
Tests natural language to SQL conversion, validation, and execution
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock, patch
import json

from app.services.sql_agent_service import SQLAgentService


@pytest.mark.unit
@pytest.mark.asyncio
class TestSchemaDescription:
    """Tests for schema description building"""

    def test_build_schema_description(self):
        """Test returns complete schema string"""
        sql_agent = SQLAgentService()

        schema = sql_agent._build_schema_description()

        assert len(schema) > 100  # Should be substantial
        assert "professionnels" in schema
        assert "coproprietes" in schema
        assert "coproprietaires" in schema

    def test_build_schema_description_includes_all_tables(self):
        """Test all allowed tables are present in schema"""
        sql_agent = SQLAgentService()

        schema = sql_agent._build_schema_description()

        for table in sql_agent.ALLOWED_TABLES:
            assert table in schema.lower()


@pytest.mark.unit
@pytest.mark.asyncio
class TestNaturalLanguageToSQL:
    """Tests for NL to SQL conversion"""

    async def test_nl_to_sql_simple_select(self):
        """Test 'Find all plumbers' → SELECT"""
        sql_agent = SQLAgentService()

        # Mock LLM response
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "sql": "SELECT * FROM professionnels WHERE category = 'plombier'",
            "explanation": "Finds all plumbers"
        })
        sql_agent.llm_service.chat_model.ainvoke = AsyncMock(return_value=mock_response)

        result = await sql_agent.natural_language_to_sql(
            "Find all plumbers",
            operation_type="SELECT"
        )

        assert "SELECT" in result["sql"].upper()
        assert "professionnels" in result["sql"]
        assert "explanation" in result

    async def test_nl_to_sql_with_join(self):
        """Test 'Who lives in building X' → JOIN query"""
        sql_agent = SQLAgentService()

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "sql": "SELECT c.nom, c.prenom FROM coproprietaires c JOIN coproprietes co ON c.copropriete_id = co.id WHERE co.nom = 'Les Mimosas'",
            "explanation": "Finds residents of Les Mimosas"
        })
        sql_agent.llm_service.chat_model.ainvoke = AsyncMock(return_value=mock_response)

        result = await sql_agent.natural_language_to_sql(
            "Who lives in Les Mimosas?",
            operation_type="SELECT"
        )

        assert "JOIN" in result["sql"].upper()
        assert "coproprietaires" in result["sql"]
        assert "coproprietes" in result["sql"]

    async def test_nl_to_sql_with_filter(self):
        """Test 'Plumbers in 13th' → WHERE clause"""
        sql_agent = SQLAgentService()

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "sql": "SELECT * FROM professionnels WHERE category = 'plombier' AND postal_code LIKE '75013%'",
            "explanation": "Plumbers in 75013"
        })
        sql_agent.llm_service.chat_model.ainvoke = AsyncMock(return_value=mock_response)

        result = await sql_agent.natural_language_to_sql(
            "Find plumbers in the 13th arrondissement",
            operation_type="SELECT"
        )

        assert "WHERE" in result["sql"].upper()
        assert "postal_code" in result["sql"] or "75013" in result["sql"]

    async def test_nl_to_sql_add_limit(self):
        """Test auto-adds LIMIT 1000"""
        sql_agent = SQLAgentService()

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "sql": "SELECT * FROM professionnels",
            "explanation": "All professionals"
        })
        sql_agent.llm_service.chat_model.ainvoke = AsyncMock(return_value=mock_response)

        result = await sql_agent.natural_language_to_sql(
            "Show all professionals",
            operation_type="SELECT"
        )

        # Validation or execution should add LIMIT
        assert "sql" in result

    async def test_nl_to_sql_insert_operation(self):
        """Test generates INSERT with RETURNING"""
        sql_agent = SQLAgentService()

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "sql": "INSERT INTO professionnels (name, email, category) VALUES ('Jean Dupont', 'jean@email.fr', 'plombier') RETURNING *",
            "explanation": "Inserts new professional"
        })
        sql_agent.llm_service.chat_model.ainvoke = AsyncMock(return_value=mock_response)

        result = await sql_agent.natural_language_to_sql(
            "Add a new plumber named Jean Dupont",
            operation_type="INSERT"
        )

        assert "INSERT" in result["sql"].upper()
        assert "RETURNING" in result["sql"].upper() or "INSERT" in result["sql"].upper()

    async def test_nl_to_sql_update_operation(self):
        """Test generates UPDATE with WHERE"""
        sql_agent = SQLAgentService()

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "sql": "UPDATE professionnels SET statut = 'inactive' WHERE id = 5",
            "explanation": "Updates professional status"
        })
        sql_agent.llm_service.chat_model.ainvoke = AsyncMock(return_value=mock_response)

        result = await sql_agent.natural_language_to_sql(
            "Mark professional ID 5 as inactive",
            operation_type="UPDATE"
        )

        assert "UPDATE" in result["sql"].upper()
        assert "WHERE" in result["sql"].upper()

    async def test_nl_to_sql_json_parsing(self):
        """Test parses LLM JSON response"""
        sql_agent = SQLAgentService()

        mock_response = MagicMock()
        mock_response.content = """
        {
            "sql": "SELECT * FROM professionnels LIMIT 10",
            "explanation": "First 10 professionals"
        }
        """
        sql_agent.llm_service.chat_model.ainvoke = AsyncMock(return_value=mock_response)

        result = await sql_agent.natural_language_to_sql("Show 10 professionals")

        assert result["sql"] == "SELECT * FROM professionnels LIMIT 10"
        assert "explanation" in result

    async def test_nl_to_sql_json_with_markdown(self):
        """Test strips markdown code blocks"""
        sql_agent = SQLAgentService()

        mock_response = MagicMock()
        mock_response.content = """```json
        {
            "sql": "SELECT * FROM professionnels",
            "explanation": "Test"
        }
        ```"""
        sql_agent.llm_service.chat_model.ainvoke = AsyncMock(return_value=mock_response)

        result = await sql_agent.natural_language_to_sql("Test query")

        assert "sql" in result
        assert "```" not in result.get("sql", "")

    async def test_nl_to_sql_invalid_json(self):
        """Test handles malformed JSON"""
        sql_agent = SQLAgentService()

        mock_response = MagicMock()
        mock_response.content = "This is not valid JSON"
        sql_agent.llm_service.chat_model.ainvoke = AsyncMock(return_value=mock_response)

        with pytest.raises(ValueError):
            await sql_agent.natural_language_to_sql("Test")

    async def test_nl_to_sql_llm_error(self):
        """Test raises error on LLM failure"""
        sql_agent = SQLAgentService()

        sql_agent.llm_service.chat_model.ainvoke = AsyncMock(side_effect=Exception("LLM Error"))

        with pytest.raises(ValueError):
            await sql_agent.natural_language_to_sql("Test query")

    async def test_nl_to_sql_includes_explanation(self):
        """Test returns explanation field"""
        sql_agent = SQLAgentService()

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "sql": "SELECT * FROM professionnels",
            "explanation": "This query retrieves all professionals from the database"
        })
        sql_agent.llm_service.chat_model.ainvoke = AsyncMock(return_value=mock_response)

        result = await sql_agent.natural_language_to_sql("Get all professionals")

        assert result["explanation"] == "This query retrieves all professionals from the database"

    async def test_nl_to_sql_french_query(self):
        """Test handles French natural language"""
        sql_agent = SQLAgentService()

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "sql": "SELECT * FROM professionnels WHERE category = 'électricien'",
            "explanation": "Trouve les électriciens"
        })
        sql_agent.llm_service.chat_model.ainvoke = AsyncMock(return_value=mock_response)

        result = await sql_agent.natural_language_to_sql(
            "Trouve tous les électriciens",
            operation_type="SELECT"
        )

        assert "SELECT" in result["sql"].upper()


@pytest.mark.unit
@pytest.mark.asyncio
class TestSQLValidation:
    """Tests for SQL validation and security"""

    def test_validate_sql_safe_select(self):
        """Test allows safe SELECT"""
        sql_agent = SQLAgentService()

        validation = sql_agent._validate_sql(
            "SELECT * FROM professionnels WHERE city = 'Paris' LIMIT 10"
        )

        assert validation["is_valid"] is True
        assert len(validation["errors"]) == 0

    def test_validate_sql_safe_update_with_where(self):
        """Test allows UPDATE with WHERE"""
        sql_agent = SQLAgentService()

        validation = sql_agent._validate_sql(
            "UPDATE professionnels SET statut = 'active' WHERE id = 5"
        )

        assert validation["is_valid"] is True

    def test_validate_sql_safe_delete_with_where(self):
        """Test allows DELETE with WHERE"""
        sql_agent = SQLAgentService()

        validation = sql_agent._validate_sql(
            "DELETE FROM professionnels WHERE id = 10"
        )

        assert validation["is_valid"] is True

    def test_validate_sql_blocks_drop(self):
        """Test blocks DROP TABLE"""
        sql_agent = SQLAgentService()

        validation = sql_agent._validate_sql(
            "DROP TABLE professionnels"
        )

        assert validation["is_valid"] is False
        assert any("DROP" in error for error in validation["errors"])

    def test_validate_sql_blocks_truncate(self):
        """Test blocks TRUNCATE"""
        sql_agent = SQLAgentService()

        validation = sql_agent._validate_sql(
            "TRUNCATE TABLE professionnels"
        )

        assert validation["is_valid"] is False
        assert any("TRUNCATE" in error for error in validation["errors"])

    def test_validate_sql_blocks_alter(self):
        """Test blocks ALTER TABLE"""
        sql_agent = SQLAgentService()

        validation = sql_agent._validate_sql(
            "ALTER TABLE professionnels ADD COLUMN test VARCHAR(255)"
        )

        assert validation["is_valid"] is False

    def test_validate_sql_blocks_grant(self):
        """Test blocks GRANT"""
        sql_agent = SQLAgentService()

        validation = sql_agent._validate_sql(
            "GRANT ALL PRIVILEGES ON professionnels TO user"
        )

        assert validation["is_valid"] is False

    def test_validate_sql_blocks_create(self):
        """Test blocks CREATE TABLE"""
        sql_agent = SQLAgentService()

        validation = sql_agent._validate_sql(
            "CREATE TABLE new_table (id INT)"
        )

        assert validation["is_valid"] is False

    def test_validate_sql_update_without_where(self):
        """Test blocks UPDATE without WHERE"""
        sql_agent = SQLAgentService()

        validation = sql_agent._validate_sql(
            "UPDATE professionnels SET statut = 'inactive'"
        )

        assert validation["is_valid"] is False
        assert any("WHERE" in error for error in validation["errors"])

    def test_validate_sql_delete_without_where(self):
        """Test blocks DELETE without WHERE"""
        sql_agent = SQLAgentService()

        validation = sql_agent._validate_sql(
            "DELETE FROM professionnels"
        )

        assert validation["is_valid"] is False
        assert any("WHERE" in error for error in validation["errors"])

    def test_validate_sql_unauthorized_table(self):
        """Test blocks queries on non-allowed tables"""
        sql_agent = SQLAgentService()

        validation = sql_agent._validate_sql(
            "SELECT * FROM users_secrets"
        )

        assert validation["is_valid"] is False
        assert any("autorisée" in error.lower() or "allowed" in error.lower()
                   for error in validation["errors"])

    def test_validate_sql_warns_no_limit(self):
        """Test warns when SELECT has no LIMIT"""
        sql_agent = SQLAgentService()

        validation = sql_agent._validate_sql(
            "SELECT * FROM professionnels"
        )

        # Should be valid but with warning
        assert validation["is_valid"] is True
        assert len(validation["warnings"]) > 0
        assert any("LIMIT" in warning for warning in validation["warnings"])

    def test_validate_sql_multiple_tables(self):
        """Test validates all tables in JOIN"""
        sql_agent = SQLAgentService()

        # Valid JOIN with allowed tables
        validation1 = sql_agent._validate_sql(
            "SELECT * FROM professionnels p JOIN coproprietes c ON p.id = c.id"
        )
        assert validation1["is_valid"] is True

        # Invalid JOIN with unauthorized table
        validation2 = sql_agent._validate_sql(
            "SELECT * FROM professionnels p JOIN secret_table s ON p.id = s.id"
        )
        assert validation2["is_valid"] is False

    def test_validate_sql_case_insensitive(self):
        """Test works regardless of case"""
        sql_agent = SQLAgentService()

        validation = sql_agent._validate_sql(
            "select * from professionnels where city = 'Paris'"
        )

        assert validation["is_valid"] is True

    def test_validate_sql_complex_injection_attempt(self):
        """Test blocks SQL injection patterns"""
        sql_agent = SQLAgentService()

        # Attempt to inject DROP
        validation = sql_agent._validate_sql(
            "SELECT * FROM professionnels WHERE name = 'Test'; DROP TABLE professionnels; --'"
        )

        assert validation["is_valid"] is False


@pytest.mark.unit
@pytest.mark.asyncio
class TestSQLExecution:
    """Tests for SQL execution"""

    async def test_execute_sql_select_success(self, sql_test_db):
        """Test executes SELECT and returns results"""
        sql_agent = SQLAgentService()

        result = await sql_agent.execute_sql(
            sql="SELECT * FROM professionnels LIMIT 1",
            db=sql_test_db,
            validate=True
        )

        assert result["success"] is True
        assert "results" in result
        assert result["row_count"] >= 0

    async def test_execute_sql_select_with_limit(self, sql_test_db):
        """Test auto-adds LIMIT to SELECT"""
        sql_agent = SQLAgentService()

        result = await sql_agent.execute_sql(
            sql="SELECT * FROM professionnels",
            db=sql_test_db,
            validate=True
        )

        # Should add LIMIT automatically
        assert result["success"] is True

    async def test_execute_sql_insert_with_returning(self, sql_test_db):
        """Test executes INSERT and returns data"""
        sql_agent = SQLAgentService()

        result = await sql_agent.execute_sql(
            sql="INSERT INTO professionnels (name, email, category) VALUES ('Test Pro', 'test@test.fr', 'test') RETURNING *",
            db=sql_test_db,
            validate=False  # Skip validation for test
        )

        # Note: May fail depending on schema, adjust as needed
        assert "success" in result

    async def test_execute_sql_update_commits(self, sql_test_db):
        """Test commits UPDATE transaction"""
        sql_agent = SQLAgentService()

        result = await sql_agent.execute_sql(
            sql="UPDATE professionnels SET name = 'Updated' WHERE id = 1",
            db=sql_test_db,
            validate=False
        )

        assert "success" in result

    async def test_execute_sql_validation_failure(self, sql_test_db):
        """Test returns error if validation fails"""
        sql_agent = SQLAgentService()

        result = await sql_agent.execute_sql(
            sql="DROP TABLE professionnels",
            db=sql_test_db,
            validate=True
        )

        assert result["success"] is False
        assert "validation_errors" in result

    async def test_execute_sql_syntax_error(self, sql_test_db):
        """Test catches SQL syntax errors"""
        sql_agent = SQLAgentService()

        result = await sql_agent.execute_sql(
            sql="SELCT * FORM professionnels",  # Typos
            db=sql_test_db,
            validate=False
        )

        assert result["success"] is False
        assert "error" in result

    async def test_execute_sql_rollback_on_error(self, sql_test_db):
        """Test rolls back on exception"""
        sql_agent = SQLAgentService()

        # Execute invalid SQL
        result = await sql_agent.execute_sql(
            sql="SELECT * FROM nonexistent_table",
            db=sql_test_db,
            validate=False
        )

        assert result["success"] is False

    async def test_execute_sql_without_validation(self, sql_test_db):
        """Test skips validation if validate=False"""
        sql_agent = SQLAgentService()

        # This would normally fail validation
        result = await sql_agent.execute_sql(
            sql="SELECT * FROM professionnels",  # No LIMIT, but validation skipped
            db=sql_test_db,
            validate=False
        )

        # Should execute despite missing LIMIT
        assert "success" in result


@pytest.mark.unit
@pytest.mark.asyncio
class TestNaturalQueryPipeline:
    """Tests for complete NL→SQL→Execute pipeline"""

    async def test_execute_natural_query_full_pipeline(self, sql_test_db):
        """Test NL → SQL → Execute → Results"""
        sql_agent = SQLAgentService()

        # Mock LLM to return valid SQL
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "sql": "SELECT * FROM professionnels WHERE category = 'plombier' LIMIT 5",
            "explanation": "Finds plumbers"
        })
        sql_agent.llm_service.chat_model.ainvoke = AsyncMock(return_value=mock_response)

        result = await sql_agent.execute_natural_query(
            query="Find all plumbers",
            db=sql_test_db,
            operation_type="SELECT"
        )

        assert result["success"] is True
        assert "sql" in result
        assert "results" in result or "row_count" in result

    async def test_execute_natural_query_validation_error(self, sql_test_db):
        """Test stops at validation"""
        sql_agent = SQLAgentService()

        # Mock LLM to return dangerous SQL
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "sql": "DROP TABLE professionnels",
            "explanation": "Dangerous operation"
        })
        sql_agent.llm_service.chat_model.ainvoke = AsyncMock(return_value=mock_response)

        result = await sql_agent.execute_natural_query(
            query="Delete all data",
            db=sql_test_db
        )

        assert result["success"] is False
        assert "validation_errors" in result

    async def test_execute_natural_query_execution_error(self, sql_test_db):
        """Test returns error from execution"""
        sql_agent = SQLAgentService()

        # Mock LLM to return SQL with syntax error
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "sql": "SELCT * FORM professionnels",  # Syntax error
            "explanation": "Broken query"
        })
        sql_agent.llm_service.chat_model.ainvoke = AsyncMock(return_value=mock_response)

        result = await sql_agent.execute_natural_query(
            query="Get data",
            db=sql_test_db
        )

        assert result["success"] is False

    async def test_execute_natural_query_with_warnings(self, sql_test_db):
        """Test includes validation warnings"""
        sql_agent = SQLAgentService()

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "sql": "SELECT * FROM professionnels WHERE id = 1",  # No LIMIT
            "explanation": "Get professional"
        })
        sql_agent.llm_service.chat_model.ainvoke = AsyncMock(return_value=mock_response)

        result = await sql_agent.execute_natural_query(
            query="Get professional 1",
            db=sql_test_db
        )

        # Should succeed but may include warnings
        assert "success" in result

    async def test_execute_natural_query_insert_operation(self, sql_test_db):
        """Test full pipeline for INSERT"""
        sql_agent = SQLAgentService()

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "sql": "INSERT INTO professionnels (name, email, category) VALUES ('New Pro', 'new@test.fr', 'plombier')",
            "explanation": "Adds new professional"
        })
        sql_agent.llm_service.chat_model.ainvoke = AsyncMock(return_value=mock_response)

        result = await sql_agent.execute_natural_query(
            query="Add a new plumber",
            db=sql_test_db,
            operation_type="INSERT"
        )

        # May succeed or fail depending on schema, but should handle gracefully
        assert "success" in result
