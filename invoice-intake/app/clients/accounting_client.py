from __future__ import annotations

import time
from typing import Optional

import httpx

from app.config import get_settings
from app.models.invoice import AccountingInvoiceRequest, AccountingResult, Partner, TaxCode


class AccountingAPIError(Exception):
    def __init__(self, code: str, message: str, details: Optional[dict] = None, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.retryable = retryable


_TRANSIENT_CODES = {"ACCOUNTING_SERVICE_ERROR", "ACCOUNTING_TIMEOUT", "ACCOUNTING_UNAVAILABLE"}


class AccountingClient:
    """Thin adapter around the mock accounting API. The only place that talks to it."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None,
                 timeout: float = 15.0, max_attempts: int = 3):
        settings = get_settings()
        self.base_url = (base_url or settings.accounting_api_url).rstrip("/")
        self.api_key = api_key or settings.accounting_api_key
        self.timeout = timeout
        self.max_attempts = max_attempts

    def _headers(self) -> dict:
        return {"X-API-Key": self.api_key}

    def _request(self, method: str, path: str, **kwargs) -> tuple[int, dict]:
        """Send a request with retry only for transient failures."""
        attempts = 0
        delay = 1.0
        while True:
            attempts += 1
            try:
                resp = httpx.request(method, f"{self.base_url}{path}",
                                     headers=self._headers(), timeout=self.timeout, **kwargs)
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout,
                    httpx.RemoteProtocolError) as exc:
                if attempts >= self.max_attempts:
                    raise AccountingAPIError("ACCOUNTING_UNAVAILABLE",
                                             f"Accounting API unreachable: {exc}", retryable=True)
                time.sleep(delay)
                delay *= 2
                continue

            body = self._parse(resp)
            if resp.status_code >= 500 and attempts < self.max_attempts:
                time.sleep(delay)
                delay *= 2
                continue
            return resp.status_code, body

    @staticmethod
    def _parse(resp: httpx.Response) -> dict:
        try:
            return resp.json()
        except ValueError:
            return {"success": False, "data": None,
                    "error": {"code": f"HTTP_{resp.status_code}", "message": "Invalid response body"}}

    def _map_error(self, status: int, body: dict) -> AccountingAPIError:
        err = body.get("error") or {}
        code = err.get("code") or ""
        message = err.get("message") or f"Accounting API error (HTTP {status})"
        details = err.get("details")
        if status == 401:
            return AccountingAPIError("ACCOUNTING_AUTH_ERROR", "Accounting API rejected the API key", details)
        if status == 409:
            return AccountingAPIError("DUPLICATE_INVOICE", message, details)
        if status == 422:
            return AccountingAPIError(code if code else "ACCOUNTING_VALIDATION_ERROR", message, details)
        if status == 400:
            return AccountingAPIError(code if code else "ACCOUNTING_VALIDATION_ERROR", message, details)
        if status == 404:
            return AccountingAPIError("ACCOUNTING_NOT_FOUND", message, details)
        return AccountingAPIError("ACCOUNTING_SERVICE_ERROR", message, details, retryable=True)

    def health(self) -> tuple[int, dict]:
        resp = httpx.get(f"{self.base_url}/health", timeout=self.timeout)
        return resp.status_code, self._parse(resp)

    def get_partners(self) -> list[Partner]:
        status, body = self._request("GET", "/partners")
        if status != 200:
            raise self._map_error(status, body)
        return [Partner(**p) for p in body["data"].get("partners", [])]

    def get_tax_codes(self) -> list[TaxCode]:
        status, body = self._request("GET", "/tax-codes")
        if status != 200:
            raise self._map_error(status, body)
        return [TaxCode(**t) for t in body["data"].get("tax_codes", [])]

    def list_invoices(self) -> list[dict]:
        status, body = self._request("GET", "/invoices")
        if status != 200:
            raise self._map_error(status, body)
        return body["data"].get("invoices", [])

    def delete_invoices(self) -> int:
        status, body = self._request("DELETE", "/invoices")
        if status != 200:
            raise self._map_error(status, body)
        return body["data"].get("removed", 0)

    def create_invoice(self, request: AccountingInvoiceRequest) -> AccountingResult:
        status, body = self._request("POST", "/invoices",
                                     json=request.model_dump(exclude_none=True))
        if status == 201:
            return AccountingResult(success=True,
                                    accounting_id=body["data"].get("accounting_id"),
                                    status_code=status)
        error = self._map_error(status, body)
        return AccountingResult(success=False, status_code=status,
                                error_code=error.code, error_message=error.message,
                                details=error.details)