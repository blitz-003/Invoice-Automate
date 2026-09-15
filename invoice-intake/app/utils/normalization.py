"""Japanese text, date and amount normalization helpers."""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import Optional

_COMPANY_SUFFIX_RE = re.compile(
    r"(株式会社|有限会社|合同会社|合名会社|合資会社|特例有限会社|(?:㈱)|(?:㊿)|農事組合法人|協同組合|財団法人|社団法人|学校法人|医療法人|株式会社は|(?:\(株\))|(?:（株）)|(?:\(有\))|(?:（有）))"
)
def normalize_text(value: str) -> str:
    """NFKC normalize + lowercase latin, trim, collapse whitespace."""
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFKC", str(value))
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.lower()
    normalized = re.sub(r"[\s\u3000]+", " ", normalized).strip()
    return normalized


def strip_company_suffix(value: str) -> str:
    """Remove common Japanese corporate suffixes for matching."""
    text = unicodedata.normalize("NFKC", str(value))
    text = _COMPANY_SUFFIX_RE.sub(" ", text)
    text = re.sub(r"[（）()]\s*", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" ・ー.,，。")
    return text


def normalized_key(value: str) -> str:
    """Canonical string used for partner matching."""
    return normalize_text(strip_company_suffix(value))


_ERA_OFFSETS = {
    "明治": 1868,
    "大正": 1912,
    "昭和": 1926,
    "平成": 1989,
    "令和": 2019,
}

_KANJI_DIGITS = {
    "〇": 0, "零": 0, "一": 1, "二": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
}

_ERA_DATE_RE = re.compile(
    r"((?:令和|平成|昭和|大正|明治))\s*([0-9０-９〇一二三四五六七八九]+)\s*[年.]\s*([0-9０-９一二三四五六七八九]+)\s*[月/.]\s*([0-9０-９一二三四五六七八九]+)\s*(?:日)?"
)
_ISO_DATE_RE = re.compile(
    r"([0-9０-９]{4})\s*[年/.\-－/]\s*([0-9０-９]{1,2})\s*[月/.\-－/]\s*([0-9０-９]{1,2})\s*(?:日)?"
)


def _num(value: str) -> int:
    value = value.strip()
    if re.fullmatch(r"[0-9０-９]+", value):
        return int(unicodedata.normalize("NFKC", value))
    if len(value) == 1 and value in _KANJI_DIGITS:
        return _KANJI_DIGITS[value]
    # mixed kanji number like 二〇二六
    total = 0
    for ch in value:
        if ch in _KANJI_DIGITS:
            total = total * 10 + _KANJI_DIGITS[ch]
        elif ch.isdigit():
            total = total * 10 + int(ch)
        else:
            return 0
    return total


def parse_japanese_date(value: str) -> Optional[date]:
    """Parse common Japanese date representations into an ISO date or None."""
    if not value:
        return None
    text = unicodedata.normalize("NFKC", str(value)).strip()
    text = text.replace("．", ".")

    m = _ERA_DATE_RE.search(text)
    if m:
        era, year, month, day = m.groups()
        year = _num(year)
        month = _num(month)
        day = _num(day)
        year += _ERA_OFFSETS[era] - 1
        if 1 <= month <= 12 and 1 <= day <= 31:
            try:
                return date(year, month, day)
            except ValueError:
                return None

    m = _ISO_DATE_RE.search(text)
    if m:
        year, month, day = (_num(g) for g in m.groups())
        if 1 <= month <= 12 and 1 <= day <= 31:
            try:
                return date(year, month, day)
            except ValueError:
                return None

    return None


_INT_RE = re.compile(r"[0-9０-９]+")


def parse_int(value: Optional[str]) -> Optional[int]:
    """Extract the first integer from a possibly-formatted amount string."""
    if value is None:
        return None
    text = unicodedata.normalize("NFKC", str(value))
    text = text.replace(",", "").replace("，", "").replace("．", ".")
    text = text.replace("円", "").replace("¥", "").replace("￥", "").replace("税込", "")
    if not text:
        return None
    match = _INT_RE.search(text)
    if not match:
        return None
    return int(match.group(0))