"""Global hotkey registration using Win32 RegisterHotKey API."""

import ctypes
import ctypes.wintypes
import logging
import threading

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger("monitor.hotkey")

# Win32 constants
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
HOTKEY_ID = 1

# Modifier keys
MOD_ALT = 0x0001

# Virtual key codes
VK_C = 0x43
VK_M = 0x4D
VK_U = 0x55

# Hotkey combos to try in order.
# Ctrl+Shift+C is tried first (works when Claude Code is not running),
# then Ctrl+Shift+M (M for Monitor) which is free even when Claude Code is open.
_HOTKEY_COMBOS = [
    (MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT, VK_C, "Ctrl+Shift+C"),
    (MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT, VK_M, "Ctrl+Shift+M"),
    (MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, VK_M, "Ctrl+Alt+M"),
    (MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT, VK_U, "Ctrl+Shift+U"),
    (MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, VK_U, "Ctrl+Alt+U"),
    (MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, VK_C, "Ctrl+Alt+C"),
]

user32 = ctypes.windll.user32


class GlobalHotkey(QObject):
    """Registers a global hotkey (best available combo). Emits activated() when pressed."""

    activated = Signal()
    registered = Signal(str)  # emits the combo name that was successfully registered

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread: threading.Thread | None = None
        self._running = False
        self._registered = False
        self.combo_name: str = ""  # set after successful registration

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            # Post a quit message to unblock GetMessage
            if self._thread.is_alive():
                self._thread.join(timeout=2)
        self._thread = None

    def _run(self):
        registered_name = None
        for modifiers, vk, name in _HOTKEY_COMBOS:
            result = user32.RegisterHotKey(None, HOTKEY_ID, modifiers, vk)
            if result:
                registered_name = name
                break
            logger.debug("Could not register %s, trying next...", name)

        if not registered_name:
            logger.warning("Failed to register any global hotkey. All combos taken.")
            return

        self._registered = True
        self.combo_name = registered_name
        self.registered.emit(registered_name)
        logger.info("Global hotkey %s registered", registered_name)

        msg = ctypes.wintypes.MSG()
        while self._running:
            # PeekMessage with PM_REMOVE to avoid blocking forever
            if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):  # PM_REMOVE=1
                if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                    self.activated.emit()
            else:
                # Small sleep to avoid busy-waiting
                import time
                time.sleep(0.05)

        user32.UnregisterHotKey(None, HOTKEY_ID)
        self._registered = False
        logger.info("Global hotkey unregistered")
