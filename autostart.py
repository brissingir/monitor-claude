import os
import subprocess
from pathlib import Path

SHORTCUT_NAME = "ClaudeUsageMonitor.lnk"
PROJECT_DIR = Path(__file__).parent.resolve()


def _startup_dir() -> Path:
    return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def _shortcut_path() -> Path:
    return _startup_dir() / SHORTCUT_NAME


def is_installed() -> bool:
    return _shortcut_path().exists()


def install():
    target = str(PROJECT_DIR / "venv" / "Scripts" / "pythonw.exe")
    workdir = str(PROJECT_DIR)
    shortcut = str(_shortcut_path())

    ps_script = (
        '$ws = New-Object -ComObject WScript.Shell; '
        f'$s = $ws.CreateShortcut("{shortcut}"); '
        f'$s.TargetPath = "{target}"; '
        f'$s.Arguments = "main.py"; '
        f'$s.WorkingDirectory = "{workdir}"; '
        '$s.Save()'
    )
    subprocess.run(["powershell", "-Command", ps_script], check=True)


def uninstall():
    path = _shortcut_path()
    if path.exists():
        path.unlink()


if __name__ == "__main__":
    if is_installed():
        print("Autostart already installed. Removing...")
        uninstall()
        print("Removed.")
    else:
        print("Installing autostart...")
        install()
        print(f"Shortcut created at: {_shortcut_path()}")
