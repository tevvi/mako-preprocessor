import os
import json
import logging
import threading
import contextlib

_LOGGER = logging.getLogger(__name__)
META_FILE = ".mako_meta.json"

class MetadataManager:
    _instance = None
    _lock = threading.RLock()
    CURRENT_VERSION = "2.0.0"

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        _LOGGER.debug("Initializing MetadataManager")
        self._data = {}
        self._batch_active = 0
        self._batch_changed = False
        self._load()
        self._migrate()

    def _load(self):
        if os.path.exists(META_FILE):
            try:
                with open(META_FILE, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
                    _LOGGER.debug("Metadata loaded successfully")
            except json.JSONDecodeError:
                _LOGGER.warning("⚠️ Metadata file is corrupted. Creating a new one.")
                self._data = {}

    def _migrate(self):
        version = self._data.get("metadata_version")
        if version != self.CURRENT_VERSION:
            _LOGGER.info(f"Migrating metadata from version {version} to {self.CURRENT_VERSION}")
            # TODO: migration logic here
            self._data["metadata_version"] = self.CURRENT_VERSION
            self.save()

    def save(self):
        with self._lock:
            with open(META_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
                _LOGGER.debug("Metadata saved successfully")

    def get(self, key, default=None):
        value = self._data.get(key, default)
        _LOGGER.debug(f"Getting key: {key}, value: {value}")
        return value

    def set(self, key, value):
        _LOGGER.debug(f"Setting key: {key}, value: {value}")
        with self._lock:
            self._data[key] = value
            if self._batch_active == 0:
                self.save()
            else:
                self._batch_changed = True

    def update(self, new_data):
        _LOGGER.debug(f"Updating data: {new_data}")
        with self._lock:
            self._data.update(new_data)
            if self._batch_active == 0:
                self.save()
            else:
                self._batch_changed = True

    @property
    def data(self):
        _LOGGER.debug("Getting a copy of all data")
        return self._data.copy()

    def clear_all(self):
        self._data.clear()
        self._data["metadata_version"] = self.CURRENT_VERSION
        self.save()
        _LOGGER.debug("All metadata cleared")

    @contextlib.contextmanager
    def batch_update(self):
        self._batch_active += 1
        _LOGGER.debug(f"Starting batch update, level: {self._batch_active}")
        try:
            yield
        finally:
            self._batch_active -= 1
            if self._batch_active == 0 and self._batch_changed:
                self.save()
                self._batch_changed = False
            _LOGGER.debug(f"Batch update finished, level: {self._batch_active}")

    @property
    def version(self):
        return self._data.get("metadata_version", "unknown")

    def update_dependencies(self, file_path, dependencies):
        with self.batch_update():
            current_dependencies = self.get_dependencies(file_path)
            self.set_dependencies(file_path, list(dependencies))

            # Update dependent files
            for dep in dependencies:
                dependents = self.get_dependents(dep)
                if file_path not in dependents:
                    dependents.append(file_path)
                self.set_dependents(dep, dependents)

            # Remove outdated dependencies
            for dep in current_dependencies:
                if dep not in dependencies:
                    dependents = self.get_dependents(dep)
                    if file_path in dependents:
                        dependents.remove(file_path)
                    self.set_dependents(dep, dependents)

    def remove_dependency(self, file_path, dependency):
        dependencies = self.get_dependencies(file_path)
        if dependency in dependencies:
            dependencies.remove(dependency)
            self.set_dependencies(file_path, dependencies)
        
        dependents = self.get_dependents(dependency)
        if file_path in dependents:
            dependents.remove(file_path)
            self.set_dependents(dependency, dependents)

    def dependencies_key(self, file_path):
        return f"{file_path}_dependencies"

    def get_dependencies(self, file_path):
        return self.get(self.dependencies_key(file_path), [])
    
    def set_dependencies(self, file_path, dependencies):
        self.set(self.dependencies_key(file_path), dependencies)
    
    def dependents_key(self, file_path):
        return f"{file_path}_dependents"

    def get_dependents(self, file_path):
        return self.get(self.dependents_key(file_path), [])
    
    def set_dependents(self, file_path, dependents):
        self.set(self.dependents_key(file_path), dependents)

    def generated_files_key(self, file_path):
        return f"{file_path}_generated_files"
    
    def get_generated_files(self, file_path):
        return self.get(self.generated_files_key(file_path), [])

    def set_generated_files(self, file_path, generated_files):
        self.set(self.generated_files_key(file_path), list(generated_files))

    def remove_file_metadata(self, file_path):
        with self.batch_update():
            # Remove the file from dependencies of other files
            dependents = self.get_dependents(file_path)
            for dependent in dependents:
                self.remove_dependency(dependent, file_path)

            # Remove the file's own dependencies
            dependencies = self.get_dependencies(file_path)
            for dependency in dependencies:
                self.remove_dependency(file_path, dependency)

            # Remove the file's generated files
            generated_files = self.get_generated_files(file_path)
            for generated_file in generated_files:
                self._data.pop(generated_file, None)

            # Remove the file's metadata
            self._data.pop(self.dependencies_key(file_path), None)
            self._data.pop(self.dependents_key(file_path), None)
            self._data.pop(self.generated_files_key(file_path), None)
            self._data.pop(file_path, None)
