"""Regression tests for the 2026-09-04 audit fixes.

FastAPI/psycopg aren't importable in the bare CI sandbox? They are (installed
via requirements) — but these tests deliberately avoid the HTTP layer and test
the pure functions so they run everywhere (mirror of test_extractor.py style).
"""
import os
import unittest
from unittest import mock

try:
    import alerts
    import track
    from main import _admin_ok, _client_ip
except ImportError as e:  # CI sandbox has no backend deps; run where they exist
    raise unittest.SkipTest(f"backend deps not installed: {e}")


class FakeHeaders(dict):
    def get(self, k, default=None):
        return super().get(k.lower(), default)


class FakeClient:
    def __init__(self, host):
        self.host = host


class FakeRequest:
    def __init__(self, headers=None, peer="8.8.8.8"):
        self.headers = FakeHeaders(headers or {})
        self.client = FakeClient(peer) if peer else None


class AdminAuthTest(unittest.TestCase):
    def setUp(self):
        os.environ["ADMIN_KEY"] = "correct-horse"
        # keep the brute-force path inert (no redis in unit tests)
        patcher = mock.patch("cache._redis", create=True, return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _ok(self, headers, peer="8.8.8.8"):
        return _admin_ok(FakeRequest(headers, peer))

    def test_correct_key(self):
        self.assertTrue(self._ok({"x-admin-key": "correct-horse"}))

    def test_wrong_key(self):
        self.assertFalse(self._ok({"x-admin-key": "wrong"}))

    def test_non_ascii_key_is_401_not_500(self):
        # pre-fix: hmac.compare_digest(str, str) raised TypeError on 'éê중' → 500
        self.assertFalse(self._ok({"x-admin-key": "éê중"}))

    def test_no_key_env_disables_admin(self):
        with mock.patch.dict(os.environ, {"ADMIN_KEY": ""}):
            self.assertFalse(self._ok({"x-admin-key": "correct-horse"}))

    def test_missing_header(self):
        self.assertFalse(self._ok({}))


class ClientIpTest(unittest.TestCase):
    def test_public_peer_ignores_spoofed_x_real_ip(self):
        # direct internet peer must not be able to rotate its rate-limit key
        ip = _client_ip(FakeRequest({"x-real-ip": "1.2.3.4"}, peer="9.9.9.9"))
        self.assertEqual(ip, "9.9.9.9")

    def test_private_peer_trusts_x_real_ip(self):
        # behind Traefik (private peer) the proxy header wins
        ip = _client_ip(FakeRequest({"x-real-ip": "1.2.3.4"}, peer="172.26.0.5"))
        self.assertEqual(ip, "1.2.3.4")


class SaltTest(unittest.TestCase):
    def test_no_track_salt_means_no_hash(self):
        # pre-fix: TRACK_SALT defaulted to "pm" → daily hash reproducible by anyone
        with mock.patch.dict(os.environ, {"TRACK_SALT": ""}, clear=False):
            track.DAILY_SALT = ""
            self.assertEqual(track.ip_hash("1.2.3.4"), "")

    def test_salt_set_rotates_per_day_shape(self):
        with mock.patch.dict(os.environ, {"TRACK_SALT": "real-secret"}):
            track.DAILY_SALT = ""
            h = track.ip_hash("1.2.3.4")
            self.assertEqual(len(h), 16)
            self.assertEqual(h, track.ip_hash("1.2.3.4"))


class ScrubTest(unittest.TestCase):
    def test_api_key_redacted(self):
        s = "serpapi fetch failed: https://serpapi.com/search.json?api_key=SECRET123&engine=amazon"
        self.assertNotIn("SECRET123", alerts._scrub(s))
        self.assertIn("api_key=[REDACTED]", alerts._scrub(s))

    def test_generic_secret_params_redacted(self):
        s = "auth failed token=abc123 password=hunter2 ok"
        out = alerts._scrub(s)
        self.assertNotIn("abc123", out)
        self.assertNotIn("hunter2", out)


if __name__ == "__main__":
    unittest.main()
