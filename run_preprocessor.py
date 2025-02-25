import logging
import os
from .utils import FileMatcher
from .preprocessor_worker import PreprocessorWorker
import traceback

_LOGGER = logging.getLogger(__name__)

class RunPreprocessor:
    def __init__(self, run_config):
        _LOGGER.debug("Initializing RunPreprocessor")
        self.run_config = run_config
        self.worker = PreprocessorWorker(run_config)

    def _feature_paths(self):
        _LOGGER.debug("Generating feature paths")
        for base_dir in self.run_config.directories:
            if not os.path.exists(base_dir):
                _LOGGER.warning(f"MAKO-012 ⚠️ Directory {base_dir} not found, skipping.")
                continue
            for root, _, files in os.walk(base_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    file_type, ext = FileMatcher.get_file_type(full_path, self.run_config)
                    if file_type:
                        _LOGGER.debug(f"File matched: {full_path}, type: {file_type}, extension: {ext}")
                        yield full_path

    def run(self):
        _LOGGER.debug("Running preprocessor")
        try:
            files_to_process = list(self._feature_paths())
            if files_to_process:
                self.worker.add_files(files_to_process)
                _LOGGER.info("✅ Files added to processing queue")
        except Exception as e:
            _LOGGER.error(f"MAKO-013 ❌ Error collecting files: {e}\n{traceback.format_exc()}")
