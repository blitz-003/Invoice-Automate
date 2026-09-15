from __future__ import annotations

import hashlib


def sha256_file(file_path: str, chunk_size: int = 1 << 16) -> str:
    digest = hashlib.sha256()
    with open(file_path, "rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def duplicate_key(partner_code: str, invoice_number: str) -> str:
    return f"{partner_code}::{invoice_number}"