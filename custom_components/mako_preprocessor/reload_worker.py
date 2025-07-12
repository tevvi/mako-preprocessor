import threading
import time
from queue import Queue, Empty
from .utils import get_logger

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
        self._logger = get_logger(type(self))
        self._logger.debug("Initializing ReloadWorker")
        self.run_config = run_config
        self.reload_queue = Queue()
        self.stop_event = threading.Event()
        self.worker_thread = threading.Thread(target=self._reload_worker, daemon=True)
        self.worker_thread.start()

    def _process_debounce(self, first_request_time):
        last_request_time = first_request_time

        while not self.stop_event.is_set():
            time_to_wait_from_last = self.run_config.reload_wait_min_secs - (time.time() - last_request_time)
            min_wait_time = time_to_wait_from_last

            if (hasattr(self.run_config, 'reload_wait_max_secs') and 
                self.run_config.reload_wait_max_secs):
                time_to_wait_from_first = self.run_config.reload_wait_max_secs - (time.time() - first_request_time)
                if time_to_wait_from_first < min_wait_time:
                    min_wait_time = time_to_wait_from_first

            if min_wait_time > 0:
                try:
                    while min_wait_time > 1:
                        min_wait_time -= 1
                        if self.stop_event.is_set():
                            break
                        self.reload_queue.get(timeout=1)
                    if self.stop_event.is_set():
                        break

                    last_request_time = self.reload_queue.get(timeout=min_wait_time)
                except Empty:
                    self.reload_ha()
                    break

            while not self.reload_queue.empty():
                last_request_time = self.reload_queue.get_nowait()
        
            current_time = time.time()
            time_since_first = current_time - first_request_time
            time_since_last = current_time - last_request_time

            # Проверяем максимальное время ожидания
            if (hasattr(self.run_config, 'reload_wait_max_secs') and 
                self.run_config.reload_wait_max_secs and 
                time_since_first >= self.run_config.reload_wait_max_secs):
                self._logger.debug("Maximum wait time exceeded, reloading")
                self.reload_ha()
                break
            
            # Проверяем минимальное время с последнего запроса
            if time_since_last >= self.run_config.reload_wait_min_secs:
                self._logger.debug("Minimum wait time after last request met, reloading")
                self.reload_ha()
                break

    def _reload_worker(self):
        self._logger = get_logger(type(self))
        self._logger.debug("Starting reload worker thread")

        while not self.stop_event.is_set():
            try:
                self._process_debounce(self.reload_queue.get(timeout=1))
            except Empty:
                continue

    def reload_ha(self):
        self._logger.debug("Reloading Home Assistant")
        if self.run_config.reload_behavior == "reload_core_config":
            self._logger.info("🔄 Reloading Home Assistant core config")
            self.run_config.hass.services.call("homeassistant", "reload_core_config")
        elif self.run_config.reload_behavior == "reload_all":
            self._logger.info("🔄 Reloading all Home Assistant scripts")
            self.run_config.hass.services.call("homeassistant", "reload_all")
        else:
            self._logger.info("ℹ️ Home Assistant reload not required")

    def request_reload(self):
        self._logger.debug("Requesting reload")
        self.reload_queue.put(time.time())

    def stop(self):
        self._logger.debug("Stopping ReloadWorker")
        self.stop_event.set()
