import os
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock

# Mock HomeAssistant to avoid ModuleNotFoundError
class HomeAssistant:
    def __init__(self):
        self.services = MagicMock()

# Import the real setup function
from ...mako_preprocessor import setup, DOMAIN

class TestSetup(unittest.TestCase):
    def setUp(self):
        self.hass = HomeAssistant()
        self.temp_dir = tempfile.mkdtemp()
        self.test_mako_file = os.path.join(self.temp_dir, "test.yaml.mako")
        self.test_output_file = os.path.join(self.temp_dir, "test.yaml")
        
        with open(self.test_mako_file, "w") as f:
            f.write("key: value")

        self.config = {
            DOMAIN: {
                "directories": [self.temp_dir],
                "render_extensions": [".mako"],
                "run_on_start_ha": True,
                "hot_reload": False,
                "reload_behavior": "none",
                "batch_size": 1,
                "reload_frequency_secs": 1,
                "hot_reload_delay_secs": 1,
            }
        }

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    @patch("mako_preprocessor.RunPreprocessor.run")
    def test_setup_generates_file(self, mock_run):
        mock_run.side_effect = self._mock_run_preprocessor
        setup(self.hass, self.config)
        self.assertTrue(os.path.exists(self.test_output_file))
        with open(self.test_output_file, "r") as f:
            content = f.read()
        self.assertEqual(content, "key: value")

    def _mock_run_preprocessor(self):
        shutil.copyfile(self.test_mako_file, self.test_output_file)

if __name__ == "__main__":
    unittest.main()
