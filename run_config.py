import json
import os
DOMAIN = "mako_preprocessor"

class RunConfig:
    DEFAULT_VALUES = {
        "hot_reload": True,
        "hot_reload_delay_secs": 30,
        "run_on_start_ha": True,
        "reload_frequency_secs": 5,
        "batch_size": 50,
        "hot_reload_extensions": [".yaml"],
        "backup_enabled": False,
        "backup_directory": "/backup"
    }
    
    def __init__(self, hass, **kwargs):
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
