"""Export session data to CSV or JSON."""

import csv
import json
import logging
from pathlib import Path

from cost_estimator import estimate_cost
from data_store import DataStore
from models import SessionData

logger = logging.getLogger("monitor.exporter")


def export_csv(sessions: list[SessionData], file_path: Path):
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Session ID", "Title", "Project", "Model", "Entrypoint",
            "Git Branch", "Started At", "Duration (min)",
            "User Messages", "Input Tokens", "Output Tokens",
            "Cache Create Tokens", "Cache Read Tokens",
            "Total Tokens", "Estimated Cost (USD)",
        ])
        for s in sessions:
            dur_min = (s.duration_seconds // 60) if s.duration_seconds else ""
            models = ", ".join(u.model for u in s.token_usage)
            total_in = sum(u.input_tokens for u in s.token_usage)
            total_out = sum(u.output_tokens for u in s.token_usage)
            total_cc = sum(u.cache_creation_tokens for u in s.token_usage)
            total_cr = sum(u.cache_read_tokens for u in s.token_usage)
            cost = sum(estimate_cost(u.model, u) for u in s.token_usage)

            writer.writerow([
                s.session_id,
                s.ai_title or s.slug or "Untitled",
                s.project_path,
                models,
                s.entrypoint,
                s.git_branch,
                s.started_at.isoformat() if s.started_at else "",
                dur_min,
                s.user_message_count,
                total_in, total_out, total_cc, total_cr,
                s.total_tokens,
                f"{cost:.4f}",
            ])
    logger.info("Exported %d sessions to CSV: %s", len(sessions), file_path)


def export_json(sessions: list[SessionData], file_path: Path):
    data = []
    for s in sessions:
        cost = sum(estimate_cost(u.model, u) for u in s.token_usage)
        data.append({
            "session_id": s.session_id,
            "title": s.ai_title or s.slug or "Untitled",
            "project": s.project_path,
            "entrypoint": s.entrypoint,
            "git_branch": s.git_branch,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "ended_at": s.ended_at.isoformat() if s.ended_at else None,
            "duration_seconds": s.duration_seconds,
            "user_messages": s.user_message_count,
            "total_tokens": s.total_tokens,
            "estimated_cost_usd": round(cost, 4),
            "models": [
                {
                    "model": u.model,
                    "input_tokens": u.input_tokens,
                    "output_tokens": u.output_tokens,
                    "cache_creation_tokens": u.cache_creation_tokens,
                    "cache_read_tokens": u.cache_read_tokens,
                    "message_count": u.message_count,
                }
                for u in s.token_usage
            ],
        })
    file_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Exported %d sessions to JSON: %s", len(sessions), file_path)
