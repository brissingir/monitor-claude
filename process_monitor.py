"""Monitor running Claude Code processes using psutil."""

import logging
import time
from dataclasses import dataclass

import psutil

logger = logging.getLogger("monitor.process")

CLAUDE_PATTERNS = {"claude", "claude.exe"}
NODE_CLI_MARKERS = {"@anthropic-ai/claude-code", "claude-code"}


@dataclass
class ClaudeProcess:
    pid: int
    name: str
    memory_mb: float
    cpu_percent: float
    uptime_seconds: int
    cwd: str
    cmdline: str


def find_claude_processes() -> list[ClaudeProcess]:
    """Find running Claude Code processes. Returns a list of ClaudeProcess."""
    results: list[ClaudeProcess] = []
    now = time.time()

    for proc in psutil.process_iter(["pid", "name", "create_time"]):
        try:
            name = (proc.info["name"] or "").lower()
            pid = proc.info["pid"]

            # Direct match: claude.exe
            is_claude = name in CLAUDE_PATTERNS

            # Node process running Claude CLI
            if not is_claude and name in ("node.exe", "node"):
                try:
                    cmdline = proc.cmdline()
                    cmdline_str = " ".join(cmdline).lower()
                    is_claude = any(m in cmdline_str for m in NODE_CLI_MARKERS)
                except (psutil.AccessDenied, psutil.ZombieProcess):
                    continue

            if not is_claude:
                continue

            # Gather details
            try:
                mem = proc.memory_info().rss / (1024 * 1024)
                cpu = proc.cpu_percent(interval=0)
                create_time = proc.info["create_time"] or now
                uptime = int(now - create_time)
                cwd = ""
                try:
                    cwd = proc.cwd()
                except (psutil.AccessDenied, psutil.ZombieProcess, OSError):
                    pass
                cmdline_str = ""
                try:
                    cmdline_str = " ".join(proc.cmdline()[:3])
                except (psutil.AccessDenied, psutil.ZombieProcess):
                    pass

                results.append(ClaudeProcess(
                    pid=pid,
                    name=proc.info["name"] or "unknown",
                    memory_mb=round(mem, 1),
                    cpu_percent=round(cpu, 1),
                    uptime_seconds=max(0, uptime),
                    cwd=cwd,
                    cmdline=cmdline_str,
                ))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    logger.debug("Found %d Claude processes", len(results))
    return results


def kill_process(pid: int) -> bool:
    """Terminate a process by PID. Returns True on success."""
    try:
        proc = psutil.Process(pid)
        proc.terminate()
        proc.wait(timeout=5)
        logger.info("Terminated process PID %d", pid)
        return True
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired) as e:
        logger.warning("Failed to terminate PID %d: %s", pid, e)
        return False


def format_uptime(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    hours = seconds // 3600
    mins = (seconds % 3600) // 60
    return f"{hours}h {mins}m"
