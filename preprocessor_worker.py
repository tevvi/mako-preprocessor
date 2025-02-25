import os
import threading
import contextlib
import logging
from queue import Queue, Empty
import time
from .template_renderer import TemplateRenderer
from .reload_worker import ReloadWorker
from .utils import ThreadSafeSet
import traceback

_LOGGER = logging.getLogger(__name__)

class PreprocessorWorker:
    _instance = None
    _lock = threading.Lock()

    class Lock:
        _thread_lock = threading.Lock()

        @classmethod
        @contextlib.contextmanager
        def acquire(cls):
            _LOGGER.debug("Acquiring locks")
            with cls._thread_lock:
                _LOGGER.debug("Acquired thread lock")
                yield
            _LOGGER.debug("Released thread lock")

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
        _LOGGER.debug("Initializing PreprocessorWorker")
        self.run_config = run_config
        self.template_renderer = TemplateRenderer(run_config)
        self.render_queue = Queue()
        self.reload_pending = False
        self.stop_event = threading.Event()
        self.pending_hot_reload = {}
        self.queued_files = ThreadSafeSet()
        self.scheduled_files = ThreadSafeSet()
        self.reload_worker = ReloadWorker(run_config)
        self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.worker_thread.start()

    def add_file(self, file_path, from_hot_reload=False):
        _LOGGER.debug(f"Add file to queue: {file_path}, from_hot_reload: {from_hot_reload}")
        if file_path in self.queued_files or (from_hot_reload and file_path in self.scheduled_files):
            return
        
        self.queued_files.add(file_path)
        self.render_queue.put((file_path, from_hot_reload))

    def add_files(self, files):
        _LOGGER.debug(f"Add multiple files to queue: {files}")
        for file_path in files:
            self.add_file(file_path)

    def _should_process_file(self, file_path, from_hot_reload):
        _LOGGER.debug(f"Checking if file should be processed: {file_path}, from_hot_reload: {from_hot_reload}")
        
        if not os.path.exists(file_path) or not from_hot_reload:
            return {"should_process": True, "retry_after": None}
         
        try:
            current_time = time.time()
            file_mod_time = os.path.getmtime(file_path)
            
            if file_path in self.pending_hot_reload:
                last_known_mod_time = self.pending_hot_reload[file_path]
                if file_mod_time <= last_known_mod_time:
                    return {"should_process": False, "retry_after": None}
            
            time_since_mod = current_time - file_mod_time
            if time_since_mod < self.run_config.hot_reload_delay_secs:
                return {"should_process": False, "retry_after": self.run_config.hot_reload_delay_secs - time_since_mod}
                
            self.pending_hot_reload[file_path] = file_mod_time
            return {"should_process": True, "retry_after": None}
            
        except OSError:
            _LOGGER.error(f"MAKO-014 Error checking file {file_path}: {traceback.format_exc()}")
            return {"should_process": False, "retry_after": None}

    def _schedule_retry(self, file_path, retry_after, from_hot_reload):
        self.scheduled_files.add(file_path)
        threading.Timer(
            retry_after,
            lambda: self._reschedule_file(file_path, from_hot_reload)
        ).start()

    def _collect_batch_files(self, file_path, from_hot_reload):
        batch_files = set()
        while len(batch_files) < self.run_config.batch_size:
            try:
                self.render_queue.task_done()
                self.queued_files.remove(file_path)

                if file_path in batch_files:
                    continue

                result = self._should_process_file(file_path, from_hot_reload)
                if result["should_process"]:
                    batch_files.add(file_path)
                elif result["retry_after"] is not None:
                    self._schedule_retry(file_path, result["retry_after"], from_hot_reload)
                
                if len(batch_files) >= self.run_config.batch_size:
                    break

                file_path, from_hot_reload = self.render_queue.get_nowait()
            except Empty:
                break
        return batch_files

    def _process_queue(self):
        _LOGGER.debug("Starting to process queue")
        while not self.stop_event.is_set():
            try:
                batch_files = None
                _LOGGER.debug(f"Checking queue {self.render_queue.qsize()}")
                file_path, from_hot_reload = self.render_queue.get(timeout=1)
                batch_files = self._collect_batch_files(file_path, from_hot_reload)
                _LOGGER.debug(f"Collected batch of files: {len(batch_files)}")
                if batch_files:
                    with self.Lock.acquire():
                        self.template_renderer.process_batch(list(batch_files))
                        self.reload_pending = True

            except Empty:
                if not batch_files and self.render_queue.empty() and self.scheduled_files.empty() and self.reload_pending:
                    self.reload_worker.request_reload()
                    self.reload_pending = False
                continue
            except Exception as e:
                _LOGGER.error(f"MAKO-015 Error in preprocessor worker: {e}\n{traceback.format_exc()}")
                continue

    def schedule_hot_reload(self, file_path):
        _LOGGER.debug(f"Scheduling hot reload: {file_path}")
        if file_path in self.scheduled_files:
            return
        
        self._schedule_retry(file_path, self.run_config.hot_reload_delay_secs, from_hot_reload=True)

    def _reschedule_file(self, file_path, from_hot_reload):
        _LOGGER.debug(f"Rescheduling file: {file_path}, from_hot_reload: {from_hot_reload}")
        self.scheduled_files.remove(file_path)
        self.add_file(file_path, from_hot_reload)

    def stop(self):
        _LOGGER.debug("Stopping PreprocessorWorker")
        self.stop_event.set()