"""Acceso HTTP al portal oficial del BOIB."""

import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class BoibClient:
    def __init__(self, timeout: int = 30, retries: int = 3) -> None:
        self.timeout = timeout
        self.retries = retries
        self.base_url = "https://www.caib.es/eboibfront/"
        self._cache: dict[str, tuple[bytes, str]] = {}

    def _get_body(self, url: str, cache: bool) -> tuple[bytes, str]:
        if cache and url in self._cache:
            return self._cache[url]

        request = Request(
            url,
            headers={
                "User-Agent": "BOIBScrap/0.1 (+consulta personal; Python urllib)",
                "Accept": "text/html,application/xhtml+xml,application/xml,application/pdf;q=0.9,*/*;q=0.8",
            },
        )
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    charset = response.headers.get_content_charset() or "utf-8"
                    body = response.read()
                    if cache:
                        self._cache[url] = (body, charset)
                    return body, charset
            except HTTPError as exc:
                last_error = exc
                if exc.code not in {429, 500, 502, 503, 504} or attempt == self.retries:
                    break
            except (URLError, TimeoutError, OSError) as exc:
                last_error = exc
                if attempt == self.retries:
                    break
            time.sleep(min(2 ** attempt, 8))

        raise RuntimeError(f"No se pudo consultar {url} tras varios intentos: {last_error}") from last_error

    def get_text(self, url: str) -> str:
        body, charset = self._get_body(url, cache=True)
        return body.decode(charset, errors="replace")

    def get_bytes(self, url: str) -> bytes:
        body, _charset = self._get_body(url, cache=False)
        return body
