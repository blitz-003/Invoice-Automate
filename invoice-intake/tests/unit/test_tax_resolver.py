from app.services.tax_resolver import tax_code_for_rate


def test_standards():
    assert tax_code_for_rate(10) == ("T10", None)
    assert tax_code_for_rate(8) == ("T08", None)


def test_unknown_without_tax_defaults_t10():
    assert tax_code_for_rate(None, 0) == ("T10", None)
    assert tax_code_for_rate(None, None) == ("T10", None)


def test_unknown_with_tax_reason():
    code, reason = tax_code_for_rate(None, 330)
    assert code is None
    assert reason == "UNKNOWN_TAX_RATE"

    code2, reason2 = tax_code_for_rate(5, 100)
    assert code2 is None
    assert reason2 == "UNKNOWN_TAX_RATE"