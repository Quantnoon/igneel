"""Web research tools available to the market analysis agent."""

from copy import deepcopy
import ipaddress
import os
from pathlib import Path
import socket
from threading import Lock
import time
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from dotenv import load_dotenv
import requests

from agent.paths import ENV_FILE

load_dotenv(ENV_FILE)

_CACHE_SECONDS = 60 * 60
_MAX_PAGE_BYTES = 2_000_000
_MAX_PAGE_CHARS = 50_000
_MAX_REDIRECTS = 5
_cache_lock = Lock()
_search_cache: dict[tuple[str, int], tuple[float, dict]] = {}
_page_cache: dict[str, tuple[float, str]] = {}


def _cached(cache: dict, key):
    with _cache_lock:
        entry = cache.get(key)
        if entry is None:
            return None
        created_at, value = entry
        if time.monotonic() - created_at >= _CACHE_SECONDS:
            del cache[key]
            return None
        return deepcopy(value)


def _remember(cache: dict, key, value) -> None:
    with _cache_lock:
        cache[key] = (time.monotonic(), deepcopy(value))


def web_search(query: str, max_results: int = 5) -> dict:
    """Search the web for market context and goal-relevant trading material."""
    query = " ".join(query.split())
    if not query:
        return {"success": False, "error": "Search query must not be empty.", "results": []}
    if not isinstance(max_results, int) or isinstance(max_results, bool) or not 1 <= max_results <= 10:
        return {"success": False, "error": "max_results must be between 1 and 10.", "results": []}

    key = (query.casefold(), max_results)
    cached = _cached(_search_cache, key)
    if cached is not None:
        return cached

    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return {"success": False, "error": "TAVILY_API_KEY is not configured.", "results": []}

    try:
        from tavily import TavilyClient

        result = TavilyClient(api_key=api_key).search(
            query=query,
            max_results=max_results,
            search_depth="advanced",
        )
    except Exception as exc:
        return {"success": False, "error": f"Web search failed: {exc}", "results": []}

    if not isinstance(result, dict) or not isinstance(result.get("results"), list):
        return {"success": False, "error": "Web search returned an invalid response.", "results": []}

    result = {**result, "success": True}
    _remember(_search_cache, key, result)
    return deepcopy(result)


def _public_web_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("URL must use HTTP or HTTPS and include a host.")
    if parsed.username or parsed.password:
        raise ValueError("URLs containing credentials are not allowed.")
    try:
        port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    except ValueError as exc:
        raise ValueError("URL has an invalid port.") from exc

    try:
        literal_ip = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        literal_ip = None
    if literal_ip is not None and not literal_ip.is_global:
        raise ValueError("URL host must resolve only to public addresses.")

    try:
        addresses = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ValueError(f"Could not resolve URL host: {exc}") from exc
    if not addresses or any(not ipaddress.ip_address(info[4][0]).is_global for info in addresses):
        raise ValueError("URL host must resolve only to public addresses.")
    return url


def fetch_url(url: str) -> str:
    """Fetch readable text from a public webpage found through web search."""
    url = url.strip()
    if not url or len(url) > 2048:
        return "Unable to fetch URL: provide a URL of at most 2048 characters."

    cached = _cached(_page_cache, url)
    if cached is not None:
        return cached

    current_url = url
    for _ in range(_MAX_REDIRECTS + 1):
        try:
            _public_web_url(current_url)
            response = requests.get(
                current_url,
                timeout=(5, 20),
                stream=True,
                allow_redirects=False,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 Chrome/140.0 Safari/537.36"
                    )
                },
            )
            try:
                if response.is_redirect:
                    location = response.headers.get("Location")
                    if not location:
                        return f"Unable to fetch {url}: redirect has no destination."
                    current_url = urljoin(current_url, location)
                    continue

                response.raise_for_status()
                content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower().strip()
                if content_type and content_type not in {"text/html", "application/xhtml+xml", "text/plain"}:
                    return f"Unable to fetch {url}: unsupported content type {content_type}."

                chunks = []
                size = 0
                for chunk in response.iter_content(chunk_size=16_384):
                    size += len(chunk)
                    if size > _MAX_PAGE_BYTES:
                        return f"Unable to fetch {url}: page exceeds {_MAX_PAGE_BYTES} bytes."
                    chunks.append(chunk)

                html = b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")
                soup = BeautifulSoup(html, "html.parser")
                for element in soup(["script", "style", "noscript", "svg"]):
                    element.decompose()
                page_text = soup.get_text(separator="\n", strip=True)
                if not page_text:
                    return f"Unable to fetch {url}: page contains no readable text."
                result = f"Source: {current_url}\n\n{page_text[:_MAX_PAGE_CHARS]}"
                _remember(_page_cache, url, result)
                return result
            finally:
                response.close()
        except (ValueError, requests.RequestException) as exc:
            return f"Unable to fetch {url}: {exc}"

    return f"Unable to fetch {url}: too many redirects."
