from localevidence import config
from localevidence.library import chunk_text


def test_norm_doi():
    assert config.norm_doi("https://doi.org/10.1/AbC") == "10.1/abc"
    assert config.norm_doi("HTTP://dx.doi.org/10.2/Z") == "10.2/z"
    assert config.norm_doi(None) == ""


def test_slugify_doi():
    assert config.slugify_doi("10.1/AbC.d") == "10-1-abc-d"


def test_classify_tier():
    assert config.classify_tier("A systematic review of X", "") == "systematic-review"
    assert config.classify_tier("Clinical practice guideline for Y", "") == "guideline"
    assert config.classify_tier("A randomized controlled trial", "") == "rct"
    assert config.classify_tier("Some paper", "", "journal-article") == "article"
    assert config.classify_tier("Nothing matches here", "") == "other"


def test_key_terms_dedup_and_stopwords():
    t = config.key_terms("What is the dose of diazepam for diazepam withdrawal?")
    assert "diazepam" in t and "withdrawal" in t
    assert "what" not in t and "the" not in t
    assert t.count("diazepam") == 1


def test_chunk_text_edges():
    assert chunk_text("") == []
    assert chunk_text("a b c") == ["a b c"]


def test_chunk_text_overlap_coverage():
    words = " ".join(str(i) for i in range(500))
    chunks = chunk_text(words, target_words=200, overlap_words=50)
    assert len(chunks) > 1
    assert all(len(c.split()) <= 200 for c in chunks)
    # step = 150, so chunk 2 starts at word 150
    assert chunks[1].split()[0] == "150"
