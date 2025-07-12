from homeassistant.helpers import config_validation as cv
from .metadata import MetadataManager
import voluptuous as vol
from .run_preprocessor import RunPreprocessor
from .run_config import DOMAIN, RunConfig
from .hot_reload_worker import HotReloadWorker

def validate_extensions(config):
    render_ext = config.get("render_extensions", [])
    serialize_ext = config.get("serialize_extensions", [])
    
    # Check for empty extensions
    if not render_ext and not serialize_ext:
        raise vol.Invalid("render_extensions and serialize_extensions cannot both be empty")
    
    # Check for intersecting extensions
    intersected_extensions = set(render_ext) & set(serialize_ext)
    if intersected_extensions:
        raise vol.Invalid(f"The following extensions intersect: {', '.join(intersected_extensions)}")
    
    return config

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            vol.Schema(
                {
                    vol.Required("directories", default=["/config"]): vol.All(cv.ensure_list, [cv.isdir]),
                    vol.Optional("render_extensions", default=[".mako"]): vol.All(cv.ensure_list, [cv.string]),
                    vol.Optional("serialize_extensions", default=[".serialize"]): vol.All(cv.ensure_list, [cv.string]),
                    vol.Optional("overwrite_modified_files", default=False): cv.boolean,
                    vol.Optional("run_on_start_ha", default=True): cv.boolean,
                    vol.Optional("reload_behavior", default="reload_core_config"): vol.In(
                        ["reload_core_config", "reload_all", "none"]
                    ),
                    vol.Optional("enable_features", default=["render", "template", "serialize"]): vol.All(
                        cv.ensure_list,
                        [vol.In(["render", "template", "serialize"])],
                        vol.Length(min=1)
                    ),
                    vol.Optional("hot_reload", default=True): cv.boolean,
                    vol.Optional("hot_reload_delay_secs", default=30): vol.All(
                        cv.positive_int,
                        vol.Range(min=1, max=3600)
                    ),
                    vol.Optional("reload_wait_min_secs", default=1): vol.All(
                        cv.positive_int, 
                        vol.Range(min=0, max=3600)
                    ),
                    vol.Optional("reload_wait_max_secs"): vol.Any(
                        vol.All(cv.positive_int, vol.Range(min=0, max=3600)),
                        None
                    ),
                    vol.Optional("batch_size", default=50): vol.All(
                        cv.positive_int,
                        vol.Range(min=1, max=1000)
                    ),
                    vol.Optional("constants", default={}): vol.Schema({cv.string: cv.string}),
                    vol.Optional("hot_reload_extensions", default=[".yaml"]): vol.All(cv.ensure_list, [cv.string]),
                    vol.Optional("backup_enabled", default=False): cv.boolean,
                    vol.Optional("backup_directory", default="/config/backup"): cv.isdir,
                }
            ),
            validate_extensions
        )
    },
    extra=vol.ALLOW_EXTRA,
)

def setup(hass, config):
    run_config = RunConfig.from_setup_config(hass, config[DOMAIN])
    
    if run_config.hot_reload:
        HotReloadWorker(run_config)

    def handle_run_preprocessor(call):
        preprocessor = RunPreprocessor(run_config)
        preprocessor.run()

    def handle_view_metadata(call):
        metadata = MetadataManager()
        return metadata.data

    def handle_clear_metadata(call):
        metadata = MetadataManager()
        metadata.clear_all()

    hass.services.register(DOMAIN, "run_preprocessor", handle_run_preprocessor)
    hass.services.register(DOMAIN, "view_metadata", handle_view_metadata)
    hass.services.register(DOMAIN, "clear_metadata", handle_clear_metadata)

    if run_config.run_on_start_ha:
        preprocessor = RunPreprocessor(run_config)
        preprocessor.run()

    return True
