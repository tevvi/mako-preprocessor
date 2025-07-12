import json
import os
import threading
from .utils import get_logger

DOMAIN = "mako_preprocessor"

class RunConfig:
    _instance = None
    _lock = threading.Lock()
    
    DEFAULT_VALUES = {
        "hot_reload": True,
        "hot_reload_delay_secs": 30,
        "run_on_start_ha": True,
        "reload_wait_min_secs": 1,
        "batch_size": 50,
        "hot_reload_extensions": [".yaml"],
        "backup_enabled": False,
        "backup_directory": "/backup"
    }
    
    def __new__(cls, hass=None, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    if hass is not None:
                        cls._instance._initialize(hass, **kwargs)
        elif hass is not None:
            cls._instance._initialize(hass, **kwargs)
        return cls._instance

    def _initialize(self, hass, **kwargs):
        self._logger = get_logger(type(self))
        self.hass = hass
        for key, value in kwargs.items():
            setattr(self, key, value)
        self.version = self._load_version()

    def _load_version(self):
        manifest_path = os.path.join(os.path.dirname(__file__), 'manifest.json')
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        return manifest.get('version', 'unknown')

    @staticmethod
    def from_setup_config(hass, config):
        params = {
            "directories": config["directories"],
            "render_extensions": config["render_extensions"],
            "serialize_extensions": config["serialize_extensions"],
            "overwrite_modified_files": config["overwrite_modified_files"],
            "enable_features": config["enable_features"],
            "reload_behavior": config["reload_behavior"],
            "constants": config.get("constants", {})
        }
        
        for key, default in RunConfig.DEFAULT_VALUES.items():
            params[key] = config.get(key, default)

        return RunConfig(hass, **params)

    def is_template_disabled(self):
        return "template" not in self.enable_features

    def is_render_disabled(self):
        return "render" not in self.enable_features

    def is_serialize_disabled(self):
        return "serialize" not in self.enable_features

    def is_hot_reload_disabled(self):
        return "hot_reload" not in self.enable_features
