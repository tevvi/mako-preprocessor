import json
import subprocess
import traceback
import yaml
import logging
import threading
import os

_LOGGER = logging.getLogger(__name__)

class ThreadSafeSet:
    def __init__(self):
        self._set = set()
        self._lock = threading.Lock()
        _LOGGER.debug("ThreadSafeSet initialized")

    def add(self, item):
        with self._lock:
            self._set.add(item)
            _LOGGER.debug(f"Item added to ThreadSafeSet: {item}")

    def remove(self, item):
        with self._lock:
            self._set.remove(item)
            _LOGGER.debug(f"Item removed from ThreadSafeSet: {item}")

    def empty(self):
        with self._lock:
            result = len(self._set) == 0
            _LOGGER.debug(f"ThreadSafeSet is empty: {result}")
            return result
        
    def __contains__(self, item):
        with self._lock:
            result = item in self._set
            _LOGGER.debug(f"Item checked in ThreadSafeSet: {item}, result: {result}")
            return result

class FileMatcher:
    @staticmethod
    def get_file_type(file_path, run_config):
        _LOGGER.debug(f"Getting file type for: {file_path}")
        if not run_config.is_serialize_disabled():
            for ext in run_config.serialize_extensions:
                if file_path.endswith(ext):
                    _LOGGER.debug(f"File matched as serialize: {file_path}, extension: {ext}")
                    return "serialize", ext

        if not run_config.is_render_disabled():
            for ext in run_config.render_extensions:
                if file_path.endswith(ext):
                    _LOGGER.debug(f"File matched as render: {file_path}, extension: {ext}")
                    return "render", ext

        if not run_config.is_hot_reload_disabled():
            for ext in run_config.hot_reload_extensions:
                if file_path.endswith(ext):
                    _LOGGER.debug(f"File matched as hot_reload: {file_path}, extension: {ext}")
                    return "hot_reload", ext
                    
        return None, None

class SerializedParser:
    @staticmethod
    def parse(file_path, matched_ext, constants=None):
        _LOGGER.debug(f"Parsing file: {file_path}, extension: {matched_ext}")
        try:
            file_path_without_ext = file_path[:-len(matched_ext)]
            if file_path_without_ext.endswith(".yaml"):
                with open(file_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    _LOGGER.debug(f"YAML file parsed: {file_path}")
                    return data
            elif file_path_without_ext.endswith(".json"):
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    _LOGGER.debug(f"JSON file parsed: {file_path}")
                    return data
            elif file_path_without_ext.endswith(".py"):
                env = os.environ.copy()
                if constants:
                    env.update(constants)
                result = subprocess.run(["python", file_path], capture_output=True, text=True, env=env)
                if result.returncode != 0:
                    _LOGGER.error(f"MAKO-001 ❌ Error executing Python file {file_path}: {result.stderr}")
                    return None
                data = json.safe_load(result.stdout)
                _LOGGER.debug(f"Python file executed and parsed: {file_path}, data: {data}")
                return data
            else:
                _LOGGER.error(f"MAKO-002 ❌ Unknown format {matched_ext} for file {file_path}. Skipping.")
                return None
        except Exception as e:
            _LOGGER.error(f"MAKO-003 ❌ Error parsing file {file_path}: {e}\n{traceback.format_exc()}")
            return None
