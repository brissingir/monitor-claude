import ctypes
import sys

from PySide6.QtWidgets import QApplication

from logging_config import setup_logging


def main():
    # Single-instance check via Windows named mutex
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "ClaudeUsageMonitor_SingleInstance")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        sys.exit(0)

    logger = setup_logging()
    logger.info("Starting Claude Usage Monitor")

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("Claude Usage Monitor")

    from app import SystemTrayApp
    tray_app = SystemTrayApp()
    tray_app.start()

    logger.info("Application running")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
