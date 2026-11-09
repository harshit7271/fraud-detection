"""
FACEGUARD AI - Production Data Sync to Local PostgreSQL
Fetches live production interview sessions and fraud events from Hugging Face Spaces
and imports them into your local PostgreSQL database (Port 5433).
"""

import argparse
import getpass
import json
import sys
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models.fraud import FraudEventModel, FraudReportModel
from app.db.models.session import InterviewSession
from app.db.models.tenant import Tenant, TenantConfig

PROD_API_URL = "https://harshit7271-faceguard-ai.hf.space/api/v1"
TENANTS = [
    {"slug": "enterprise-a", "name": "Enterprise A", "key": "enterprise-a-key-2026"},
    {"slug": "enterprise-b", "name": "Enterprise B", "key": "enterprise-b-key-2026"},
    {"slug": "enterprise-c", "name": "Enterprise C", "key": "enterprise-c-key-2026"},
]


def fetch_prod_sessions(tenant_slug: str, tenant_key: str) -> list[dict]:
    """Fetches sessions from live Hugging Face production microservice."""
    url = f"{PROD_API_URL}/fraud/sessions"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "FaceGuard-Data-Sync",
            "X-Tenant-Key": tenant_key,
            "X-Tenant-Id": tenant_slug,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"  [!] Notice: Could not fetch sessions for {tenant_slug}: {e}")
        return []


def fetch_prod_events(session_id: str, tenant_slug: str, tenant_key: str) -> list[dict]:
    """Fetches confirmed fraud events for a session."""
    url = f"{PROD_API_URL}/fraud/sessions/{session_id}/events"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "FaceGuard-Data-Sync",
            "X-Tenant-Key": tenant_key,
            "X-Tenant-Id": tenant_slug,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data if isinstance(data, list) else []
    except Exception:
        return []


def ensure_database_exists(host: str, port: int, user: str, password: str, dbname: str) -> None:
    """Connects to default postgres database to create face_fraud_db if missing."""
    print(f"\n[1/5] Checking database '{dbname}' on {host}:{port}...")
    conn = psycopg2.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        dbname="postgres",
        connect_timeout=5,
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (dbname,))
    exists = cur.fetchone()
    if not exists:
        print(f"  [+] Database '{dbname}' not found. Creating it now...")
        cur.execute(f'CREATE DATABASE "{dbname}";')
        print(f"  [+] Database '{dbname}' created successfully!")
    else:
        print(f"  [OK] Database '{dbname}' already exists.")
    cur.close()
    conn.close()


def sync_data(host: str, port: int, user: str, password: str, dbname: str) -> None:
    # 1. Ensure target DB exists
    ensure_database_exists(host, port, user, password, dbname)

    # 2. Initialize SQLAlchemy Schema
    print("\n[2/5] Creating / updating PostgreSQL tables...")
    safe_pwd = urllib.parse.quote_plus(password)
    sync_url = f"postgresql+psycopg2://{user}:{safe_pwd}@{host}:{port}/{dbname}"
    engine = create_engine(sync_url)
    Base.metadata.create_all(engine)
    print("  [OK] All tables (tenants, interview_sessions, fraud_events, etc.) are verified.")

    # 3. Seed / Ensure Tenants Exist
    print("\n[3/5] Setting up tenant boundaries...")
    tenant_id_map: dict[str, uuid.UUID] = {}
    with Session(engine) as session:
        for t in TENANTS:
            existing = session.query(Tenant).filter(Tenant.slug == t["slug"]).first()
            if not existing:
                import hashlib
                key_hash = hashlib.sha256(t["key"].encode("utf-8")).hexdigest()
                tenant_obj = Tenant(
                    slug=t["slug"],
                    name=t["name"],
                    api_key_hash=key_hash,
                    is_active=True,
                )
                session.add(tenant_obj)
                session.flush()
                config = TenantConfig(
                    tenant_id=tenant_obj.id,
                    face_match_threshold=0.38,
                    face_uncertain_threshold=0.25,
                    multiple_faces_debounce_ms=2000,
                    face_absence_debounce_ms=3000,
                    biometric_retention_days=30,
                    event_weights={},
                    risk_bands={},
                )
                session.add(config)
                session.commit()
                tenant_id_map[t["slug"]] = tenant_obj.id
                print(f"  [+] Created tenant: {t['name']} ({t['slug']})")
            else:
                tenant_id_map[t["slug"]] = existing.id
                print(f"  [OK] Existing tenant: {t['name']} ({t['slug']})")

    # 4. Fetch Live Data from Production & Insert
    print("\n[4/5] Downloading live sessions from Hugging Face Spaces production...")
    total_synced_sessions = 0
    total_synced_events = 0

    with Session(engine) as session:
        for t in TENANTS:
            slug = t["slug"]
            key = t["key"]
            t_uuid = tenant_id_map.get(slug)
            if not t_uuid:
                continue

            print(f"  [*] Querying production for tenant '{slug}'...")
            prod_sessions = fetch_prod_sessions(slug, key)
            print(f"      Found {len(prod_sessions)} live session(s).")

            for s_data in prod_sessions:
                s_id_str = s_data.get("session_id")
                if not s_id_str:
                    continue

                try:
                    s_uuid = uuid.UUID(s_id_str)
                except ValueError:
                    s_uuid = uuid.uuid4()

                cand_id = s_data.get("candidate_id", "unknown_candidate")
                int_id = s_data.get("interview_id", "unknown_interview")
                status = s_data.get("status", "INITIALIZED")
                consent = s_data.get("consent_recorded", True)

                created_str = s_data.get("created_at")
                if created_str:
                    try:
                        created_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                    except Exception:
                        created_dt = datetime.now()
                else:
                    created_dt = datetime.now()

                # Upsert interview_session
                db_session = session.query(InterviewSession).filter(InterviewSession.id == s_uuid).first()
                if not db_session:
                    db_session = InterviewSession(
                        id=s_uuid,
                        tenant_id=t_uuid,
                        candidate_id=cand_id,
                        interview_id=int_id,
                        status=status,
                        consent_recorded=consent,
                        created_at=created_dt,
                    )
                    session.add(db_session)
                    session.flush()
                    total_synced_sessions += 1
                else:
                    db_session.status = status

                # Sync current risk assessment / report
                risk = s_data.get("current_risk")
                if risk and isinstance(risk, dict):
                    existing_report = session.query(FraudReportModel).filter(FraudReportModel.session_id == s_uuid).first()
                    if not existing_report:
                        db_rep = FraudReportModel(
                            tenant_id=t_uuid,
                            session_id=s_uuid,
                            risk_score=float(risk.get("risk_score", 0.0)),
                            risk_level=risk.get("risk_level", "LOW"),
                            fraud_status=risk.get("fraud_status", "CLEARED"),
                            recommendation=risk.get("recommendation", "NO_ACTION"),
                            summary_breakdown=risk.get("event_breakdown", {}),
                        )
                        session.add(db_rep)

                # Sync confirmed fraud events for this session
                prod_events = fetch_prod_events(s_id_str, slug, key)
                for ev in prod_events:
                    ev_type = ev.get("event_type", "ANOMALY")
                    ev_ts = ev.get("timestamp_ms", int(datetime.now().timestamp() * 1000))
                    ev_dur = ev.get("duration_ms", 0)
                    ev_conf = float(ev.get("confidence", 0.95))
                    ev_sev = ev.get("severity", "MEDIUM")
                    ev_meta = ev.get("evidence_metadata", {})

                    # Check duplicate event
                    existing_ev = session.query(FraudEventModel).filter(
                        FraudEventModel.session_id == s_uuid,
                        FraudEventModel.event_type == ev_type,
                        FraudEventModel.timestamp_ms == ev_ts,
                    ).first()

                    if not existing_ev:
                        db_ev = FraudEventModel(
                            tenant_id=t_uuid,
                            session_id=s_uuid,
                            event_type=ev_type,
                            timestamp_ms=ev_ts,
                            duration_ms=ev_dur,
                            confidence=ev_conf,
                            severity=ev_sev,
                            evidence_metadata=ev_meta,
                        )
                        session.add(db_ev)
                        total_synced_events += 1

            session.commit()

    # 5. Verification & Summary Output
    print("\n[5/5] Verification & Summary:")
    print("=" * 60)
    with Session(engine) as session:
        session_count = session.query(InterviewSession).count()
        event_count = session.query(FraudEventModel).count()
        report_count = session.query(FraudReportModel).count()
        tenant_count = session.query(Tenant).count()

        print(f"  Total Tenants in PostgreSQL:     {tenant_count}")
        print(f"  Total Sessions in PostgreSQL:    {session_count} (+{total_synced_sessions} newly synced)")
        print(f"  Total Fraud Events in PostgreSQL:{event_count} (+{total_synced_events} newly synced)")
        print(f"  Total Risk Reports in PostgreSQL:{report_count}")
    print("=" * 60)

    print("\n  [SUCCESS] All production data is now stored in your local PostgreSQL!")
    print(f"  Database: face_fraud_db (Port: {port})")
    print("\n  Try running these queries in pgAdmin 4 or DBeaver:")
    print("  -------------------------------------------------------------")
    print("  SELECT id, candidate_id, interview_id, status, created_at FROM interview_sessions;")
    print("  SELECT session_id, risk_score, risk_level, fraud_status FROM fraud_reports;")
    print("  SELECT session_id, event_type, severity, confidence FROM fraud_events;")
    print("  -------------------------------------------------------------\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync production FaceGuard AI data to local PostgreSQL.")
    parser.add_argument("--host", default="127.0.0.1", help="PostgreSQL host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5433, help="PostgreSQL port (default: 5433)")
    parser.add_argument("--user", default="postgres", help="PostgreSQL user (default: postgres)")
    parser.add_argument("--password", default=None, help="PostgreSQL password")
    parser.add_argument("--dbname", default="face_fraud_db", help="Target database name (default: face_fraud_db)")
    args = parser.parse_args()

    pwd = args.password
    if not pwd:
        pwd = getpass.getpass(f"Enter PostgreSQL password for user '{args.user}' on port {args.port}: ")

    try:
        sync_data(
            host=args.host,
            port=args.port,
            user=args.user,
            password=pwd,
            dbname=args.dbname,
        )
    except psycopg2.OperationalError as e:
        print(f"\n[X] Connection failed: {e}")
        print("Please check your PostgreSQL password and port.")
        sys.exit(1)
    except Exception as e:
        print(f"\n[X] An unexpected error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
