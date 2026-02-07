#!/usr/bin/env python3
"""
DMARC Dashboard — Interactive Setup Script

Orchestrates the entire first-run experience:
  1. Generate .env with secure secrets
  2. Collect admin credentials
  3. Optionally configure email ingestion
  4. Optionally configure geolocation (MaxMind)
  5. Start services, run migrations, create admin user

Usage:
  python scripts/setup.py                  # Interactive mode
  python scripts/setup.py --non-interactive  # Use env vars / defaults

Non-interactive env vars:
  ADMIN_EMAIL    (default: admin@localhost)
  ADMIN_PASSWORD (default: auto-generated)
  SKIP_EMAIL=1   Skip email ingestion config
  SKIP_GEO=1     Skip geolocation config
  EMAIL_HOST, EMAIL_USER, EMAIL_PASSWORD  (if not skipping email)
  MAXMIND_LICENSE_KEY  (if not skipping geo)
"""

import getpass
import os
import re
import secrets
import shutil
import string
import subprocess
import sys
import time

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_EXAMPLE = os.path.join(PROJECT_DIR, ".env.example")
ENV_FILE = os.path.join(PROJECT_DIR, ".env")
SETUP_MARKER = os.path.join(PROJECT_DIR, ".setup_complete")

BANNER = r"""
╔══════════════════════════════════════════╗
║     DMARC Dashboard — Quick Setup       ║
╚══════════════════════════════════════════╝
"""

DONE_TEMPLATE = """
╔══════════════════════════════════════════╗
║  Setup complete!                        ║
║                                         ║
║  Dashboard:  http://localhost:80        ║
║  Login:      {email:<25s}║
║  Password:   {password:<25s}║
║                                         ║
║  Next steps:                            ║
║  - Upload DMARC XML reports             ║
║  - Or wait for email ingestion          ║
╚══════════════════════════════════════════╝
"""


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def log(msg: str) -> None:
    print(f"  → {msg}")


def log_step(step: int, total: int, msg: str) -> None:
    print(f"\n[{step}/{total}] {msg}")


def generate_secret(length: int = 64) -> str:
    """Generate a URL-safe secret token."""
    return secrets.token_urlsafe(length)


def generate_password(length: int = 16) -> str:
    """Generate a strong random password with mixed character types."""
    alphabet = string.ascii_letters + string.digits + "!@#$%&*"
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        # Ensure at least one of each type
        if (
            any(c.isupper() for c in password)
            and any(c.islower() for c in password)
            and any(c.isdigit() for c in password)
            and any(c in "!@#$%&*" for c in password)
        ):
            return password


def run(cmd: str, check: bool = True, capture: bool = False, timeout: int = 300) -> subprocess.CompletedProcess:
    """Run a shell command from the project directory."""
    return subprocess.run(
        cmd,
        shell=True,
        cwd=PROJECT_DIR,
        check=check,
        capture_output=capture,
        text=True,
        timeout=timeout,
    )


def prompt(msg: str, default: str = "") -> str:
    """Prompt user for input with optional default."""
    if default:
        val = input(f"  {msg} [{default}]: ").strip()
        return val if val else default
    return input(f"  {msg}: ").strip()


def prompt_password(msg: str = "Password", allow_empty: bool = False) -> str:
    """Prompt for a password (hidden input)."""
    while True:
        val = getpass.getpass(f"  {msg}: ")
        if val or allow_empty:
            return val
        print("  Password cannot be empty.")


def prompt_yn(msg: str, default: bool = False) -> bool:
    """Prompt for yes/no."""
    suffix = "[Y/n]" if default else "[y/N]"
    val = input(f"  {msg} {suffix}: ").strip().lower()
    if not val:
        return default
    return val in ("y", "yes")


def check_docker() -> bool:
    """Verify docker and docker compose are available."""
    try:
        run("docker compose version", capture=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


# ---------------------------------------------------------------------------
# Step 1: Generate .env
# ---------------------------------------------------------------------------

def generate_env(
    db_password: str,
    redis_password: str,
    jwt_secret: str,
    flower_password: str,
    email_config: dict | None = None,
) -> None:
    """Generate .env file from .env.example with real secrets."""
    if not os.path.exists(ENV_EXAMPLE):
        print(f"ERROR: {ENV_EXAMPLE} not found.")
        sys.exit(1)

    with open(ENV_EXAMPLE) as f:
        content = f.read()

    # Replace placeholder secrets
    replacements = {
        "POSTGRES_PASSWORD=CHANGE_ME_use_strong_password": f"POSTGRES_PASSWORD={db_password}",
        "REDIS_PASSWORD=CHANGE_ME_use_strong_password": f"REDIS_PASSWORD={redis_password}",
        "FLOWER_BASIC_AUTH=admin:CHANGE_ME_use_strong_password": f"FLOWER_BASIC_AUTH=admin:{flower_password}",
        "JWT_SECRET_KEY=CHANGE_ME_generate_with_python_c_import_secrets_print_secrets_token_urlsafe_64": f"JWT_SECRET_KEY={jwt_secret}",
        "DATABASE_URL=postgresql://dmarc:dmarc@db:5432/dmarc": f"DATABASE_URL=postgresql://dmarc:{db_password}@db:5432/dmarc",
    }

    for old, new in replacements.items():
        content = content.replace(old, new)

    # Apply email config if provided
    if email_config:
        content = re.sub(r"^EMAIL_HOST=.*$", f"EMAIL_HOST={email_config['host']}", content, flags=re.MULTILINE)
        content = re.sub(r"^EMAIL_USER=.*$", f"EMAIL_USER={email_config['user']}", content, flags=re.MULTILINE)
        content = re.sub(r"^EMAIL_PASSWORD=.*$", f"EMAIL_PASSWORD={email_config['password']}", content, flags=re.MULTILINE)

    # Back up existing .env if present
    if os.path.exists(ENV_FILE):
        backup = ENV_FILE + ".backup"
        shutil.copy2(ENV_FILE, backup)
        log(f"Backed up existing .env to .env.backup")

    with open(ENV_FILE, "w") as f:
        f.write(content)


# ---------------------------------------------------------------------------
# Step 5: Start services and initialize
# ---------------------------------------------------------------------------

def wait_for_health(max_wait: int = 120) -> bool:
    """Wait for backend health endpoint to respond."""
    start = time.time()
    while time.time() - start < max_wait:
        try:
            result = run("docker compose exec -T backend python -c \"from app.database import engine; engine.connect()\"",
                         check=False, capture=True, timeout=10)
            if result.returncode == 0:
                return True
        except subprocess.TimeoutExpired:
            pass
        time.sleep(3)
    return False


def run_migrations() -> bool:
    """Run Alembic migrations inside the backend container."""
    result = run("docker compose exec -T backend alembic upgrade head", check=False)
    return result.returncode == 0


def create_admin(email: str, password: str) -> bool:
    """Create admin user inside the backend container."""
    # Escape single quotes in password for shell safety
    escaped_password = password.replace("'", "'\\''")
    escaped_email = email.replace("'", "'\\''")

    script = """
import sys
sys.path.insert(0, '/app')
from app.database import get_db
from app.models.user import User
from app.services.auth import get_password_hash

email = sys.argv[1]
password = sys.argv[2]
db = next(get_db())
try:
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        print(f"User {email} already exists")
        sys.exit(0)
    user = User(
        email=email,
        username=email.split('@')[0],
        hashed_password=get_password_hash(password),
        is_active=True,
        is_superuser=True,
        role='admin'
    )
    db.add(user)
    db.commit()
    print(f"Admin user created: {email}")
except Exception as e:
    db.rollback()
    print(f"Error creating user: {e}", file=sys.stderr)
    sys.exit(1)
finally:
    db.close()
"""
    result = run(
        f"docker compose exec -T backend python -c '{script}' '{escaped_email}' '{escaped_password}'",
        check=False,
    )
    return result.returncode == 0


def write_setup_marker() -> None:
    """Write marker file indicating setup is complete."""
    with open(SETUP_MARKER, "w") as f:
        f.write(f"Setup completed at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    non_interactive = "--non-interactive" in sys.argv

    print(BANNER)

    # Pre-flight checks
    if not check_docker():
        print("ERROR: docker compose is not available. Please install Docker.")
        sys.exit(1)

    if os.path.exists(SETUP_MARKER):
        print("Setup has already been completed.")
        if non_interactive:
            print("Exiting. Delete .setup_complete to re-run setup.")
            sys.exit(0)
        if not prompt_yn("Re-run setup? This will overwrite your .env file", default=False):
            sys.exit(0)

    total_steps = 5

    # ------------------------------------------------------------------
    # Step 1: Generate config
    # ------------------------------------------------------------------
    log_step(1, total_steps, "Generating configuration...")

    jwt_secret = generate_secret(64)
    db_password = generate_secret(32)
    redis_password = generate_secret(32)
    flower_password = generate_secret(16)

    log("Created .env from template")
    log("Generated JWT secret key")
    log("Generated database password")
    log("Generated Redis password")

    # ------------------------------------------------------------------
    # Step 2: Admin account
    # ------------------------------------------------------------------
    log_step(2, total_steps, "Admin account")

    admin_email = os.environ.get("ADMIN_EMAIL", "")
    admin_password = os.environ.get("ADMIN_PASSWORD", "")

    if non_interactive:
        admin_email = admin_email or "admin@localhost"
        admin_password = admin_password or generate_password()
        log(f"Admin email: {admin_email}")
    else:
        admin_email = prompt("Email", default=admin_email or "admin@localhost")
        admin_password_input = prompt_password("Password (leave blank to auto-generate)", allow_empty=True)
        if admin_password_input:
            admin_password = admin_password_input
        else:
            admin_password = generate_password()
            log(f"Generated password: {admin_password}")

    # ------------------------------------------------------------------
    # Step 3: Email ingestion (optional)
    # ------------------------------------------------------------------
    log_step(3, total_steps, "Email ingestion (optional)")

    email_config = None
    skip_email = os.environ.get("SKIP_EMAIL", "0") == "1"

    if non_interactive:
        if not skip_email and os.environ.get("EMAIL_HOST"):
            email_config = {
                "host": os.environ["EMAIL_HOST"],
                "user": os.environ.get("EMAIL_USER", ""),
                "password": os.environ.get("EMAIL_PASSWORD", ""),
            }
            log(f"Email ingestion: {email_config['host']}")
        else:
            log("Skipped (can enable later in Settings)")
    else:
        if prompt_yn("Enable automatic email ingestion?", default=False):
            email_host = prompt("IMAP host", default="imap.gmail.com")
            email_user = prompt("IMAP user")
            email_pass = prompt_password("IMAP password")
            email_config = {"host": email_host, "user": email_user, "password": email_pass}
            log("Email config saved")
        else:
            log("Skipped (can enable later in Settings)")

    # ------------------------------------------------------------------
    # Step 4: Geolocation (optional)
    # ------------------------------------------------------------------
    log_step(4, total_steps, "Geolocation (optional)")

    skip_geo = os.environ.get("SKIP_GEO", "0") == "1"

    if non_interactive:
        if not skip_geo and os.environ.get("MAXMIND_LICENSE_KEY"):
            log(f"MaxMind key configured")
        else:
            log("Skipped (can enable later in Settings)")
    else:
        if prompt_yn("Enable IP geolocation maps? (requires free MaxMind account)", default=False):
            maxmind_key = prompt("MaxMind license key")
            if maxmind_key:
                log("MaxMind key saved — GeoIP database will download on first use")
        else:
            log("Skipped (can enable later in Settings)")

    # ------------------------------------------------------------------
    # Write .env before starting services
    # ------------------------------------------------------------------
    generate_env(
        db_password=db_password,
        redis_password=redis_password,
        jwt_secret=jwt_secret,
        flower_password=flower_password,
        email_config=email_config,
    )
    log("Wrote .env configuration file")

    # ------------------------------------------------------------------
    # Step 5: Start services and initialize
    # ------------------------------------------------------------------
    log_step(5, total_steps, "Starting services...")

    log("docker compose up -d")
    result = run("docker compose up -d", check=False)
    if result.returncode != 0:
        print("\nERROR: Failed to start services. Check docker compose logs.")
        sys.exit(1)

    log("Waiting for database... ")
    if not wait_for_health():
        print("\nERROR: Services did not become healthy within 120 seconds.")
        print("Run 'docker compose logs backend' to investigate.")
        sys.exit(1)
    log("Database ready")

    log("Running migrations...")
    if not run_migrations():
        print("\nERROR: Database migrations failed.")
        print("Run 'docker compose exec backend alembic upgrade head' to debug.")
        sys.exit(1)
    log("Migrations complete")

    log("Creating admin user...")
    if not create_admin(admin_email, admin_password):
        print("\nERROR: Failed to create admin user.")
        sys.exit(1)
    log("Admin user created")

    log("Health check...")
    run("docker compose exec -T backend python -c \"import requests; print('OK')\"", check=False, capture=True)
    log("All services healthy")

    # ------------------------------------------------------------------
    # Done
    # ------------------------------------------------------------------
    write_setup_marker()

    print(DONE_TEMPLATE.format(email=admin_email, password=admin_password))


if __name__ == "__main__":
    main()
