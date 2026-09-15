from app.schema.fast_rules import load_schema
from app.services.extractor import ExtractedData, parse_llm_output
from app.services.mapper import merge_extracts


def test_parse_yaml_header():
    schema = load_schema()
    yaml_text = """
Invoice.InvoiceNumber: INV-001
Invoice.TotalAmount: '1,200'
SellerInfo.SellerName: 株式会社サンプル
"""
    data = parse_llm_output(yaml_text, schema)
    assert data.header["Invoice.InvoiceNumber"] == "INV-001"
    assert data.header["SellerInfo.SellerName"] == "株式会社サンプル"


def test_parse_yaml_items():
    schema = load_schema()
    yaml_text = """
Item[1].ItemName: サービスA
Item[1].Quantity: '2'
Item[1].UnitPrice: '500'
Item[2].ItemName: サービスB
Item[2].LineAmount: '1000'
"""
    data = parse_llm_output(yaml_text, schema)
    assert len(data.items) == 2
    assert data.items[0]["ItemName"] == "サービスA"
    assert data.items[0]["Quantity"] == "2"


def test_parse_fenced_yaml():
    schema = load_schema()
    data = parse_llm_output("```yaml\nInvoice.InvoiceNumber: INV-9\n```", schema)
    assert data.header["Invoice.InvoiceNumber"] == "INV-9"


def test_parse_flat_repeated_key_items():
    """Some models emit items as one flat map with repeated keys (duplicates are YAML-invalid);
    rows must be recovered instead of silently collapsed to the last occurrence."""
    schema = load_schema()
    yaml_text = """
SellerInfo:
  SellerName: 株式会社サンプル
Invoice:
  InvoiceNumber: INV-7
Item:
  Ord: "1"
  ItemName: 品目A
  Quantity: "24"
  UnitPrice: 2800
  LineAmount: 67200
  Ord: "2"
  ItemName: 品目B
  Quantity: "30"
  UnitPrice: 1200
  LineAmount: 36000
"""
    data = parse_llm_output(yaml_text, schema)
    assert data.header["Invoice.InvoiceNumber"] == "INV-7"
    assert len(data.items) == 2
    assert data.items[0] == {"Ord": "1", "ItemName": "品目A", "Quantity": "24",
                             "UnitPrice": "2800", "LineAmount": "67200"}
    assert data.items[1]["ItemName"] == "品目B"


def test_parse_flat_item_block_mixes_with_header():
    """Flat repeated-key item block must not clobber sibling header blocks."""
    schema = load_schema()
    yaml_text = """
Invoice.InvoiceNumber: INV-11
Item:
  Ord: "1"
  ItemName: A
  Ord: "2"
  ItemName: B
"""
    data = parse_llm_output(yaml_text, schema)
    assert data.header["Invoice.InvoiceNumber"] == "INV-11"
    assert [r["ItemName"] for r in data.items] == ["A", "B"]


def test_merge_primary_wins():
    schema = load_schema()
    primary = ExtractedData(header={"SellerInfo.SellerName": "A社"})
    secondary = ExtractedData(header={"SellerInfo.SellerName": "B社",
                                      "BuyerInfo.BuyerName": "C社"})
    merged = merge_extracts(primary, secondary, schema)
    assert merged.header["SellerInfo.SellerName"] == "A社"
    assert merged.header["BuyerInfo.BuyerName"] == "C社"


def test_merge_items_by_ordinal():
    schema = load_schema()
    primary = ExtractedData(items=[{"Ord": "1", "ItemName": "品目A", "Quantity": "1"}])
    secondary = ExtractedData(items=[{"Ord": "1", "ItemName": "品目A", "UnitPrice": "100"}])
    merged = merge_extracts(primary, secondary, schema)
    assert len(merged.items) == 1
    assert merged.items[0]["UnitPrice"] == "100"
    assert merged.items[0]["Quantity"] == "1"