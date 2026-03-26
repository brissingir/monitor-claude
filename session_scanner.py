"""Scans Claude Code local session JSONL files for token usage and metadata.

Read-only access to ~/.claude/ — never writes to Claude's directories.
All derived data goes into the app's own SQLite database via DataStore.
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, QTimer

from data_store import DataStore
from models import SessionData, SessionTokenUsage

logger = logging.getLogger("monitor.scanner")


class _ScanWorker(QObject):
    finished = Signal(int)  # number of sessions updated

    def __init__(self, claude_dir: Path, data_store: DataStore):
        super().__init__()
        self._claude_dir = claude_dir
        self._store = data_store

    def run(self):
        try:
            updated = self._scan_all_projects()
            self.finished.emit(updated)
        except Exception as e:
            logger.error("Scan failed: %s", e)
            self.finished.emit(0)

    def _scan_all_projects(self) -> int:
        projects_dir = self._claude_dir / "projects"
        if not projects_dir.exists():
            logger.debug("No projects dir at %s", projects_dir)
            return 0

        updated = 0
        for jsonl_file in projects_dir.rglob("*.jsonl"):
            try:
                if self._scan_file(jsonl_file):
                    updated += 1
            except Exception as e:
                logger.warning("Error scanning %s: %s", jsonl_file.name, e)
        return updated

    def _scan_file(self, file_path: Path) -> bool:
        file_str = str(file_path)
        file_mtime = os.path.getmtime(file_path)

        # Check if we already scanned this file up to this point
        existing_id, last_line = self._store.get_session_scan_info(file_str)
        file_size = file_path.stat().st_size

        # Quick skip: if file hasn't grown since last scan
        if existing_id and last_line > 0:
            # Read only new lines
            lines = self._read_lines(file_path, start_line=last_line)
            if not lines:
                return False
            all_lines = self._read_lines(file_path, start_line=0)
            session = self._parse_lines(all_lines, file_path)
        else:
            all_lines = self._read_lines(file_path, start_line=0)
            if not all_lines:
                return False
            session = self._parse_lines(all_lines, file_path)

        if not session or not session.session_id:
            return False

        total_lines = len(self._read_lines(file_path, start_line=0))
        self._store.upsert_session(session, total_lines, file_str)
        return True

    @staticmethod
    def _read_lines(file_path: Path, start_line: int = 0) -> list[dict]:
        lines = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for i, raw_line in enumerate(f):
                    if i < start_line:
                        continue
                    raw_line = raw_line.strip()
                    if not raw_line:
                        continue
                    try:
                        lines.append(json.loads(raw_line))
                    except json.JSONDecodeError:
                        continue
        except (OSError, UnicodeDecodeError) as e:
            logger.warning("Could not read %s: %s", file_path.name, e)
        return lines

    @staticmethod
    def _parse_lines(lines: list[dict], file_path: Path) -> SessionData | None:
        if not lines:
            return None

        session_id = ""
        slug = ""
        ai_title = None
        project_path = ""
        entrypoint = ""
        git_branch = ""
        first_ts: datetime | None = None
        last_ts: datetime | None = None
        user_count = 0
        token_by_model: dict[str, SessionTokenUsage] = {}

        # Extract project name from parent directory
        project_slug = file_path.parent.name

        for obj in lines:
            entry_type = obj.get("type", "")

            # Timestamps
            ts_str = obj.get("timestamp")
            if ts_str:
                try:
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    if first_ts is None or ts < first_ts:
                        first_ts = ts
                    if last_ts is None or ts > last_ts:
                        last_ts = ts
                except ValueError:
                    pass

            # Session ID
            if not session_id and obj.get("sessionId"):
                session_id = obj["sessionId"]

            # ai-title
            if entry_type == "ai-title":
                ai_title = obj.get("aiTitle") or obj.get("title")

            # User messages
            if entry_type == "user":
                user_count += 1

            # Assistant messages with token usage
            if entry_type == "assistant":
                if not slug and obj.get("slug"):
                    slug = obj["slug"]
                if not entrypoint and obj.get("entrypoint"):
                    entrypoint = obj["entrypoint"]
                if not git_branch and obj.get("gitBranch"):
                    git_branch = obj["gitBranch"]
                if not project_path and obj.get("cwd"):
                    project_path = obj["cwd"]

                msg = obj.get("message", {})
                model = msg.get("model", "unknown")
                usage = msg.get("usage", {})

                if usage:
                    if model not in token_by_model:
                        token_by_model[model] = SessionTokenUsage(model=model)
                    tu = token_by_model[model]
                    tu.input_tokens += usage.get("input_tokens", 0)
                    tu.output_tokens += usage.get("output_tokens", 0)
                    tu.cache_creation_tokens += usage.get("cache_creation_input_tokens", 0)
                    tu.cache_read_tokens += usage.get("cache_read_input_tokens", 0)
                    tu.message_count += 1

        if not session_id:
            return None

        return SessionData(
            session_id=session_id,
            slug=slug,
            ai_title=ai_title,
            project_path=project_path or project_slug,
            entrypoint=entrypoint,
            git_branch=git_branch,
            started_at=first_ts,
            ended_at=last_ts,
            user_message_count=user_count,
            token_usage=list(token_by_model.values()),
        )


class SessionScanner(QObject):
    """Periodically scans Claude session files and updates the DataStore."""

    scan_completed = Signal(int)  # number of sessions updated

    def __init__(self, data_store: DataStore, scan_interval_ms: int = 300_000):
        super().__init__()
        self._data_store = data_store
        self._claude_dir = Path.home() / ".claude"
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._start_scan)
        self._scan_interval = scan_interval_ms
        self._worker_thread: QThread | None = None

    def start(self):
        self._start_scan()
        self._timer.start(self._scan_interval)

    def stop(self):
        self._timer.stop()
        self._cleanup_thread()

    def scan_now(self):
        self._start_scan()

    def set_interval(self, ms: int):
        self._scan_interval = ms
        if self._timer.isActive():
            self._timer.setInterval(ms)

    def _start_scan(self):
        if self._worker_thread and self._worker_thread.isRunning():
            logger.debug("Scan already in progress, skipping")
            return

        self._cleanup_thread()

        thread = QThread()
        worker = _ScanWorker(self._claude_dir, self._data_store)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.finished.connect(self._on_scan_done)
        worker.finished.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)

        self._worker_thread = thread
        self._worker = worker

        thread.start()

    def _on_scan_done(self, updated: int):
        if updated > 0:
            logger.info("Session scan complete: %d sessions updated", updated)
        else:
            logger.debug("Session scan complete: no changes")
        self.scan_completed.emit(updated)

    def _cleanup_thread(self):
        if self._worker_thread and self._worker_thread.isRunning():
            self._worker_thread.quit()
            self._worker_thread.wait(3000)
        self._worker_thread = None


def get_active_session_ids() -> set[str]:
    """Read active session IDs from ~/.claude/sessions/*.json."""
    sessions_dir = Path.home() / ".claude" / "sessions"
    active = set()
    if not sessions_dir.exists():
        return active
    for f in sessions_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            sid = data.get("sessionId")
            if sid:
                active.add(sid)
        except (json.JSONDecodeError, OSError):
            continue
    return active
