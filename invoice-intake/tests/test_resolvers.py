from app.models.resolvers import ResolutionContext
from app.schema.fast_rules import load_schema
from app.services.resolvers import FieldResolver


def _values(**kwargs) -> dict:
    base = {
        "SellerInfo.SellerName": "株式会社 サンプル",
        "BuyerInfo.BuyerName": "株式会社 得意先",
        "Invoice.InvoiceNumber": "INV-2024-001",
        "Invoice.TotalAmount": "¥1,234,567",
        "Invoice.IssueDate": "2024年4月1日",
    }
    base.update(kwargs)
    return base


def test_resolve_clean_numbers():
    schema = load_schema()
    result = FieldResolver().resolve(schema, _values(), ResolutionContext())
    cleaned = result.cleaned["Invoice.TotalAmount"]
    assert cleaned.is_resolved
    assert cleaned.is_number
    assert cleaned.numeric_value == 1234567
    assert cleaned.value == "1234567"


def test_resolve_dates_normalized():
    schema = load_schema()
    result = FieldResolver().resolve(schema, _values(), ResolutionContext())
    cleaned = result.cleaned["Invoice.IssueDate"]
    assert cleaned.is_resolved
    assert cleaned.value == "2024-04-01"


def test_names_stripped():
    schema = load_schema()
    result = FieldResolver().resolve(
        schema,
        _values(**{"SellerInfo.SellerName": "  株式会社 サンプル、 "}),
        ResolutionContext(),
    )
    assert result.cleaned["SellerInfo.SellerName"].value == "株式会社 サンプル"


def test_overrides_win():
    schema = load_schema()
    overrides = {"Invoice.TotalAmount": "999"}
    result = FieldResolver().resolve(
        schema, _values(), ResolutionContext(overrides=overrides)
    )
    assert result.cleaned["Invoice.TotalAmount"].value == "999"


def test_missing_required_is_error():
    schema = load_schema()
    values = _values()
    values.pop("Invoice.InvoiceNumber")
    result = FieldResolver().resolve(schema, values, ResolutionContext())
    assert "Invoice.InvoiceNumber" not in result.cleaned
    assert any(e.field_name == "Invoice.InvoiceNumber" for e in result.errors)