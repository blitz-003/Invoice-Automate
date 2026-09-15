from app.models.invoice import Partner
from app.services.partner_resolver import PartnerMatcher

PARTNERS = [
    Partner(partner_code="P1", name="株式会社サンプル商事", aliases=["サンプル商事"]),
    Partner(partner_code="P2", name="ACME Trading Co., Ltd.", aliases=["ACME", "ACME Trading"]),
    Partner(partner_code="P3", name="有限会社テストコーポレーション"),
]


def test_exact_match():
    m = PartnerMatcher(PARTNERS).match("ACME")
    assert m.matched
    assert m.partner_code == "P2"
    assert m.confidence >= 0.9


def test_kanji_match():
    m = PartnerMatcher(PARTNERS).match("株式会社サンプル商事")
    assert m.matched
    assert m.partner_code == "P1"


def test_no_match():
    m = PartnerMatcher(PARTNERS).match("全然知らない会社")
    assert not m.matched
    assert m.partner_code is None


def test_missing_name():
    m = PartnerMatcher(PARTNERS).match("")
    assert not m.matched