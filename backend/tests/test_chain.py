import os
import unittest

try:
    import main  # noqa: F401
    import providers
except ImportError as e:  # CI runs bare unittest without deps installed
    raise unittest.SkipTest(f"fastapi deps missing: {e}")

from providers import _effective_chain_env


class ChainPrecedenceTest(unittest.TestCase):
    """DATA_PROVIDER pin must win over DATA_PROVIDERS env chain (regression:
    the env chain used to silently override the pin, so the pinned provider
    never received traffic)."""

    def setUp(self):
        self._dp = os.environ.get("DATA_PROVIDER")
        self._dps = os.environ.get("DATA_PROVIDERS")

    def tearDown(self):
        for k, v in (("DATA_PROVIDER", self._dp), ("DATA_PROVIDERS", self._dps)):
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_pin_wins_over_env_chain(self):
        os.environ["DATA_PROVIDER"] = "scrapingbee"
        os.environ["DATA_PROVIDERS"] = "serpapi,zenrows,mock"
        self.assertEqual(_effective_chain_env().split(",")[0], "scrapingbee")
        self.assertNotIn("mock", _effective_chain_env().split(","))

    def test_pin_dedupes_env_chain(self):
        os.environ["DATA_PROVIDER"] = "serpapi"
        os.environ["DATA_PROVIDERS"] = "serpapi,scrapingbee"
        chain = _effective_chain_env().split(",")
        self.assertEqual(chain[0], "serpapi")
        self.assertEqual(chain.count("serpapi"), 1)

    def test_env_chain_without_pin(self):
        os.environ.pop("DATA_PROVIDER", None)
        os.environ["DATA_PROVIDERS"] = "serpapi,mock"
        chain = _effective_chain_env().split(",")
        self.assertEqual(chain, ["serpapi"])  # mock filtered out of known chain

    def test_unknown_pin_ignored(self):
        os.environ["DATA_PROVIDER"] = "doesnotexist"
        os.environ.pop("DATA_PROVIDERS", None)
        self.assertEqual(_effective_chain_env().split(",")[0], providers.DEFAULT_CHAIN[0])

    def test_main_effective_chain_matches_env_version(self):
        os.environ["DATA_PROVIDER"] = "scrapingbee"
        os.environ["DATA_PROVIDERS"] = "serpapi,zenrows"
        self.assertEqual(main._effective_chain(), _effective_chain_env().split(","))


if __name__ == "__main__":
    unittest.main()
