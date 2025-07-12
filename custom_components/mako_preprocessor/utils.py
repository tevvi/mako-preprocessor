import json
import subprocess
import traceback
import yaml
import logging
import threading
import os
from datetime import datetime

class ClassLoggerAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        class_name = self.extra.get('class_name', '')
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        pid = os.getpid()
        tid = threading.get_ident()
        return f"[{now}] [PID:{pid}] [TID:{tid}] [{class_name}] {msg}", kwargs

def get_logger(class_or_name):
    name = class_or_name if isinstance(class_or_name, str) else class_or_name.__name__
    return ClassLoggerAdapter(logging.getLogger(__name__), {'class_name': name})

class ThreadSafeSet:
    def __init__(self):
        self._set = set()
        self._lock = threading.Lock()
        self._logger = get_logger(type(self))
        self._logger.debug("ThreadSafeSet initialized")

    def add(self, item):
        with self._lock:
            self._set.add(item)
            self._logger.debug(f"Item added to ThreadSafeSet: {item}")

    def remove(self, item):
        with self._lock:
            self._set.remove(item)
            self._logger.debug(f"Item removed from ThreadSafeSet: {item}")

    def empty(self):
        with self._lock:
            result = len(self._set) == 0
            self._logger.debug(f"ThreadSafeSet is empty: {result}")
            return result
        
    def __contains__(self, item):
        with self._lock:
            result = item in self._set
            self._logger.debug(f"Item checked in ThreadSafeSet: {item}, result: {result}")
            return result

class FileMatcher:
    _logger = get_logger("FileMatcher")
    @staticmethod
    def get_file_type(file_path, run_config):
        FileMatcher._logger.debug(f"Getting file type for: {file_path}")
        if not run_config.is_serialize_disabled():
            for ext in run_config.serialize_extensions:
                if file_path.endswith(ext):
                    FileMatcher._logger.debug(f"File matched as serialize: {file_path}, extension: {ext}")
                    return "serialize", ext

        if not run_config.is_render_disabled():
            for ext in run_config.render_extensions:
                if file_path.endswith(ext):
                    FileMatcher._logger.debug(f"File matched as render: {file_path}, extension: {ext}")
                    return "render", ext

        if not run_config.is_hot_reload_disabled():
            for ext in run_config.hot_reload_extensions:
                if file_path.endswith(ext):
                    FileMatcher._logger.debug(f"File matched as hot_reload: {file_path}, extension: {ext}")
                    return "hot_reload", ext
                    
        return None, None

class SerializedParser:
    _logger = get_logger("SerializedParser")
    @staticmethod
    def parse(file_path, matched_ext, constants=None):
        SerializedParser._logger.debug(f"Parsing file: {file_path}, extension: {matched_ext}")
        try:
            file_path_without_ext = file_path[:-len(matched_ext)]
            if file_path_without_ext.endswith(".yaml"):
                with open(file_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    SerializedParser._logger.debug(f"YAML file parsed: {file_path}")
                    return data
            elif file_path_without_ext.endswith(".json"):
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    SerializedParser._logger.debug(f"JSON file parsed: {file_path}")
                    return data
            elif file_path_without_ext.endswith(".py"):
                env = os.environ.copy()
                if constants:
                    env.update(constants)
                result = subprocess.run(["python", file_path], capture_output=True, text=True, env=env)
                if result.returncode != 0:
                    SerializedParser._logger.error(f"MAKO-001 ❌ Error executing Python file {file_path}: {result.stderr}")
                    return None
                data = json.safe_load(result.stdout)
                SerializedParser._logger.debug(f"Python file executed and parsed: {file_path}, data: {data}")
                return data
            else:
                SerializedParser._logger.error(f"MAKO-002 ❌ Unknown format {matched_ext} for file {file_path}. Skipping.")
                return None
        except Exception as e:
            SerializedParser._logger.error(f"MAKO-003 ❌ Error parsing file {file_path}: {e}\n{traceback.format_exc()}")
            return None
