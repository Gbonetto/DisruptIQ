"""
Tests for N8N Workflow Service
"""

import pytest
from pathlib import Path
from app.services.n8n_workflow_service import (
    N8NWorkflowService,
    DangerLevel,
    WorkflowCategory,
    WorkflowExecutionRequest
)


class TestN8NWorkflowService:
    """Test suite for N8N Workflow Service"""

    @pytest.fixture
    def service(self):
        """Create service instance"""
        return N8NWorkflowService()

    def test_service_initialization(self, service):
        """Test service initializes and loads workflows"""
        assert service is not None
        assert service.workflows is not None
        assert len(service.workflows) > 0

    def test_workflows_loaded(self, service):
        """Test that workflows.yaml is loaded"""
        # Should have at least 9 workflows declared
        assert len(service.workflows) >= 9

        # Check some known workflows
        assert "incident_water_damage" in service.workflows
        assert "send_ag_convocation" in service.workflows
        assert "archive_old_documents" in service.workflows

    def test_get_workflow(self, service):
        """Test get_workflow by ID"""
        workflow = service.get_workflow("incident_water_damage")

        assert workflow is not None
        assert workflow.id == "incident_water_damage"
        assert workflow.name == "Incident dégât des eaux"
        assert workflow.danger_level == DangerLevel.HIGH
        assert workflow.requires_confirmation is True
        assert workflow.dry_run_supported is True

    def test_get_workflow_not_found(self, service):
        """Test get_workflow with invalid ID"""
        workflow = service.get_workflow("non_existent_workflow")
        assert workflow is None

    def test_list_workflows_no_filter(self, service):
        """Test list all workflows"""
        workflows = service.list_workflows()
        assert len(workflows) >= 9

    def test_list_workflows_by_category(self, service):
        """Test list workflows filtered by category"""
        emergency_workflows = service.list_workflows(category=WorkflowCategory.EMERGENCY)

        assert len(emergency_workflows) > 0
        for wf in emergency_workflows:
            assert wf.category == WorkflowCategory.EMERGENCY

    def test_list_workflows_by_danger_level(self, service):
        """Test list workflows filtered by danger level"""
        high_danger = service.list_workflows(danger_level=DangerLevel.HIGH)

        assert len(high_danger) >= 3  # We declared 3 HIGH danger workflows
        for wf in high_danger:
            assert wf.danger_level == DangerLevel.HIGH

    def test_validate_inputs_success(self, service):
        """Test input validation success"""
        workflow = service.get_workflow("incident_water_damage")

        inputs = {
            "copropriete_id": 1,
            "lot_numbers": ["12", "13"],
            "severity": "high",
            "description": "Important water damage in building A"
        }

        is_valid, errors = service.validate_inputs(workflow, inputs)

        assert is_valid is True
        assert len(errors) == 0

    def test_validate_inputs_missing_required(self, service):
        """Test input validation with missing required field"""
        workflow = service.get_workflow("incident_water_damage")

        inputs = {
            "lot_numbers": ["12"],
            "severity": "high"
            # Missing: copropriete_id, description
        }

        is_valid, errors = service.validate_inputs(workflow, inputs)

        assert is_valid is False
        assert len(errors) >= 2
        assert any("copropriete_id" in err for err in errors)

    def test_validate_inputs_wrong_type(self, service):
        """Test input validation with wrong type"""
        workflow = service.get_workflow("incident_water_damage")

        inputs = {
            "copropriete_id": "not_an_integer",  # Should be integer
            "lot_numbers": ["12"],
            "severity": "high",
            "description": "Test"
        }

        is_valid, errors = service.validate_inputs(workflow, inputs)

        assert is_valid is False
        assert any("type invalide" in err for err in errors)

    def test_validate_inputs_enum_constraint(self, service):
        """Test input validation with enum constraint"""
        workflow = service.get_workflow("incident_water_damage")

        inputs = {
            "copropriete_id": 1,
            "lot_numbers": ["12"],
            "severity": "invalid_severity",  # Should be low|medium|high|critical
            "description": "Test"
        }

        is_valid, errors = service.validate_inputs(workflow, inputs)

        assert is_valid is False
        assert any("severity" in err for err in errors)

    def test_validate_inputs_min_constraint(self, service):
        """Test input validation with min constraint"""
        workflow = service.get_workflow("incident_water_damage")

        inputs = {
            "copropriete_id": 0,  # Min is 1
            "lot_numbers": ["12"],
            "severity": "high",
            "description": "Test"
        }

        is_valid, errors = service.validate_inputs(workflow, inputs)

        assert is_valid is False
        assert any("minimum" in err for err in errors)

    def test_validate_inputs_string_length(self, service):
        """Test input validation with string length constraint"""
        workflow = service.get_workflow("incident_water_damage")

        inputs = {
            "copropriete_id": 1,
            "lot_numbers": ["12"],
            "severity": "high",
            "description": "Short"  # Min length is 10
        }

        is_valid, errors = service.validate_inputs(workflow, inputs)

        assert is_valid is False
        assert any("longueur minimum" in err for err in errors)

    @pytest.mark.asyncio
    async def test_generate_preview(self, service):
        """Test preview generation"""
        inputs = {
            "copropriete_id": 1,
            "lot_numbers": ["12", "13", "14"],
            "severity": "high",
            "description": "Water damage in multiple apartments"
        }

        preview = await service.generate_preview(
            workflow_id="incident_water_damage",
            inputs=inputs,
            db=None  # No DB in unit test
        )

        assert preview is not None
        assert preview.workflow_id == "incident_water_damage"
        assert preview.danger_level == DangerLevel.HIGH
        assert preview.requires_confirmation is True
        assert len(preview.estimated_actions) > 0
        assert len(preview.warnings) > 0  # High danger should have warnings
        assert preview.preview_text != ""

    @pytest.mark.asyncio
    async def test_generate_preview_invalid_workflow(self, service):
        """Test preview generation with invalid workflow"""
        preview = await service.generate_preview(
            workflow_id="non_existent",
            inputs={}
        )

        assert preview is not None
        assert preview.can_execute is False
        assert len(preview.blocking_issues) > 0

    @pytest.mark.asyncio
    async def test_generate_preview_invalid_inputs(self, service):
        """Test preview generation with invalid inputs"""
        inputs = {
            "copropriete_id": "invalid"
        }

        preview = await service.generate_preview(
            workflow_id="incident_water_damage",
            inputs=inputs
        )

        assert preview is not None
        assert preview.can_execute is False
        assert len(preview.blocking_issues) > 0

    def test_workflow_timeout_configuration(self, service):
        """Test that workflows have proper timeout configuration"""
        for wf in service.workflows.values():
            assert wf.timeout_seconds >= 60
            assert wf.timeout_seconds <= 600

    def test_high_danger_workflows_require_confirmation(self, service):
        """Test that HIGH danger workflows require confirmation"""
        high_danger_workflows = service.list_workflows(danger_level=DangerLevel.HIGH)

        for wf in high_danger_workflows:
            assert wf.requires_confirmation is True

    def test_high_danger_workflows_support_dry_run(self, service):
        """Test that HIGH danger workflows support dry-run"""
        high_danger_workflows = service.list_workflows(danger_level=DangerLevel.HIGH)

        for wf in high_danger_workflows:
            assert wf.dry_run_supported is True

    def test_workflow_inputs_schema(self, service):
        """Test that workflows have properly defined inputs"""
        workflow = service.get_workflow("incident_water_damage")

        assert len(workflow.inputs) > 0

        # Check required fields
        required_inputs = [inp for inp in workflow.inputs if inp.required]
        assert len(required_inputs) > 0

        # Check validation schemas
        validated_inputs = [inp for inp in workflow.inputs if inp.validation]
        assert len(validated_inputs) > 0

    def test_workflow_outputs_schema(self, service):
        """Test that workflows have properly defined outputs"""
        workflow = service.get_workflow("incident_water_damage")

        assert len(workflow.outputs) > 0

        for output in workflow.outputs:
            assert output.name is not None
            assert output.type is not None

    def test_all_categories_represented(self, service):
        """Test that we have workflows in all categories"""
        categories = set()
        for wf in service.workflows.values():
            categories.add(wf.category)

        # Should have at least 4 different categories
        assert len(categories) >= 4

    def test_danger_level_distribution(self, service):
        """Test that we have workflows at different danger levels"""
        danger_levels = set()
        for wf in service.workflows.values():
            danger_levels.add(wf.danger_level)

        # Should have at least 3 different danger levels
        assert len(danger_levels) >= 3
        assert DangerLevel.LOW in danger_levels
        assert DangerLevel.MEDIUM in danger_levels
        assert DangerLevel.HIGH in danger_levels
