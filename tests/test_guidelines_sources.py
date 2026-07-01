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


if __name__ == "__main__":
    unittest.main()
