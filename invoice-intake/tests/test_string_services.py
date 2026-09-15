from app.services.similarity import max_ngram_relation, ngram_relation


def test_ngram_identical():
    assert ngram_relation(3, "株式会社やまだ", "株式会社やまだ") == 1.0


def test_ngram_common_substring():
    score = ngram_relation(3, "株式会社やまだ電気", "株式会社やまだ")
    assert score > 0.5


def test_ngram_empty():
    assert ngram_relation(3, "", "abc") == 0.0
    assert max_ngram_relation(2, "株式会社", "株式会社") == 1.0


def test_ngram_disjoint():
    assert ngram_relation(2, "abc", "xyz") == 0.0