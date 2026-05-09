import unittest
import os
import shutil
import tempfile
from pathlib import Path
from runtime_config import RuntimeConfig


class TestRuntimeConfig(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.env_patch = {}

    def tearDown(self):
        shutil.rmtree(self.test_dir)
        for k in self.env_patch:
            if self.env_patch[k] is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = self.env_patch[k]

    def set_env(self, key, value):
        if key not in self.env_patch:
            self.env_patch[key] = os.environ.get(key)
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value

    def test_default_dev_mode(self):
        # Clear relevant env vars
        for k in [
            "INIT_TRACKER_MODE", "INITTRACKER_MODE",
            "INIT_TRACKER_HOME", "INITTRACKER_HOME",
            "INIT_TRACKER_DATA_DIR", "INITTRACKER_DATA_DIR"
        ]:
            self.set_env(k, None)

        config = RuntimeConfig()
        self.assertEqual(config.mode, "development")
        self.assertFalse(config.is_production())
        # data_dir should default to ~/Documents/Dnd-Init-Yamls or similar
        self.assertTrue("Dnd-Init-Yamls" in str(config.data_dir))

    def test_production_mode_with_home(self):
        self.set_env("INIT_TRACKER_MODE", "production")
        self.set_env("INIT_TRACKER_HOME", str(self.test_dir))
        
        config = RuntimeConfig()
        self.assertEqual(config.mode, "production")
        self.assertTrue(config.is_production())
        self.assertEqual(config.home, str(self.test_dir))
        self.assertEqual(config.data_dir, self.test_dir / "data")
        self.assertEqual(config.log_dir, self.test_dir / "logs")
        self.assertEqual(config.releases_dir, self.test_dir / "releases")

    def test_legacy_env_support(self):
        self.set_env("INITTRACKER_MODE", "server")
        self.set_env("INITTRACKER_DATA_DIR", str(self.test_dir / "legacy_data"))
        
        config = RuntimeConfig()
        self.assertEqual(config.mode, "server")
        self.assertTrue(config.is_production())
        self.assertEqual(config.data_dir, (self.test_dir / "legacy_data").resolve())

    def test_new_env_overrides_legacy(self):
        self.set_env("INIT_TRACKER_MODE", "production")
        self.set_env("INITTRACKER_MODE", "development")
        
        config = RuntimeConfig()
        self.assertEqual(config.mode, "production")

    def test_ensure_dirs_production(self):
        self.set_env("INIT_TRACKER_MODE", "production")
        self.set_env("INIT_TRACKER_HOME", str(self.test_dir))
        
        config = RuntimeConfig()
        config.ensure_dirs()
        
        self.assertTrue((self.test_dir / "data").is_dir())
        self.assertTrue((self.test_dir / "logs").is_dir())
        self.assertTrue((self.test_dir / "releases").is_dir())

    def test_app_dir_override(self):
        self.set_env("INIT_TRACKER_APP_DIR", str(self.test_dir))
        config = RuntimeConfig()
        self.assertEqual(config.app_dir, self.test_dir.resolve())

    def test_network_settings(self):
        self.set_env("INIT_TRACKER_HOST", "1.2.3.4")
        self.set_env("INIT_TRACKER_PORT", "9999")
        self.set_env("INIT_TRACKER_PUBLIC_BASE_URL", "https://example.com/")
        
        config = RuntimeConfig()
        self.assertEqual(config.host, "1.2.3.4")
        self.assertEqual(config.port, 9999)
        self.assertEqual(config.public_base_url, "https://example.com/")

    def test_bad_port_fallback(self):
        self.set_env("INIT_TRACKER_PORT", "not-a-number")
        config = RuntimeConfig()
        self.assertEqual(config.port, 8787)


if __name__ == "__main__":
    unittest.main()
