import ctypes
import sys

from PySide6.QtWidgets import QApplication

from app import SystemTrayApp


def main():
    # Single-instance check via Windows named mutex
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "ClaudeUsageMonitor_SingleInstance")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        sys.exit(0)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("Claude Usage Monitor")

    tray_app = SystemTrayApp()
    tray_app.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
