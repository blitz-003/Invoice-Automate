from app.services.business_validators import validate_business


def test_clean_invoice():
    r = validate_business(
        issue_date="2024-04-01", due_date="2024-05-01",
        subtotal=2000, tax_amount=200, total_amount=2200,
        line_amount=2200,
    )
    assert not r.critical
    assert not r.reason_codes


def test_amount_mismatch():
    r = validate_business(
        issue_date="2024-04-01", due_date="2024-05-01",
        subtotal=2000, tax_amount=200, total_amount=2400,
        line_amount=2200,
    )
    assert "AMOUNT_MISMATCH" in r.reason_codes


def test_invalid_date_order():
    r = validate_business(
        issue_date="2024-06-01", due_date="2024-05-01",
        subtotal=100, tax_amount=10, total_amount=110, line_amount=110,
    )
    assert r.critical
    assert "INVALID_DATE" in r.reason_codes


def test_missing_issue_date():
    r = validate_business(issue_date=None, due_date="2024-05-01",
                          subtotal=None, tax_amount=None, total_amount=None,
                          line_amount=None)
    assert r.critical
    assert "INVALID_DATE" in r.reason_codes