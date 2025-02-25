import threading
import logging
import time
from queue import Queue, Empty

_LOGGER = logging.getLogger(__name__)

class ReloadWorker:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, run_config=None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize(run_config)
        elif run_config is not None:
            cls._instance.run_config = run_config
        return cls._instance

    def _initialize(self, run_config):
        _LOGGER.debug("Initializing ReloadWorker")
        self.run_config = run_config
        self.reload_queue = Queue()
        self.stop_event = threading.Event()
        self.worker_thread = threading.Thread(target=self._reload_worker, daemon=True)
        self.worker_thread.start()

    def _reload_worker(self):
        _LOGGER.debug("Starting reload worker thread")
        last_reload_time = 0
        
        while not self.stop_event.is_set():
            try:
                self.reload_queue.get(timeout=1)
                _LOGGER.debug("Reload request received")
                current_time = time.time()
                if current_time - last_reload_time < self.run_config.reload_frequency_secs:
                    time.sleep(self.run_config.reload_frequency_secs - (current_time - last_reload_time))
                
                self.reload_ha()
                last_reload_time = time.time()
                
                while not self.reload_queue.empty():
                    self.reload_queue.get_nowait()
                    
            except Empty:
                _LOGGER.debug("Reload queue is empty")
                continue

    def reload_ha(self):
        _LOGGER.debug("Reloading Home Assistant")
        if self.run_config.reload_behavior == "reload_core_config":
            _LOGGER.info("🔄 Reloading Home Assistant core config")
            self.run_config.hass.services.call("homeassistant", "reload_core_config")
        elif self.run_config.reload_behavior == "reload_all":
            _LOGGER.info("🔄 Reloading all Home Assistant scripts")
            self.run_config.hass.services.call("homeassistant", "reload_all")
        else:
            _LOGGER.info("ℹ️ Home Assistant reload not required")

    def request_reload(self):
        _LOGGER.debug("Requesting reload")
        self.reload_queue.put(True)

    def stop(self):
        _LOGGER.debug("Stopping ReloadWorker")
        self.stop_event.set()
