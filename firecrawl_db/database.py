"""SQLite database operations for Firecrawl data."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

from .models import Link, Metadata, Scrape


class Database:
    """SQLite database for storing Firecrawl scrape data."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_schema(self) -> None:
        """Initialize database schema."""
        with self._connection() as conn:
            cursor = conn.cursor()

            # Main scrapes table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scrapes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_url TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    scraped_at TIMESTAMP,
                    source_file TEXT,
                    markdown TEXT,
                    html TEXT,
                    screenshot_url TEXT,
                    screenshot_desktop_url TEXT,
                    screenshot_mobile_url TEXT,
                    screenshot_desktop_path TEXT,
                    screenshot_mobile_path TEXT,
                    title TEXT,
                    description TEXT,
                    language TEXT,
                    status_code INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Add new columns if they don't exist (for existing databases)
            for col in ["screenshot_desktop_url", "screenshot_mobile_url",
                        "screenshot_desktop_path", "screenshot_mobile_path"]:
                try:
                    cursor.execute(f"ALTER TABLE scrapes ADD COLUMN {col} TEXT")
                except sqlite3.OperationalError:
                    pass  # Column already exists

            # Links table (1-to-many)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scrape_id INTEGER NOT NULL,
                    url TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    FOREIGN KEY (scrape_id) REFERENCES scrapes(id) ON DELETE CASCADE
                )
            """)

            # Metadata table (key-value)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scrape_id INTEGER NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT,
                    FOREIGN KEY (scrape_id) REFERENCES scrapes(id) ON DELETE CASCADE
                )
            """)

            # FTS5 full-text search table
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS scrapes_fts USING fts5(
                    title,
                    description,
                    markdown,
                    content='scrapes',
                    content_rowid='id'
                )
            """)

            # Triggers to keep FTS in sync
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS scrapes_ai AFTER INSERT ON scrapes BEGIN
                    INSERT INTO scrapes_fts(rowid, title, description, markdown)
                    VALUES (new.id, new.title, new.description, new.markdown);
                END
            """)

            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS scrapes_ad AFTER DELETE ON scrapes BEGIN
                    INSERT INTO scrapes_fts(scrapes_fts, rowid, title, description, markdown)
                    VALUES('delete', old.id, old.title, old.description, old.markdown);
                END
            """)

            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS scrapes_au AFTER UPDATE ON scrapes BEGIN
                    INSERT INTO scrapes_fts(scrapes_fts, rowid, title, description, markdown)
                    VALUES('delete', old.id, old.title, old.description, old.markdown);
                    INSERT INTO scrapes_fts(rowid, title, description, markdown)
                    VALUES (new.id, new.title, new.description, new.markdown);
                END
            """)

            # Indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_scrapes_source_url ON scrapes(source_url)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_scrapes_mode ON scrapes(mode)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_scrapes_scraped_at ON scrapes(scraped_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_links_scrape_id ON links(scrape_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_metadata_scrape_id ON metadata(scrape_id)")

    def insert_scrape(self, scrape: Scrape) -> int:
        """Insert a new scrape record."""
        with self._connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO scrapes (
                    source_url, mode, scraped_at, source_file,
                    markdown, html, screenshot_url,
                    screenshot_desktop_url, screenshot_mobile_url,
                    screenshot_desktop_path, screenshot_mobile_path,
                    title, description, language, status_code
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    scrape.source_url,
                    scrape.mode,
                    scrape.scraped_at,
                    scrape.source_file,
                    scrape.markdown,
                    scrape.html,
                    scrape.screenshot_url,
                    scrape.screenshot_desktop_url,
                    scrape.screenshot_mobile_url,
                    scrape.screenshot_desktop_path,
                    scrape.screenshot_mobile_path,
                    scrape.title,
                    scrape.description,
                    scrape.language,
                    scrape.status_code,
                ),
            )

            scrape_id = cursor.lastrowid

            # Insert links
            for link in scrape.links:
                cursor.execute(
                    "INSERT INTO links (scrape_id, url, position) VALUES (?, ?, ?)",
                    (scrape_id, link.url, link.position),
                )

            # Insert metadata
            for meta in scrape.metadata:
                cursor.execute(
                    "INSERT INTO metadata (scrape_id, key, value) VALUES (?, ?, ?)",
                    (scrape_id, meta.key, meta.value),
                )

            return scrape_id

    def get_scrape(self, scrape_id: int) -> Optional[Scrape]:
        """Get a scrape by ID with its links and metadata."""
        with self._connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM scrapes WHERE id = ?", (scrape_id,))
            row = cursor.fetchone()
            if not row:
                return None

            scrape = self._row_to_scrape(row)

            # Load links
            cursor.execute(
                "SELECT * FROM links WHERE scrape_id = ? ORDER BY position",
                (scrape_id,),
            )
            scrape.links = [
                Link(id=r["id"], scrape_id=r["scrape_id"], url=r["url"], position=r["position"])
                for r in cursor.fetchall()
            ]

            # Load metadata
            cursor.execute("SELECT * FROM metadata WHERE scrape_id = ?", (scrape_id,))
            scrape.metadata = [
                Metadata(id=r["id"], scrape_id=r["scrape_id"], key=r["key"], value=r["value"])
                for r in cursor.fetchall()
            ]

            return scrape

    def list_scrapes(
        self,
        limit: int = 100,
        offset: int = 0,
        mode: Optional[str] = None,
        url_contains: Optional[str] = None,
    ) -> list[Scrape]:
        """List scrapes with optional filtering."""
        with self._connection() as conn:
            cursor = conn.cursor()

            query = "SELECT * FROM scrapes WHERE 1=1"
            params: list = []

            if mode:
                query += " AND mode = ?"
                params.append(mode)

            if url_contains:
                query += " AND source_url LIKE ?"
                params.append(f"%{url_contains}%")

            query += " ORDER BY scraped_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            return [self._row_to_scrape(row) for row in cursor.fetchall()]

    def search_fulltext(self, query: str, limit: int = 100) -> list[Scrape]:
        """Full-text search across title, description, and markdown."""
        with self._connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT s.* FROM scrapes s
                JOIN scrapes_fts fts ON s.id = fts.rowid
                WHERE scrapes_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """,
                (query, limit),
            )

            return [self._row_to_scrape(row) for row in cursor.fetchall()]

    def delete_scrape(self, scrape_id: int) -> bool:
        """Delete a scrape and its related records."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM scrapes WHERE id = ?", (scrape_id,))
            return cursor.rowcount > 0

    def get_stats(self) -> dict:
        """Get database statistics."""
        with self._connection() as conn:
            cursor = conn.cursor()

            stats = {}

            cursor.execute("SELECT COUNT(*) FROM scrapes")
            stats["total_scrapes"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM links")
            stats["total_links"] = cursor.fetchone()[0]

            cursor.execute("SELECT mode, COUNT(*) as count FROM scrapes GROUP BY mode")
            stats["by_mode"] = {row["mode"]: row["count"] for row in cursor.fetchall()}

            cursor.execute(
                """
                SELECT DATE(scraped_at) as date, COUNT(*) as count
                FROM scrapes
                WHERE scraped_at IS NOT NULL
                GROUP BY DATE(scraped_at)
                ORDER BY date DESC
                LIMIT 10
            """
            )
            stats["recent_dates"] = {row["date"]: row["count"] for row in cursor.fetchall()}

            return stats

    def exists_by_url_and_file(self, source_url: str, source_file: str) -> bool:
        """Check if a scrape already exists for this URL and source file."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM scrapes WHERE source_url = ? AND source_file = ?",
                (source_url, source_file),
            )
            return cursor.fetchone() is not None

    def _row_to_scrape(self, row: sqlite3.Row) -> Scrape:
        """Convert a database row to a Scrape object."""
        scraped_at = None
        if row["scraped_at"]:
            try:
                scraped_at = datetime.fromisoformat(row["scraped_at"])
            except (ValueError, TypeError):
                pass

        created_at = None
        if row["created_at"]:
            try:
                created_at = datetime.fromisoformat(row["created_at"])
            except (ValueError, TypeError):
                pass

        updated_at = None
        if row["updated_at"]:
            try:
                updated_at = datetime.fromisoformat(row["updated_at"])
            except (ValueError, TypeError):
                pass

        # Handle optional new columns (may not exist in older databases)
        def get_col(name: str):
            try:
                return row[name]
            except (IndexError, KeyError):
                return None

        return Scrape(
            id=row["id"],
            source_url=row["source_url"],
            mode=row["mode"],
            scraped_at=scraped_at,
            source_file=row["source_file"],
            markdown=row["markdown"],
            html=row["html"],
            screenshot_url=row["screenshot_url"],
            screenshot_desktop_url=get_col("screenshot_desktop_url"),
            screenshot_mobile_url=get_col("screenshot_mobile_url"),
            screenshot_desktop_path=get_col("screenshot_desktop_path"),
            screenshot_mobile_path=get_col("screenshot_mobile_path"),
            title=row["title"],
            description=row["description"],
            language=row["language"],
            status_code=row["status_code"],
            created_at=created_at,
            updated_at=updated_at,
        )
