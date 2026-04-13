
from PyQt5.QtCore import QObject, pyqtSignal, QRunnable, QTimer
from network import debug_log, safe_request

class Worker(QRunnable):
    """
    A generic worker thread that runs a function and emits a signal with the result.
    """
    class Signals(QObject):
        finished = pyqtSignal(object)
        error = pyqtSignal(object)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = self.Signals()

    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
            try:
                self.signals.finished.emit(result)
            except RuntimeError:
                # The receiver may have been deleted during shutdown/navigation.
                pass
        except BaseException as e:
            try:
                self.signals.error.emit(e)
            except RuntimeError:
                pass

class HeartbeatWorker(QObject):
    """
    A worker that sends a heartbeat to the server every 15 seconds.
    """
    kicked = pyqtSignal()
    banned = pyqtSignal()
    status_updated = pyqtSignal(dict) # FIX: Signal for instant synchronization

    def __init__(self, username: str, session_token: str | None = None):
        super().__init__()
        self._username = username
        self._session_token = session_token
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.send_heartbeat)
        self._is_running = False
        self._request_in_flight = False

    def start(self):
        if not self._is_running:
            debug_log("[DEBUG] Starting heartbeat worker.")
            self._is_running = True
            self._timer.start(10000)
            self.send_heartbeat() # Send a heartbeat immediately

    def stop(self):
        if self._is_running:
            debug_log("[DEBUG] Stopping heartbeat worker.")
            self._is_running = False
            self._timer.stop()

    def send_heartbeat(self):
        if not self._is_running or self._request_in_flight:
            return
        
        def heartbeat_thread():
            self._request_in_flight = True
            try:
                from network import safe_json
                response = safe_request("post", "heartbeat", json={
                    "username": self._username,
                    "session_token": self._session_token
                })
                if response.status_code == 401:
                    debug_log("[DEBUG] Heartbeat returned 401, user kicked.")
                    self.kicked.emit()
                elif response.status_code == 403:
                    debug_log("[DEBUG] Heartbeat returned 403, user banned.")
                    self.banned.emit()
                elif response.status_code == 200:
                    payload = safe_json(response)
                    if isinstance(payload, dict) and payload.get("status") == "ok":
                        self.status_updated.emit(payload)
            except Exception as e:
                debug_log(f"[ERROR] Heartbeat failed: {e}")
            finally:
                self._request_in_flight = False

        # Run in a separate thread to avoid blocking the main thread
        import threading
        threading.Thread(target=heartbeat_thread, daemon=True).start()
