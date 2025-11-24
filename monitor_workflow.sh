#!/bin/bash
echo "🔍 Monitoring Emergency Workflows - Press Ctrl+C to stop"
echo "=========================================="
echo ""
docker-compose logs -f backend | grep --line-buffered -E "(emergency_workflow|n8n_thought|n8n_workflow|workflow_result)"
