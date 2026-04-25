import unittest
from sbackup._compression import load_config

class TestCompression(unittest.TestCase):
    def test_load_config(self):
        config = load_config()
        self.assertEqual(config.compression_level, 5)
        self.assertEqual(config.auto_save_interval, 300)

if __name__ == '__main__':
    unittest.main()
