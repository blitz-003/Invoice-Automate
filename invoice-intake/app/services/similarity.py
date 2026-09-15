from __future__ import annotations


def ngram_relation(n: int, s1: str, s2: str) -> float:
    """Jaccard-style similarity over character n-grams in [0, 1]."""
    if not s1 or not s2:
        return 0.0
    a = _ngrams(n, s1)
    b = _ngrams(n, s2)
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def max_ngram_relation(n: int, s1: str, s2: str) -> float:
    """Assymmetry-correcting similarity by picking the best window alignment."""
    if not s1 or not s2:
        return 0.0
    a = _ngrams(n, s1)
    b = _ngrams(n, s2)
    if not a or not b:
        return 0.0
    return len(a & b) / max(len(a), len(b))


def _ngrams(n: int, s: str) -> set[str]:
    cleaned = "".join(ch for ch in s if not ch.isspace())
    if len(cleaned) < n:
        return {cleaned} if cleaned else set()
    return {cleaned[i : i + n] for i in range(len(cleaned) - n + 1)}