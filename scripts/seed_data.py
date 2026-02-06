#!/usr/bin/env python3
"""
Seed the DMARC database with sample reports for development/testing.

Usage:
    docker compose exec backend python scripts/seed_data.py
"""

import hashlib
import os
import random
import sys
import uuid
from datetime import datetime, timedelta

# Add parent directory to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.dmarc import DmarcRecord, DmarcReport, IngestedReport

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://dmarc:dmarc@db:5432/dmarc")

DOMAINS = [
    "example.com",
    "acme-corp.com",
    "techstartup.io",
    "globalsales.net",
    "secure-mail.org",
    "mycompany.com",
    "enterprise.co",
]

ORGS = [
    "google.com",
    "outlook.com",
    "yahoo.com",
    "proofpoint.com",
    "mimecast.com",
    "barracuda.com",
    "cloudflare.com",
    "fastmail.com",
]

SOURCE_IPS = [
    "209.85.220.41",
    "209.85.220.42",
    "40.107.22.100",
    "40.107.22.101",
    "74.6.231.20",
    "74.6.231.21",
    "67.231.152.10",
    "91.220.42.83",
    "185.70.42.15",
    "198.51.100.50",
    "203.0.113.10",
    "203.0.113.25",
    "192.0.2.100",
    "192.0.2.200",
    # Some suspicious IPs
    "45.33.32.156",
    "185.220.101.1",
    "23.129.64.100",
]


def generate_reports(session, count=15):
    """Generate sample DMARC reports."""
    now = datetime.utcnow()
    created = 0

    for i in range(count):
        domain = random.choice(DOMAINS)
        org = random.choice(ORGS)
        days_ago = random.randint(1, 60)
        date_begin = now - timedelta(days=days_ago)
        date_end = date_begin + timedelta(hours=24)

        report_id_str = f"{org}!{domain}!{int(date_begin.timestamp())}!{int(date_end.timestamp())}"
        content_hash = hashlib.sha256(f"seed-{uuid.uuid4().hex}".encode()).hexdigest()

        # Create ingested report
        ingested = IngestedReport(
            message_id=f"<{uuid.uuid4().hex[:12]}@{org}>",
            received_at=date_end + timedelta(hours=random.randint(1, 12)),
            filename=f"{org}!{domain}!{int(date_begin.timestamp())}!{int(date_end.timestamp())}.xml.gz",
            content_hash=content_hash,
            file_size=random.randint(1024, 50000),
            storage_path=f"/app/import_reports/seed/{content_hash[:8]}.xml.gz",
            status="completed",
            created_at=now,
            updated_at=now,
        )
        session.add(ingested)
        session.flush()

        # Determine policy
        policies = ["none", "quarantine", "reject"]
        policy_weights = [0.4, 0.35, 0.25]
        policy = random.choices(policies, weights=policy_weights, k=1)[0]

        report = DmarcReport(
            ingested_report_id=ingested.id,
            report_id=report_id_str,
            org_name=org,
            email=f"noreply-dmarc@{org}",
            date_begin=date_begin,
            date_end=date_end,
            domain=domain,
            adkim=random.choice(["r", "s"]),
            aspf=random.choice(["r", "s"]),
            p=policy,
            sp=random.choice(["none", "quarantine", "reject"]),
            pct=100,
            created_at=now,
        )
        session.add(report)
        session.flush()

        # Generate 2-8 records per report
        num_records = random.randint(2, 8)
        for _ in range(num_records):
            source_ip = random.choice(SOURCE_IPS)

            # Weight results toward passing
            is_pass = random.random() < 0.7
            dkim_result = "pass" if is_pass else "fail"
            spf_result = "pass" if (is_pass or random.random() < 0.3) else "fail"

            if dkim_result == "pass" and spf_result == "pass":
                disposition = "none"
            elif policy == "reject" and dkim_result == "fail" and spf_result == "fail":
                disposition = "reject"
            elif policy == "quarantine" and dkim_result == "fail":
                disposition = "quarantine"
            else:
                disposition = "none"

            record = DmarcRecord(
                report_id=report.id,
                source_ip=source_ip,
                count=random.randint(1, 5000),
                disposition=disposition,
                dkim=dkim_result,
                spf=spf_result,
                header_from=domain,
                envelope_from=domain if random.random() < 0.8 else f"bounce.{domain}",
                envelope_to=domain,
                dkim_domain=domain,
                dkim_result=dkim_result,
                dkim_selector=random.choice(["google", "selector1", "selector2", "s1", "default"]),
                spf_domain=domain,
                spf_result=spf_result,
                spf_scope="mfrom",
                created_at=now,
            )
            session.add(record)

        created += 1
        print(f"  Created report {created}/{count}: {org} -> {domain} ({date_begin.date()})")

    session.commit()
    return created


def main():
    print("=" * 50)
    print("DMARC Seed Data Generator")
    print("=" * 50)
    print(f"Database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else DATABASE_URL}")
    print()

    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Check existing data
        existing = session.query(DmarcReport).count()
        print(f"Existing reports in database: {existing}")
        print()

        count = 15
        print(f"Generating {count} sample DMARC reports...")
        print()
        created = generate_reports(session, count)

        total = session.query(DmarcReport).count()
        total_records = session.query(DmarcRecord).count()
        print()
        print(f"Seed complete: {created} reports created")
        print(f"Total reports: {total}")
        print(f"Total records: {total_records}")

    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
