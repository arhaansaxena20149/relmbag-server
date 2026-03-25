
from PyQt5.QtCore import QObject, pyqtSignal, QRunnable, QTimer
import time
from network import safe_request

class Worker(QRunnable):
    """
    A generic worker thread that runs a function and emits a signal with the result.
    """
    class Signals(QObject):
        finished = pyqtSignal(object)
        error = pyqtSignal(Exception)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = self.Signals()

    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.signals.finished.emit(result)
        except Exception as e:
            self.signals.error.emit(e)

class HeartbeatWorker(QObject):
    """
    A worker that sends a heartbeat to the server every 15 seconds.
    """
    kicked = pyqtSignal()
    banned = pyqtSignal()

    def __init__(self, username: str, session_token: str | None = None):
        super().__init__()
        self._username = username
        self._session_token = session_token
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.send_heartbeat)
        self._is_running = False

    def start(self):
        if not self._is_running:
            print("[DEBUG] Starting heartbeat worker.")
            self._is_running = True
            self._timer.start(15000)  # 15 seconds
            self.send_heartbeat() # Send a heartbeat immediately

    def stop(self):
        if self._is_running:
            print("[DEBUG] Stopping heartbeat worker.")
            self._is_running = False
            self._timer.stop()

    def send_heartbeat(self):
        if not self._is_running:
            return
        
        def heartbeat_thread():
            try:
                print("[DEBUG] Sending heartbeat.")
                from network import safe_json
                response = safe_request("post", "heartbeat", json={
                    "username": self._username,
                    "session_token": self._session_token
                })
                if response.status_code == 401:
                    print("[DEBUG] Heartbeat returned 401, user kicked.")
                    self.kicked.emit()
                elif response.status_code == 403:
                    print("[DEBUG] Heartbeat returned 403, user banned.")
                    self.banned.emit()
            except Exception as e:
                print(f"[ERROR] Heartbeat failed: {e}")

        # Run in a separate thread to avoid blocking the main thread
        import threading
        threading.Thread(target=heartbeat_thread).start()
