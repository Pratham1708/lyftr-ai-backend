"""
SQLite storage layer with idempotent message ingestion.
Primary key on message_id ensures idempotency.
"""
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from app.config import Config
from app.models import Message, SenderStats
from app.logging_utils import get_logger


logger = get_logger(__name__)


class MessageStorage:
    """SQLite-based message storage with idempotent operations."""
    
    def __init__(self, db_path: str = None):
        """Initialize storage and ensure database exists."""
        self.db_path = db_path or Config.DATABASE_PATH
        self._ensure_database()
    
    def _ensure_database(self) -> None:
        """Create database directory and initialize schema."""
        # Ensure parent directory exists
        db_file = Path(self.db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize schema
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    from_msisdn TEXT NOT NULL,
                    to_msisdn TEXT NOT NULL,
                    ts TEXT NOT NULL,
                    text TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            
            # Create indexes for efficient querying
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_from_msisdn 
                ON messages(from_msisdn)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ts 
                ON messages(ts)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at 
                ON messages(created_at)
            """)
            
            conn.commit()
            logger.info(f"Database initialized at {self.db_path}")
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def insert_message(
        self,
        message_id: str,
        from_msisdn: str,
        to_msisdn: str,
        ts: datetime,
        text: Optional[str] = None
    ) -> bool:
        """
        Insert message with idempotent behavior.
        
        Returns:
            True if message was inserted, False if it already existed.
        """
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO messages 
                    (message_id, from_msisdn, to_msisdn, ts, text, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        message_id,
                        from_msisdn,
                        to_msisdn,
                        ts.isoformat(),
                        text,
                        datetime.utcnow().isoformat()
                    )
                )
                conn.commit()
                logger.info(f"Inserted new message: {message_id}")
                return True
        except sqlite3.IntegrityError:
            # Message already exists (duplicate message_id)
            logger.info(f"Message already exists: {message_id}")
            return False
    
    def get_messages(
        self,
        limit: int = 50,
        offset: int = 0,
        from_msisdn: Optional[str] = None,
        since: Optional[datetime] = None,
        search_query: Optional[str] = None
    ) -> Tuple[List[Message], int]:
        """
        Retrieve messages with pagination and filtering.
        
        Returns:
            Tuple of (messages list, total count)
        """
        with self._get_connection() as conn:
            # Build WHERE clause
            where_clauses = []
            params = []
            
            if from_msisdn:
                where_clauses.append("from_msisdn = ?")
                params.append(from_msisdn)
            
            if since:
                where_clauses.append("ts >= ?")
                params.append(since.isoformat())
            
            if search_query:
                where_clauses.append("text LIKE ?")
                params.append(f"%{search_query}%")
            
            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
            
            # Get total count
            count_query = f"SELECT COUNT(*) as total FROM messages WHERE {where_sql}"
            total = conn.execute(count_query, params).fetchone()["total"]
            
            # Get paginated results with deterministic ordering (ASC - oldest first)
            query = f"""
                SELECT message_id, from_msisdn, to_msisdn, ts, text, created_at
                FROM messages
                WHERE {where_sql}
                ORDER BY ts ASC, message_id ASC
                LIMIT ? OFFSET ?
            """
            params.extend([limit, offset])
            
            rows = conn.execute(query, params).fetchall()
            
            messages = [
                Message(
                    message_id=row["message_id"],
                    from_=row["from_msisdn"],
                    to=row["to_msisdn"],
                    ts=datetime.fromisoformat(row["ts"]),
                    text=row["text"],
                    created_at=datetime.fromisoformat(row["created_at"])
                )
                for row in rows
            ]
            
            return messages, total
    
    def get_stats(self) -> dict:
        """
        Get analytics statistics.
        
        Returns:
            Dictionary with total_messages, senders_count, messages_per_sender,
            first_message_ts, and last_message_ts.
        """
        with self._get_connection() as conn:
            # Total messages
            total = conn.execute("SELECT COUNT(*) as count FROM messages").fetchone()["count"]
            
            # Unique senders count
            senders = conn.execute(
                "SELECT COUNT(DISTINCT from_msisdn) as count FROM messages"
            ).fetchone()["count"]
            
            # Top 10 senders by message count (deterministic ordering)
            top_senders = conn.execute("""
                SELECT from_msisdn, COUNT(*) as count
                FROM messages
                GROUP BY from_msisdn
                ORDER BY count DESC, from_msisdn ASC
                LIMIT 10
            """).fetchall()
            
            messages_per_sender = [
                SenderStats(from_=row["from_msisdn"], count=row["count"])
                for row in top_senders
            ]
            
            # First and last message timestamps
            timestamps = conn.execute("""
                SELECT 
                    MIN(ts) as first_ts,
                    MAX(ts) as last_ts
                FROM messages
            """).fetchone()
            
            first_ts = None
            last_ts = None
            
            if timestamps["first_ts"]:
                first_ts = datetime.fromisoformat(timestamps["first_ts"])
            if timestamps["last_ts"]:
                last_ts = datetime.fromisoformat(timestamps["last_ts"])
            
            return {
                "total_messages": total,
                "senders_count": senders,
                "messages_per_sender": messages_per_sender,
                "first_message_ts": first_ts,
                "last_message_ts": last_ts
            }
    
    def health_check(self) -> bool:
        """Check if database is accessible."""
        try:
            with self._get_connection() as conn:
                conn.execute("SELECT 1").fetchone()
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
