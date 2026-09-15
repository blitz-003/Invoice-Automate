from app.schema.fast_rules import FastRulesTemplate, TemplateField, load_schema


def test_schema_default_block_shape(schema: FastRulesTemplate):
    assert schema.tuple_name == "InvoiceData"
    names = [b.name for b in schema.blocks]
    assert {"SellerInfo", "BuyerInfo", "Invoice", "Item"} <= set(names)
    invoice = next(b for b in schema.blocks if b.name == "Invoice")
    assert "InvoiceNumber" in invoice.field_names()
    assert "TotalAmount" in invoice.field_names()
    item = next(b for b in schema.blocks if b.name == "Item")
    assert item.rows_constant is None
    assert item.ordinal_field == "Ord"


def test_all_fields_have_types():
    schema = load_schema()
    for block in schema.blocks:
        for field in block.fields:
            assert field.name
            assert field.raw_type in ("str", "int", "float", "number")


def test_named_year_parse():
    from app.schema.fast_rules import parse_year

    assert parse_year("令和") is None
    assert parse_year("2024年4月1日") == "2024"