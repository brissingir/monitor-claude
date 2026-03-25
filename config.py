import json
import os
from dataclasses import asdict
from pathlib import Path

from models import AppSettings


class AppConfig:
    APP_NAME = "ClaudeUsageMonitor"

    def __init__(self):
        self._dir = Path(os.environ.get("LOCALAPPDATA", Path.home())) / self.APP_NAME
        self._file = self._dir / "settings.json"

    def load(self) -> AppSettings:
        if not self._file.exists():
            return AppSettings()
        try:
            data = json.loads(self._file.read_text(encoding="utf-8"))
            return AppSettings(**{k: v for k, v in data.items() if k in AppSettings.__dataclass_fields__})
        except (json.JSONDecodeError, OSError, TypeError):
            return AppSettings()

    def save(self, settings: AppSettings):
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")

    @property
    def data_dir(self) -> Path:
        return self._dir
