#!/usr/bin/env python3
"""
HTTP Trigger Service for Digest
Runs on HOST (not in Docker) to trigger Gmail sync via HTTP.

This service allows the Docker backend to trigger Gmail sync without
network/SSL issues that occur when running Gmail API inside Docker.

Usage:
    python http_trigger.py

The service listens on port 5001 and exposes:
    POST /trigger-sync - Triggers v1.py to fetch emails from Gmail

Architecture:
    Docker Backend (8000) --> HTTP Trigger (5001) --> v1.py --> Gmail API
"""

import asyncio
import os
import sys
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import threading

# Add current directory and project root to path for imports
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..'))
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

# Import the digest service
from v1 import DigestService


class TriggerHandler(BaseHTTPRequestHandler):
    """HTTP request handler for trigger service"""

    def do_POST(self):
        """Handle POST requests"""
        if self.path == '/trigger-sync':
            self._handle_trigger_sync()
        else:
            self._send_json_response(404, {"error": "Not found"})

    def do_GET(self):
        """Handle GET requests"""
        if self.path == '/health':
            self._send_json_response(200, {
                "status": "healthy",
                "service": "digest-trigger",
                "timestamp": datetime.now().isoformat()
            })
        else:
            self._send_json_response(404, {"error": "Not found"})

    def _handle_trigger_sync(self):
        """Trigger the digest sync"""
        try:
            # Parse request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8') if content_length else '{}'
            params = json.loads(body) if body else {}

            since_hours = params.get('since_hours', 24)
            max_emails = params.get('max_emails', 100)

            print(f"[{datetime.now().strftime('%H:%M:%S')}] Trigger sync request: since_hours={since_hours}, max_emails={max_emails}")

            # Run the async digest generation
            result = asyncio.run(self._run_digest(since_hours, max_emails))

            self._send_json_response(200, {
                "status": "success",
                "emails_synced": result.get('total_emails', 0),
                "message": "Gmail sync completed",
                "details": {
                    "urgent": result.get('urgent', {}).get('count', 0),
                    "important": result.get('important', {}).get('count', 0),
                    "routine": result.get('routine', {}).get('count', 0)
                }
            })

        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Error: {str(e)}")
            self._send_json_response(500, {
                "status": "error",
                "message": str(e)
            })

    async def _run_digest(self, since_hours: int, max_emails: int):
        """Run the digest service"""
        service = DigestService()
        return await service.generate_digest(since_hours=since_hours, max_emails=max_emails)

    def _send_json_response(self, status_code: int, data: dict):
        """Send JSON response"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def log_message(self, format, *args):
        """Override to use custom logging format"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}")


def run_server(port: int = 5001):
    """Run the HTTP trigger server"""
    server_address = ('', port)
    httpd = HTTPServer(server_address, TriggerHandler)

    print("=" * 60)
    print("HTTP Trigger Service for DisruptIQ Digest")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Listening on: http://0.0.0.0:{port}")
    print(f"Health check: http://localhost:{port}/health")
    print(f"Trigger sync: POST http://localhost:{port}/trigger-sync")
    print("=" * 60)
    print("Press Ctrl+C to stop")
    print()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        httpd.shutdown()


if __name__ == "__main__":
    run_server(5001)
