import logging
import os
from .utils import FileMatcher, get_logger
from .preprocessor_worker import PreprocessorWorker
import traceback

class RunPreprocessor:
    def __init__(self, run_config):
        self._logger = get_logger(type(self))
        self._logger.debug("Initializing RunPreprocessor")
        self.run_config = run_config
        self.worker = PreprocessorWorker(run_config)

    def _feature_paths(self):
        self._logger.debug("Generating feature paths")
        for base_dir in self.run_config.directories:
            if not os.path.exists(base_dir):
                self._logger.warning(f"MAKO-012 ⚠️ Directory {base_dir} not found, skipping.")
                continue
            for root, _, files in os.walk(base_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    file_type, ext = FileMatcher.get_file_type(full_path, self.run_config)
                    if file_type:
                        self._logger.debug(f"File matched: {full_path}, type: {file_type}, extension: {ext}")
                        yield full_path

    def run(self):
        self._logger.debug("Running preprocessor")
        try:
            files_to_process = list(self._feature_paths())
            if files_to_process:
                self.worker.add_files(files_to_process)
                self._logger.info("✅ Files added to processing queue")
        except Exception as e:
            self._logger.error(f"MAKO-013 ❌ Error collecting files: {e}\n{traceback.format_exc()}")
