import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from affiliate import affiliate_url, invalidate_tags, tag_for


class AffiliateTagTest(unittest.TestCase):
    """Partner IDs resolve per marketplace (DB/admin edit first, env
    fallback); locales without a program get plain untagged links."""

    def setUp(self):
        invalidate_tags()
        self._saved = {k: os.environ.get(k) for k in
                       ("AMAZON_TAG_DE", "AMAZON_TAG_ES", "AMAZON_TAG_US")}
        for k in self._saved:
            os.environ.pop(k, None)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        invalidate_tags()

    def test_dach_shares_de_tag(self):
        os.environ["AMAZON_TAG_DE"] = "websters0d2-21"
        invalidate_tags()
        for mp in ("de", "at", "ch"):
            self.assertEqual(tag_for(mp), "websters0d2-21")

    def test_locales_without_program_are_untagged(self):
        os.environ["AMAZON_TAG_DE"] = "websters0d2-21"
        invalidate_tags()
        self.assertEqual(tag_for("com"), "")
        self.assertEqual(tag_for("fr"), "")

    def test_empty_tag_yields_plain_link(self):
        url = affiliate_url("B08NCPB1SM", "", "de")
        self.assertEqual(url, "https://www.amazon.de/dp/B08NCPB1SM")
        self.assertNotIn("tag=", url)

    def test_tagged_link(self):
        url = affiliate_url("B08NCPB1SM", "websters0d2-21", "de")
        self.assertIn("tag=websters0d2-21", url)
