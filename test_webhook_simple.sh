#!/bin/bash
# Test webhook simple
echo "Testing N8N webhook..."
curl -X POST http://localhost:5678/webhook/emergency-water-leak \
  -H "Content-Type: application/json" \
  -d '{"test":"hello"}' \
  -v
