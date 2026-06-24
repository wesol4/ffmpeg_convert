"""Testy app/update.py (bez sieci — mock fetch_latest_version)."""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import update  # noqa: E402


class TestNormalize(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(update._normalize("v1.2.3"), (1, 2, 3))
        self.assertEqual(update._normalize("1.2"), (1, 2))
        self.assertEqual(update._normalize("2.0.10"), (2, 0, 10))

    def test_comparison(self):
        self.assertLess(update._normalize("1.2.3"), update._normalize("1.2.10"))
        self.assertGreater(update._normalize("2.0"), update._normalize("1.99.99"))


class TestCheckForUpdates(unittest.TestCase):
    def test_newer_available(self):
        with mock.patch("app.update.fetch_latest_version", return_value="v9.9.9"):
            has, latest, msg = update.check_for_updates("0.7.0")
        self.assertTrue(has)
        self.assertEqual(latest, "v9.9.9")
        self.assertIn("v9.9.9", msg)

    def test_up_to_date(self):
        with mock.patch("app.update.fetch_latest_version", return_value="v0.7.0"):
            has, latest, msg = update.check_for_updates("0.7.0")
        self.assertFalse(has)
        self.assertIn("najnowszą", msg)

    def test_network_failure(self):
        with mock.patch("app.update.fetch_latest_version", return_value=None):
            has, latest, msg = update.check_for_updates("0.7.0")
        self.assertFalse(has)
        self.assertIsNone(latest)
        self.assertIn("Nie udało się", msg)


if __name__ == "__main__":
    unittest.main()
