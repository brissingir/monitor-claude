import logging
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

from models import UsageData, SessionData, SessionTokenUsage

logger = logging.getLogger("monitor.datastore")

SCHEMA_VERSION = 2
RETENTION_DAYS = 90


class DataStore:
    def __init__(self, db_path: Path):
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()
        self._auto_prune()

    def _init_schema(self):
        cur = self._conn.cursor()
        cur.execute(
            "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)"
        )
        row = cur.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
        current = int(row["value"]) if row else 0

        if current < 1:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS usage_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    five_hour_pct REAL NOT NULL,
                    five_hour_resets_at TEXT,
                    seven_day_pct REAL NOT NULL,
                    seven_day_resets_at TEXT,
                    sonnet_pct REAL,
                    opus_pct REAL,
                    extra_usage_enabled INTEGER NOT NULL DEFAULT 0,
                    extra_usage_pct REAL
                )
            """)
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_snapshots_ts ON usage_snapshots(timestamp)"
            )
            cur.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', ?)",
                ("1",),
            )
            logger.info("Database schema v1 initialized")

        if current < 2:
            self._migrate_to_v2(cur)

        self._conn.commit()

    def _migrate_to_v2(self, cur):
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                slug TEXT,
                ai_title TEXT,
                project_path TEXT,
                entrypoint TEXT,
                git_branch TEXT,
                started_at TEXT,
                ended_at TEXT,
                user_message_count INTEGER NOT NULL DEFAULT 0,
                last_scanned_line INTEGER NOT NULL DEFAULT 0,
                file_path TEXT
            )
        """)
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_started ON sessions(started_at)"
        )
        cur.execute("""
            CREATE TABLE IF NOT EXISTS session_token_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES sessions(session_id),
                model TEXT NOT NULL,
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                cache_creation_tokens INTEGER NOT NULL DEFAULT 0,
                cache_read_tokens INTEGER NOT NULL DEFAULT 0,
                message_count INTEGER NOT NULL DEFAULT 0,
                UNIQUE(session_id, model)
            )
        """)
        cur.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', '2')"
        )
        logger.info("Database migrated to schema v2 (sessions)")

    def _auto_prune(self):
        cutoff = (datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)).isoformat()
        cur = self._conn.execute(
            "DELETE FROM usage_snapshots WHERE timestamp < ?", (cutoff,)
        )
        if cur.rowcount > 0:
            logger.info("Pruned %d old snapshots (>%d days)", cur.rowcount, RETENTION_DAYS)
            self._conn.execute("PRAGMA optimize")
        self._conn.commit()

    def save_snapshot(self, data: UsageData):
        self._conn.execute(
            """INSERT INTO usage_snapshots
               (timestamp, five_hour_pct, five_hour_resets_at,
                seven_day_pct, seven_day_resets_at,
                sonnet_pct, opus_pct,
                extra_usage_enabled, extra_usage_pct)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data.fetched_at.isoformat(),
                data.five_hour_utilization,
                data.five_hour_resets_at.isoformat() if data.five_hour_resets_at else None,
                data.seven_day_utilization,
                data.seven_day_resets_at.isoformat() if data.seven_day_resets_at else None,
                data.seven_day_sonnet_utilization,
                data.seven_day_opus_utilization,
                int(data.extra_usage_enabled),
                data.extra_usage_utilization,
            ),
        )
        self._conn.commit()
        logger.debug(
            "Snapshot saved: 5h=%.1f%% 7d=%.1f%%",
            data.five_hour_utilization,
            data.seven_day_utilization,
        )

    def get_latest_snapshot(self) -> UsageData | None:
        row = self._conn.execute(
            "SELECT * FROM usage_snapshots ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
        if not row:
            return None
        return self._row_to_usage(row)

    def get_snapshots_since(self, since: datetime) -> list[UsageData]:
        rows = self._conn.execute(
            "SELECT * FROM usage_snapshots WHERE timestamp >= ? ORDER BY timestamp ASC",
            (since.isoformat(),),
        ).fetchall()
        return [self._row_to_usage(r) for r in rows]

    def get_snapshot_count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) as cnt FROM usage_snapshots").fetchone()
        return row["cnt"] if row else 0

    @staticmethod
    def _row_to_usage(row: sqlite3.Row) -> UsageData:
        def parse_dt(val: str | None) -> datetime | None:
            if not val:
                return None
            try:
                return datetime.fromisoformat(val)
            except ValueError:
                return None

        return UsageData(
            five_hour_utilization=row["five_hour_pct"],
            five_hour_resets_at=parse_dt(row["five_hour_resets_at"]),
            seven_day_utilization=row["seven_day_pct"],
            seven_day_resets_at=parse_dt(row["seven_day_resets_at"]),
            seven_day_sonnet_utilization=row["sonnet_pct"],
            seven_day_opus_utilization=row["opus_pct"],
            extra_usage_enabled=bool(row["extra_usage_enabled"]),
            extra_usage_utilization=row["extra_usage_pct"],
            fetched_at=parse_dt(row["timestamp"]) or datetime.now(timezone.utc),
        )

    # --- Session methods ---

    def upsert_session(self, session: SessionData, last_scanned_line: int, file_path: str):
        self._conn.execute(
            """INSERT INTO sessions
               (session_id, slug, ai_title, project_path, entrypoint, git_branch,
                started_at, ended_at, user_message_count, last_scanned_line, file_path)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(session_id) DO UPDATE SET
                 ai_title = COALESCE(excluded.ai_title, ai_title),
                 ended_at = excluded.ended_at,
                 user_message_count = excluded.user_message_count,
                 last_scanned_line = excluded.last_scanned_line""",
            (
                session.session_id,
                session.slug,
                session.ai_title,
                session.project_path,
                session.entrypoint,
                session.git_branch,
                session.started_at.isoformat() if session.started_at else None,
                session.ended_at.isoformat() if session.ended_at else None,
                session.user_message_count,
                last_scanned_line,
                file_path,
            ),
        )
        for usage in session.token_usage:
            self._conn.execute(
                """INSERT INTO session_token_usage
                   (session_id, model, input_tokens, output_tokens,
                    cache_creation_tokens, cache_read_tokens, message_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(session_id, model) DO UPDATE SET
                     input_tokens = excluded.input_tokens,
                     output_tokens = excluded.output_tokens,
                     cache_creation_tokens = excluded.cache_creation_tokens,
                     cache_read_tokens = excluded.cache_read_tokens,
                     message_count = excluded.message_count""",
                (
                    session.session_id,
                    usage.model,
                    usage.input_tokens,
                    usage.output_tokens,
                    usage.cache_creation_tokens,
                    usage.cache_read_tokens,
                    usage.message_count,
                ),
            )
        self._conn.commit()

    def get_session_scan_info(self, file_path: str) -> tuple[str | None, int]:
        """Returns (session_id, last_scanned_line) for a given file path."""
        row = self._conn.execute(
            "SELECT session_id, last_scanned_line FROM sessions WHERE file_path = ?",
            (file_path,),
        ).fetchone()
        if not row:
            return None, 0
        return row["session_id"], row["last_scanned_line"]

    def get_recent_sessions(self, limit: int = 20) -> list[SessionData]:
        rows = self._conn.execute(
            "SELECT * FROM sessions ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
        sessions = []
        for row in rows:
            token_rows = self._conn.execute(
                "SELECT * FROM session_token_usage WHERE session_id = ?",
                (row["session_id"],),
            ).fetchall()
            sessions.append(self._row_to_session(row, token_rows))
        return sessions

    def get_sessions_since(self, since: datetime) -> list[SessionData]:
        rows = self._conn.execute(
            "SELECT * FROM sessions WHERE started_at >= ? ORDER BY started_at ASC",
            (since.isoformat(),),
        ).fetchall()
        sessions = []
        for row in rows:
            token_rows = self._conn.execute(
                "SELECT * FROM session_token_usage WHERE session_id = ?",
                (row["session_id"],),
            ).fetchall()
            sessions.append(self._row_to_session(row, token_rows))
        return sessions

    def get_today_token_totals(self) -> dict[str, int]:
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ).isoformat()
        row = self._conn.execute(
            """SELECT
                 COALESCE(SUM(t.input_tokens), 0) as total_input,
                 COALESCE(SUM(t.output_tokens), 0) as total_output,
                 COALESCE(SUM(t.cache_creation_tokens), 0) as total_cache_create,
                 COALESCE(SUM(t.cache_read_tokens), 0) as total_cache_read
               FROM session_token_usage t
               JOIN sessions s ON t.session_id = s.session_id
               WHERE s.started_at >= ?""",
            (today_start,),
        ).fetchone()
        return {
            "input": row["total_input"],
            "output": row["total_output"],
            "cache_creation": row["total_cache_create"],
            "cache_read": row["total_cache_read"],
            "total": row["total_input"] + row["total_output"]
                     + row["total_cache_create"] + row["total_cache_read"],
        }

    def get_session_count_since(self, since: datetime) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM sessions WHERE started_at >= ?",
            (since.isoformat(),),
        ).fetchone()
        return row["cnt"] if row else 0

    @staticmethod
    def _row_to_session(row: sqlite3.Row, token_rows: list[sqlite3.Row]) -> SessionData:
        def parse_dt(val: str | None) -> datetime | None:
            if not val:
                return None
            try:
                return datetime.fromisoformat(val)
            except ValueError:
                return None

        return SessionData(
            session_id=row["session_id"],
            slug=row["slug"] or "",
            ai_title=row["ai_title"],
            project_path=row["project_path"] or "",
            entrypoint=row["entrypoint"] or "",
            git_branch=row["git_branch"] or "",
            started_at=parse_dt(row["started_at"]),
            ended_at=parse_dt(row["ended_at"]),
            user_message_count=row["user_message_count"],
            token_usage=[
                SessionTokenUsage(
                    model=tr["model"],
                    input_tokens=tr["input_tokens"],
                    output_tokens=tr["output_tokens"],
                    cache_creation_tokens=tr["cache_creation_tokens"],
                    cache_read_tokens=tr["cache_read_tokens"],
                    message_count=tr["message_count"],
                )
                for tr in token_rows
            ],
        )

    def close(self):
        self._conn.close()
