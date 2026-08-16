"""
Database manager and checkpointing module for the B2B Lead Generation Engine.
Implements crash-resilient SQLite storage with WAL mode, upsert operations,
and lead enrichment state management.
"""

import sqlite3
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from contextlib import contextmanager
from datetime import datetime

from config import DB_PATH
from models import Lead
from logger import get_logger

logger = get_logger("DatabaseManager")


class DatabaseManager:
    """
    Thread-safe SQLite database manager providing immediate checkpointing,
    lead deduplication, and pipeline state persistence.
    """

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = Path(db_path)
        self.initialize_db()

    @contextmanager
    def get_connection(self):
        """
        Context manager for acquiring SQLite connections with foreign keys enabled,
        row factory configured, and automatic transaction commit/rollback.
        """
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            # Enable WAL mode for high-concurrency and crash resilience
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database transaction error: {e}", exc_info=True)
            raise
        finally:
            conn.close()

    def initialize_db(self) -> None:
        """
        Create tables and performance indexes if they do not exist.
        """
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            address TEXT,
            website TEXT,
            email TEXT,
            query TEXT,
            rating REAL,
            reviews_count INTEGER,
            maps_url TEXT,
            is_enriched INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        create_indexes_sql = [
            "CREATE INDEX IF NOT EXISTS idx_leads_name ON leads(name);",
            "CREATE INDEX IF NOT EXISTS idx_leads_website ON leads(website);",
            "CREATE INDEX IF NOT EXISTS idx_leads_is_enriched ON leads(is_enriched);",
            "CREATE INDEX IF NOT EXISTS idx_leads_maps_url ON leads(maps_url);",
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_leads_name_phone ON leads(name, phone) WHERE phone IS NOT NULL;",
        ]

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(create_table_sql)
            for idx_sql in create_indexes_sql:
                cursor.execute(idx_sql)
        
        logger.info(f"Database initialized successfully at: {self.db_path}")

    def save_lead(self, lead: Lead) -> int:
        """
        Insert a new lead or update an existing one if matches by maps_url or (name, phone).
        Provides immediate checkpointing to prevent data loss on crash.

        :param lead: Lead data object
        :return: Inserted/Updated lead database row ID
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.utcnow().isoformat()

            # Check if lead exists by maps_url or (name, phone)
            existing_id: Optional[int] = None
            if lead.maps_url:
                cursor.execute("SELECT id FROM leads WHERE maps_url = ?", (lead.maps_url,))
                row = cursor.fetchone()
                if row:
                    existing_id = row["id"]

            if not existing_id and lead.name and lead.phone:
                cursor.execute("SELECT id FROM leads WHERE name = ? AND phone = ?", (lead.name, lead.phone))
                row = cursor.fetchone()
                if row:
                    existing_id = row["id"]

            if existing_id:
                # Update existing lead record
                update_sql = """
                UPDATE leads
                SET name = ?,
                    phone = COALESCE(?, phone),
                    address = COALESCE(?, address),
                    website = COALESCE(?, website),
                    email = COALESCE(?, email),
                    query = COALESCE(?, query),
                    rating = COALESCE(?, rating),
                    reviews_count = COALESCE(?, reviews_count),
                    updated_at = ?
                WHERE id = ?;
                """
                cursor.execute(update_sql, (
                    lead.name,
                    lead.phone,
                    lead.address,
                    lead.website,
                    lead.email,
                    lead.query,
                    lead.rating,
                    lead.reviews_count,
                    now,
                    existing_id
                ))
                lead.id = existing_id
                logger.debug(f"Updated existing lead ID {existing_id}: '{lead.name}'")
                return existing_id
            else:
                # Insert new lead record
                insert_sql = """
                INSERT INTO leads (
                    name, phone, address, website, email,
                    query, rating, reviews_count, maps_url,
                    is_enriched, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """
                cursor.execute(insert_sql, (
                    lead.name,
                    lead.phone,
                    lead.address,
                    lead.website,
                    lead.email,
                    lead.query,
                    lead.rating,
                    lead.reviews_count,
                    lead.maps_url,
                    1 if lead.is_enriched else 0,
                    lead.created_at or now,
                    lead.updated_at or now
                ))
                lead_id = cursor.lastrowid
                lead.id = lead_id
                logger.info(f"Checkpointed new lead ID {lead_id}: '{lead.name}' (Phone: {lead.phone or 'N/A'}, Website: {lead.website or 'N/A'})")
                return lead_id

    def lead_exists(self, name: str, maps_url: Optional[str] = None) -> bool:
        """
        Check if a lead with given name or Google Maps URL already exists in database.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if maps_url:
                cursor.execute("SELECT 1 FROM leads WHERE maps_url = ? LIMIT 1", (maps_url,))
                if cursor.fetchone():
                    return True
            cursor.execute("SELECT 1 FROM leads WHERE name = ? LIMIT 1", (name,))
            return cursor.fetchone() is not None

    def get_unenriched_leads(self, limit: Optional[int] = None) -> List[Lead]:
        """
        Retrieve leads that have a valid website URL but have not yet been enriched with emails.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            sql = """
            SELECT * FROM leads
            WHERE is_enriched = 0
              AND website IS NOT NULL
              AND website != ''
            ORDER BY id ASC
            """
            if limit:
                sql += f" LIMIT {int(limit)}"
            
            cursor.execute(sql)
            rows = cursor.fetchall()
            return [Lead.from_sqlite_row(row) for row in rows]

    def mark_lead_enriched(self, lead_id: int, email: Optional[str] = None) -> bool:
        """
        Mark a lead as enriched and persist discovered contact email address.
        """
        now = datetime.utcnow().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE leads
                SET is_enriched = 1,
                    email = ?,
                    updated_at = ?
                WHERE id = ?;
                """,
                (email, now, lead_id)
            )
            logger.info(f"Lead ID {lead_id} marked as enriched. Discovered email: {email or 'None'}")
            return cursor.rowcount > 0

    def get_all_leads(self, query: Optional[str] = None) -> List[Lead]:
        """
        Retrieve all leads from the database, optionally filtered by search query.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if query:
                cursor.execute("SELECT * FROM leads WHERE query = ? ORDER BY id ASC", (query,))
            else:
                cursor.execute("SELECT * FROM leads ORDER BY id ASC")
            
            rows = cursor.fetchall()
            return [Lead.from_sqlite_row(row) for row in rows]

    def get_lead_stats(self) -> Dict[str, Any]:
        """
        Calculate aggregate summary statistics of leads in the database.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM leads")
            total_leads = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM leads WHERE is_enriched = 1")
            enriched_leads = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM leads WHERE email IS NOT NULL AND email != ''")
            leads_with_email = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM leads WHERE phone IS NOT NULL AND phone != ''")
            leads_with_phone = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM leads WHERE website IS NOT NULL AND website != ''")
            leads_with_website = cursor.fetchone()[0]

            return {
                "total_leads": total_leads,
                "enriched_leads": enriched_leads,
                "leads_with_email": leads_with_email,
                "leads_with_phone": leads_with_phone,
                "leads_with_website": leads_with_website,
            }
