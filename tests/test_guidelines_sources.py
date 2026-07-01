"""The guideline-source registry: adding a source is a config entry, and the
generic crawler parses each source's index links (deriving a title when the
link regex doesn't capture one). Network mocked; no fetch, no store."""
from __future__ import annotations

import unittest
from unittest import mock


def _session(html: str):
    resp = mock.Mock()
    resp.text = html
    resp.raise_for_status = lambda: None
    sess = mock.Mock()
    sess.get = mock.Mock(return_value=resp)
    return sess


class GuidelineSourceRegistryTest(unittest.TestCase):
    def test_rch_source_parses_and_skips_non_guidelines(self):
        from localevidence.guidelines import crawl_index, SOURCES
        html = ('<a href="/clinicalguide/guideline_index/Asthma_acute/">Acute asthma</a>'
                '<a href="/clinicalguide/guideline_index/Croup">Croup</a>'
                '<a href="/clinicalguide/guideline_index/Search">Search</a>')
        out = crawl_index(_session(html), SOURCES["rch"])
        names = {n for n, _, _ in out}
        self.assertIn("Asthma_acute", names)
        self.assertIn("Croup", names)
        self.assertNotIn("Search", names)  # in _RCH_SKIP

    def test_aih_source_derives_title_from_name(self):
        from localevidence.guidelines import crawl_index, SOURCES
        html = ('<a href="/contents/vaccine-preventable-diseases/measles">Measles</a>'
                '<a href="/contents/vaccine-preventable-diseases/mumps">whatever</a>')
        out = crawl_index(_session(html), SOURCES["aih"])
        by_name = {n: (t, u) for n, t, u in out}
        self.assertIn("measles", by_name)
        self.assertEqual(by_name["measles"][0], "Measles")  # title derived from name
        self.assertTrue(by_name["measles"][1].startswith(
            "https://immunisationhandbook.health.gov.au/contents/"))

    def test_aih_is_registered_with_its_own_source_tag(self):
        from localevidence.guidelines import SOURCES
        self.assertEqual(SOURCES["aih"]["source"], "guideline:aih")
        self.assertEqual(SOURCES["aih"]["slug_prefix"], "aih-")

    def test_aih_seeds_cover_orphan_childhood_diseases(self):
        # measles/pertussis/etc. exist but aren't linked from the index or
        # sitemap, so they must be harvested via the curated seed-list.
        from localevidence.guidelines import SOURCES
        seeds = dict(SOURCES["aih"].get("seeds", []))
        self.assertIn("measles", seeds)
        self.assertTrue(any("pertussis" in name for name in seeds))
        # seeds carry a full path (paths are inconsistent across AIH)
        self.assertTrue(seeds["measles"].startswith("/contents/"))
        self.assertTrue(any(p.count("/") == 1 for p in seeds.values()))  # top-level ones too


class SkipPrefixTest(unittest.TestCase):
    def test_ascia_registered_with_source_tag(self):
        from localevidence.guidelines import SOURCES
        self.assertEqual(SOURCES["ascia"]["source"], "guideline:ascia")
        self.assertEqual(SOURCES["ascia"]["slug_prefix"], "ascia-")

    def test_skip_prefixes_drops_bibliography_pages(self):
        from localevidence.guidelines import crawl_index, SOURCES
        # ASCIA's /hp/papers/ index mixes real guidelines with references-* and
        # id-register-* pages; skip_prefixes must drop the latter, keep the former.
        html = ('<a href="/hp/papers/ascia-penicillin-allergy-guide">Penicillin</a>'
                '<a href="/hp/papers/references-crswnp-a-l">refs</a>'
                '<a href="/hp/papers/id-register-access-film">film</a>')
        out = crawl_index(_session(html), SOURCES["ascia"])
        names = {n for n, _, _ in out}
        self.assertIn("ascia-penicillin-allergy-guide", names)
        self.assertNotIn("references-crswnp-a-l", names)
        self.assertNotIn("id-register-access-film", names)


class PdfHarvestTest(unittest.TestCase):
    """_fetch_text routes PDF vs HTML so PDF-only sources (RANZCOG etc.) harvest."""

    def _resp(self, *, content, ctype, text=""):
        r = mock.Mock(); r.status_code = 200
        r.headers = {"Content-Type": ctype}; r.content = content; r.text = text
        s = mock.Mock(); s.get = mock.Mock(return_value=r)
        return s

    def test_pdf_magic_bytes_route_to_pdf_extractor(self):
        from localevidence import guidelines
        sess = self._resp(content=b"%PDF-1.5 ...", ctype="application/octet-stream")
        with mock.patch.object(guidelines, "_extract_pdf", return_value="PDFTEXT") as ep:
            out = guidelines._fetch_text(sess, "https://x/statement")  # no .pdf ext, octet-stream
        ep.assert_called_once()
        self.assertEqual(out, "PDFTEXT")

    def test_html_content_type_routes_to_html_cleaner(self):
        from localevidence import guidelines
        sess = self._resp(content=b"<html>", ctype="text/html",
                          text="<main>" + ("word " * 300) + "</main>")
        with mock.patch.object(guidelines, "_extract_pdf") as ep:
            out = guidelines._fetch_text(sess, "https://x/page")
        ep.assert_not_called()
        self.assertIn("word", out)

    def test_ranzcog_registered_as_pdf_source(self):
        from localevidence.guidelines import SOURCES
        self.assertIn("ranzcog", SOURCES)
        self.assertEqual(SOURCES["ranzcog"]["source"], "guideline:ranzcog")
        self.assertIn(r"\.pdf", SOURCES["ranzcog"]["link_re"])  # captures PDF links


class ImpersonateSessionTest(unittest.TestCase):
    """_make_session opts a source into curl-impersonate (for TLS-fingerprint
    bot-protected sites) when it's installed, and degrades safely when it isn't."""

    def test_normal_source_uses_plain_requests(self):
        import requests
        from localevidence.guidelines import _make_session
        self.assertIsInstance(_make_session({}), requests.Session)

    def test_impersonate_falls_back_to_requests_when_curl_cffi_absent(self):
        import requests
        from localevidence.guidelines import _make_session
        # curl_cffi isn't a hard dep; absence must degrade, not crash.
        s = _make_session({"impersonate": "chrome"})
        self.assertIsInstance(s, requests.Session)

    def test_impersonate_uses_curl_cffi_when_present(self):
        import sys
        from localevidence.guidelines import _make_session
        fake_sess = object()
        fake_creq = mock.Mock()
        fake_creq.Session = mock.Mock(return_value=fake_sess)
        fake_mod = mock.Mock(requests=fake_creq)
        with mock.patch.dict(sys.modules, {"curl_cffi": fake_mod,
                                           "curl_cffi.requests": fake_creq}):
            out = _make_session({"impersonate": "chrome"})
        self.assertIs(out, fake_sess)
        fake_creq.Session.assert_called_once()


if __name__ == "__main__":
    unittest.main()
