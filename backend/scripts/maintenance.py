"""
DisruptIQ Maintenance Script

Comprehensive maintenance utility for backup, health monitoring, and log rotation.

Usage:
    python scripts/maintenance.py backup [--output /path/to/backup]
    python scripts/maintenance.py health [--detailed]
    python scripts/maintenance.py monitor [--interval 60]
    python scripts/maintenance.py rotate-logs [--days 30]
    python scripts/maintenance.py cleanup [--dry-run]
"""

import os
import sys
import argparse
import asyncio
import json
import shutil
import tarfile
import gzip
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import subprocess

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import aiohttp
    import psycopg2
    from psycopg2.extensions import connection
except ImportError:
    print("⚠️  Required packages not installed. Run: pip install aiohttp psycopg2-binary")
    sys.exit(1)


class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str):
    """Print formatted header"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}{Colors.ENDC}\n")


def print_success(text: str):
    """Print success message"""
    print(f"{Colors.OKGREEN}✅ {text}{Colors.ENDC}")


def print_warning(text: str):
    """Print warning message"""
    print(f"{Colors.WARNING}⚠️  {text}{Colors.ENDC}")


def print_error(text: str):
    """Print error message"""
    print(f"{Colors.FAIL}❌ {text}{Colors.ENDC}")


def print_info(text: str):
    """Print info message"""
    print(f"{Colors.OKCYAN}ℹ️  {text}{Colors.ENDC}")


# ============================================================================
# BACKUP FUNCTIONS
# ============================================================================

def backup_database(output_dir: Path) -> Optional[Path]:
    """
    Backup PostgreSQL database

    Returns:
        Path to backup file or None if failed
    """
    print_info("Backing up PostgreSQL database...")

    try:
        # Get database URL from environment
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            print_error("DATABASE_URL not set in environment")
            return None

        # Parse database URL
        # Format: postgresql+asyncpg://user:pass@host:port/dbname
        parts = db_url.replace("postgresql+asyncpg://", "").split("@")
        if len(parts) != 2:
            print_error("Invalid DATABASE_URL format")
            return None

        user_pass = parts[0].split(":")
        host_db = parts[1].split("/")

        user = user_pass[0]
        password = user_pass[1] if len(user_pass) > 1 else ""
        host_port = host_db[0].split(":")
        host = host_port[0]
        port = host_port[1] if len(host_port) > 1 else "5432"
        dbname = host_db[1].split("?")[0] if len(host_db) > 1 else "disruptiq"

        # Generate backup filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = output_dir / f"database_backup_{timestamp}.sql.gz"

        # Set PGPASSWORD environment variable
        env = os.environ.copy()
        env["PGPASSWORD"] = password

        # Run pg_dump
        dump_cmd = [
            "pg_dump",
            "-h", host,
            "-p", port,
            "-U", user,
            "-d", dbname,
            "--no-owner",
            "--no-acl",
            "-F", "p"  # Plain text format
        ]

        print_info(f"Running pg_dump for database '{dbname}'...")

        with gzip.open(backup_file, 'wb') as f:
            result = subprocess.run(
                dump_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env
            )

            if result.returncode != 0:
                print_error(f"pg_dump failed: {result.stderr.decode()}")
                return None

            f.write(result.stdout)

        file_size_mb = backup_file.stat().st_size / (1024 * 1024)
        print_success(f"Database backup created: {backup_file} ({file_size_mb:.2f} MB)")
        return backup_file

    except Exception as e:
        print_error(f"Database backup failed: {str(e)}")
        return None


def backup_uploads(output_dir: Path) -> Optional[Path]:
    """
    Backup uploads directory

    Returns:
        Path to backup file or None if failed
    """
    print_info("Backing up uploads directory...")

    try:
        uploads_dir = Path(__file__).parent.parent / "uploads"

        if not uploads_dir.exists():
            print_warning("Uploads directory does not exist, skipping...")
            return None

        # Generate backup filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = output_dir / f"uploads_backup_{timestamp}.tar.gz"

        # Create tar.gz archive
        with tarfile.open(backup_file, "w:gz") as tar:
            tar.add(uploads_dir, arcname="uploads")

        file_size_mb = backup_file.stat().st_size / (1024 * 1024)
        file_count = sum(1 for _ in uploads_dir.rglob("*") if _.is_file())

        print_success(f"Uploads backup created: {backup_file} ({file_size_mb:.2f} MB, {file_count} files)")
        return backup_file

    except Exception as e:
        print_error(f"Uploads backup failed: {str(e)}")
        return None


async def backup_qdrant(output_dir: Path) -> Optional[Path]:
    """
    Backup Qdrant vector database snapshots

    Returns:
        Path to backup file or None if failed
    """
    print_info("Backing up Qdrant vector database...")

    try:
        qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        collection_name = os.getenv("QDRANT_COLLECTION", "disruptiq_documents")

        async with aiohttp.ClientSession() as session:
            # Create snapshot
            snapshot_url = f"{qdrant_url}/collections/{collection_name}/snapshots"

            async with session.post(snapshot_url) as response:
                if response.status != 200:
                    print_error(f"Failed to create Qdrant snapshot: {response.status}")
                    return None

                snapshot_data = await response.json()
                snapshot_name = snapshot_data.get("result", {}).get("name")

                if not snapshot_name:
                    print_error("Snapshot name not found in response")
                    return None

            # Download snapshot
            download_url = f"{qdrant_url}/collections/{collection_name}/snapshots/{snapshot_name}"

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = output_dir / f"qdrant_snapshot_{timestamp}.snapshot"

            async with session.get(download_url) as response:
                if response.status != 200:
                    print_error(f"Failed to download Qdrant snapshot: {response.status}")
                    return None

                with open(backup_file, 'wb') as f:
                    f.write(await response.read())

            file_size_mb = backup_file.stat().st_size / (1024 * 1024)
            print_success(f"Qdrant backup created: {backup_file} ({file_size_mb:.2f} MB)")
            return backup_file

    except Exception as e:
        print_error(f"Qdrant backup failed: {str(e)}")
        return None


def run_backup(args):
    """Run full backup"""
    print_header("🔄 DisruptIQ Backup")

    # Create backup directory
    if args.output:
        backup_dir = Path(args.output)
    else:
        backup_dir = Path(__file__).parent.parent / "backups" / datetime.now().strftime("%Y%m%d_%H%M%S")

    backup_dir.mkdir(parents=True, exist_ok=True)
    print_info(f"Backup directory: {backup_dir}")

    # Run backups
    results = {
        "timestamp": datetime.now().isoformat(),
        "backup_dir": str(backup_dir),
        "backups": {}
    }

    # Database backup
    db_backup = backup_database(backup_dir)
    results["backups"]["database"] = str(db_backup) if db_backup else None

    # Uploads backup
    uploads_backup = backup_uploads(backup_dir)
    results["backups"]["uploads"] = str(uploads_backup) if uploads_backup else None

    # Qdrant backup
    qdrant_backup = asyncio.run(backup_qdrant(backup_dir))
    results["backups"]["qdrant"] = str(qdrant_backup) if qdrant_backup else None

    # Save backup manifest
    manifest_file = backup_dir / "backup_manifest.json"
    with open(manifest_file, 'w') as f:
        json.dump(results, f, indent=2)

    print_success(f"Backup manifest saved: {manifest_file}")

    # Summary
    print_header("📊 Backup Summary")
    successful = sum(1 for v in results["backups"].values() if v is not None)
    total = len(results["backups"])

    print(f"  Successful: {successful}/{total}")
    print(f"  Location: {backup_dir}")

    if successful == total:
        print_success("All backups completed successfully!")
    else:
        print_warning(f"Some backups failed. Check logs above.")


# ============================================================================
# HEALTH CHECK FUNCTIONS
# ============================================================================

async def check_api_health():
    """Check API health"""
    try:
        api_url = os.getenv("API_URL", "http://localhost:8000")

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{api_url}/health/detailed", timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    return {"status": "unhealthy", "error": f"HTTP {response.status}"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


def run_health_check(args):
    """Run health check"""
    print_header("🏥 DisruptIQ Health Check")

    health_data = asyncio.run(check_api_health())

    if health_data.get("status") == "healthy":
        print_success(f"System Status: {health_data['status'].upper()}")
    elif health_data.get("status") == "degraded":
        print_warning(f"System Status: {health_data['status'].upper()}")
    else:
        print_error(f"System Status: {health_data.get('status', 'UNKNOWN').upper()}")

    if args.detailed and "checks" in health_data:
        print("\n" + "="*60)
        print("Component Health:")
        print("="*60 + "\n")

        for component, status_data in health_data["checks"].items():
            status = status_data.get("status", "unknown")
            message = status_data.get("message", "")

            if status == "healthy":
                print_success(f"{component:15s} : {status:10s} - {message}")
            elif status == "degraded":
                print_warning(f"{component:15s} : {status:10s} - {message}")
            elif status == "disabled" or status == "not_implemented":
                print_info(f"{component:15s} : {status:15s} - {message}")
            else:
                print_error(f"{component:15s} : {status:10s} - {message}")


def run_monitor(args):
    """Run continuous monitoring"""
    print_header("📊 DisruptIQ Monitor")
    print_info(f"Monitoring interval: {args.interval}s (Ctrl+C to stop)")

    try:
        while True:
            health_data = asyncio.run(check_api_health())
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            status = health_data.get("status", "unknown")

            if status == "healthy":
                print(f"{timestamp} - {Colors.OKGREEN}●{Colors.ENDC} System Healthy")
            elif status == "degraded":
                print(f"{timestamp} - {Colors.WARNING}●{Colors.ENDC} System Degraded")
            else:
                print(f"{timestamp} - {Colors.FAIL}●{Colors.ENDC} System Unhealthy")

            import time
            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\n")
        print_info("Monitoring stopped")


# ============================================================================
# LOG ROTATION FUNCTIONS
# ============================================================================

def rotate_logs(args):
    """Rotate log files"""
    print_header("🔄 Log Rotation")

    logs_dir = Path(__file__).parent.parent / "logs"

    if not logs_dir.exists():
        print_warning("Logs directory does not exist")
        return

    # Find log files older than specified days
    cutoff_date = datetime.now() - timedelta(days=args.days)
    archived = 0
    deleted = 0

    for log_file in logs_dir.glob("*.log"):
        file_time = datetime.fromtimestamp(log_file.stat().st_mtime)

        if file_time < cutoff_date:
            # Compress and archive
            archive_name = log_file.with_suffix(f".log.{file_time.strftime('%Y%m%d')}.gz")

            with open(log_file, 'rb') as f_in:
                with gzip.open(archive_name, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)

            # Delete original
            log_file.unlink()
            archived += 1
            print_info(f"Archived: {log_file.name} → {archive_name.name}")

    # Delete very old archives (> 90 days)
    old_cutoff = datetime.now() - timedelta(days=90)

    for archive_file in logs_dir.glob("*.log.*.gz"):
        file_time = datetime.fromtimestamp(archive_file.stat().st_mtime)

        if file_time < old_cutoff:
            archive_file.unlink()
            deleted += 1
            print_info(f"Deleted old archive: {archive_file.name}")

    print_success(f"Log rotation complete: {archived} archived, {deleted} deleted")


# ============================================================================
# CLEANUP FUNCTIONS
# ============================================================================

def cleanup_temp_files(args):
    """Clean up temporary files"""
    print_header("🧹 Cleanup Temporary Files")

    # Directories to clean
    temp_dirs = [
        Path(__file__).parent.parent / "__pycache__",
        Path(__file__).parent.parent / ".pytest_cache",
        Path(__file__).parent.parent / "htmlcov",
    ]

    # Files to clean
    temp_files = [
        Path(__file__).parent.parent / ".coverage",
        Path(__file__).parent.parent / "coverage.xml",
        Path(__file__).parent.parent / "coverage.json",
    ]

    total_removed = 0

    for temp_dir in temp_dirs:
        if temp_dir.exists():
            if args.dry_run:
                print_info(f"Would remove: {temp_dir}")
            else:
                shutil.rmtree(temp_dir)
                print_success(f"Removed: {temp_dir}")
            total_removed += 1

    for temp_file in temp_files:
        if temp_file.exists():
            if args.dry_run:
                print_info(f"Would remove: {temp_file}")
            else:
                temp_file.unlink()
                print_success(f"Removed: {temp_file}")
            total_removed += 1

    if args.dry_run:
        print_warning(f"Dry run: {total_removed} items would be removed")
    else:
        print_success(f"Cleanup complete: {total_removed} items removed")


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="DisruptIQ Maintenance Utility",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Backup command
    backup_parser = subparsers.add_parser("backup", help="Backup database, uploads, and Qdrant")
    backup_parser.add_argument("--output", "-o", help="Output directory for backups")

    # Health command
    health_parser = subparsers.add_parser("health", help="Check system health")
    health_parser.add_argument("--detailed", "-d", action="store_true", help="Show detailed health information")

    # Monitor command
    monitor_parser = subparsers.add_parser("monitor", help="Continuous health monitoring")
    monitor_parser.add_argument("--interval", "-i", type=int, default=60, help="Monitoring interval in seconds")

    # Rotate logs command
    rotate_parser = subparsers.add_parser("rotate-logs", help="Rotate log files")
    rotate_parser.add_argument("--days", "-d", type=int, default=30, help="Archive logs older than N days")

    # Cleanup command
    cleanup_parser = subparsers.add_parser("cleanup", help="Clean up temporary files")
    cleanup_parser.add_argument("--dry-run", action="store_true", help="Show what would be removed without removing")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Run command
    if args.command == "backup":
        run_backup(args)
    elif args.command == "health":
        run_health_check(args)
    elif args.command == "monitor":
        run_monitor(args)
    elif args.command == "rotate-logs":
        rotate_logs(args)
    elif args.command == "cleanup":
        cleanup_temp_files(args)


if __name__ == "__main__":
    main()
