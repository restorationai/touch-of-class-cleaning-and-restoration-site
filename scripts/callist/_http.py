"""Shared HTTP session: default 30s timeout + retries on idempotent calls.
Prevents a stalled socket from hanging the daily pipeline indefinitely."""
import requests
from requests.adapters import HTTPAdapter
try:
    from urllib3.util.retry import Retry
except Exception:  # older urllib3 bundled under requests
    from requests.packages.urllib3.util.retry import Retry


class _TimeoutSession(requests.Session):
    def request(self, *args, **kwargs):
        kwargs.setdefault("timeout", 30)
        return super().request(*args, **kwargs)


HTTP = _TimeoutSession()
# Retry only idempotent methods (GET/PUT/DELETE — POST excluded by default) on
# connection errors and transient 429/5xx, with backoff.
HTTP.mount("https://", HTTPAdapter(max_retries=Retry(
    total=3, connect=3, read=3, backoff_factor=1.0,
    status_forcelist=[429, 500, 502, 503, 504])))
