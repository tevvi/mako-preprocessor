import os
import time
import logging
import threading
from .metadata import MetadataManager
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from .utils import FileMatcher
from .preprocessor_worker import PreprocessorWorker

_LOGGER = logging.getLogger(__name__)

class HotReloadWorker:
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
        self.run_config = run_config
        self.observer = None
        self.metadata = MetadataManager()
        self.stop_event = threading.Event()
        self.preprocessor = PreprocessorWorker(run_config)
        self.worker_thread = threading.Thread(target=self._start_monitoring, daemon=True)
        self.worker_thread.start()

    class FileChangeHandler(FileSystemEventHandler):
        def __init__(self, worker: 'HotReloadWorker'):
            self.worker = worker

        def _handle_event(self, event, src_path):
            if event.is_directory:
                return
            file_type, _ = FileMatcher.get_file_type(src_path, self.worker.run_config)
            if file_type is not None:
                self.worker.preprocessor.schedule_hot_reload(src_path)
            else:
                dependents = self.worker.metadata.get_dependents(src_path)
                if dependents:
                    self.worker.preprocessor.schedule_hot_reload(src_path)

        def on_modified(self, event):
            self._handle_event(event, event.src_path)

        def on_created(self, event):
            self._handle_event(event, event.src_path)

        def on_deleted(self, event):
            self._handle_event(event, event.src_path)

        def on_moved(self, event):
            self._handle_event(event, event.src_path)
            self._handle_event(event, event.dest_path)

    def _start_monitoring(self):
        self.observer = Observer()
        handler = self.FileChangeHandler(self)
        for directory in self.run_config.directories:
            if os.path.exists(directory):
                self.observer.schedule(handler, directory, recursive=True)
        
        self.observer.start()
        
        while not self.stop_event.is_set():
            time.sleep(1)

        self.observer.stop()
        self.observer.join()

    def stop(self):
        if not self.stop_event.is_set():
            self.stop_event.set()
