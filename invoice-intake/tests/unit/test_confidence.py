from app.services.confidence import classify_confidence, score_confidence


def test_bands():
    assert classify_confidence(0.95) == "verified"
    assert classify_confidence(0.97) == "verified"
    assert classify_confidence(0.88) == "likely"
    assert classify_confidence(0.80) == "expected"
    assert classify_confidence(0.50) == "low"
    assert classify_confidence(None) == "low"


def test_score_average():
    assert score_confidence([0.9, 1.0]).score == 0.95
    assert score_confidence([0.9, 1.0]).band == "verified"
    assert not score_confidence([0.9, 1.0]).needs_review
    assert score_confidence([0.5, 0.5]).needs_review


def test_score_empty():
    assert score_confidence(None).needs_review
    assert score_confidence([]).band == "low"