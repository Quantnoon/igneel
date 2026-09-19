"""Focused tests for the market agent's external research tools."""

import ast
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
import requests

import agent.web_tools as web_tools
from agent.agent_prompts import ATLAS_SYSTEM_PROMPT
from agent.paths import AGENT_ROOT


@pytest.fixture(autouse=True)
def clear_caches():
    web_tools._search_cache.clear()
    web_tools._page_cache.clear()
    yield
    web_tools._search_cache.clear()
    web_tools._page_cache.clear()


def test_web_search_uses_tavily_and_caches_success_for_one_hour(monkeypatch):
    now = [0.0]
    calls = []

    class FakeClient:
        def __init__(self, api_key):
            assert api_key == "test-key"

        def search(self, **kwargs):
            calls.append(kwargs)
            return {"results": [{"url": "https://example.com/news", "title": "News"}]}

    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    monkeypatch.setitem(sys.modules, "tavily", SimpleNamespace(TavilyClient=FakeClient))
    monkeypatch.setattr(web_tools.time, "monotonic", lambda: now[0])

    first = web_tools.web_search("XAUUSD latest news", 5)
    first["results"].clear()
    assert len(web_tools.web_search("  xauusd   latest news ", 5)["results"]) == 1
    assert calls == [{"query": "XAUUSD latest news", "max_results": 5, "search_depth": "advanced"}]

    now[0] = 3600.0
    assert web_tools.web_search("XAUUSD latest news", 5)["success"] is True
    assert len(calls) == 2


def test_web_search_reports_missing_key_and_does_not_cache_failure(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    missing = web_tools.web_search("EURUSD latest news")
    assert missing["success"] is False
    assert "TAVILY_API_KEY" in missing["error"]

    class FakeClient:
        def __init__(self, api_key):
            pass

        def search(self, **kwargs):
            return {"results": []}

    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    monkeypatch.setitem(sys.modules, "tavily", SimpleNamespace(TavilyClient=FakeClient))
    assert web_tools.web_search("EURUSD latest news")["success"] is True
    assert web_tools.web_search(" ")["success"] is False
    assert web_tools.web_search("query", max_results=11)["success"] is False


class FakeResponse:
    def __init__(self, *, chunks=(), content_type="text/html", status=200, location=None):
        self.chunks = chunks
        self.headers = {"Content-Type": content_type}
        if location is not None:
            self.headers["Location"] = location
        self.status = status
        self.encoding = "utf-8"
        self.closed = False

    @property
    def is_redirect(self):
        return 300 <= self.status < 400

    def raise_for_status(self):
        if self.status >= 400:
            raise requests.HTTPError(f"HTTP {self.status}")

    def iter_content(self, chunk_size):
        yield from self.chunks

    def close(self):
        self.closed = True


def public_dns(monkeypatch):
    monkeypatch.setattr(
        web_tools.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(None, None, None, None, ("93.184.215.14", 443))],
    )


def test_fetch_url_extracts_text_and_caches_for_one_hour(monkeypatch):
    public_dns(monkeypatch)
    now = [0.0]
    monkeypatch.setattr(web_tools.time, "monotonic", lambda: now[0])
    responses = []

    def fake_get(*args, **kwargs):
        response = FakeResponse(chunks=[b"<h1>Gold rises</h1><script>ignore me</script><p>Today</p>"])
        responses.append(response)
        assert kwargs["stream"] is True
        assert kwargs["allow_redirects"] is False
        return response

    monkeypatch.setattr(web_tools.requests, "get", fake_get)
    first = web_tools.fetch_url("https://example.com/news")
    assert "Source: https://example.com/news" in first
    assert "Gold rises" in first and "Today" in first
    assert "ignore me" not in first
    assert responses[0].closed is True
    assert web_tools.fetch_url("https://example.com/news") == first
    assert len(responses) == 1

    now[0] = 3600.0
    assert web_tools.fetch_url("https://example.com/news") == first
    assert len(responses) == 2


def test_fetch_url_rejects_private_redirect(monkeypatch):
    public_dns(monkeypatch)
    response = FakeResponse(status=302, location="http://127.0.0.1/admin")
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        return response

    monkeypatch.setattr(web_tools.requests, "get", fake_get)
    result = web_tools.fetch_url("https://example.com/news")
    assert "public addresses" in result
    assert calls == ["https://example.com/news"]
    assert response.closed is True
    assert "127.0.0.1" not in web_tools._page_cache


def test_fetch_url_limits_download_and_does_not_cache_failure(monkeypatch):
    public_dns(monkeypatch)
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        return FakeResponse(chunks=[b"x" * (web_tools._MAX_PAGE_BYTES + 1)])

    monkeypatch.setattr(web_tools.requests, "get", fake_get)
    assert "exceeds" in web_tools.fetch_url("https://example.com/large")
    assert "exceeds" in web_tools.fetch_url("https://example.com/large")
    assert len(calls) == 2


def test_fetch_url_limits_returned_text(monkeypatch):
    public_dns(monkeypatch)
    monkeypatch.setattr(
        web_tools.requests,
        "get",
        lambda *args, **kwargs: FakeResponse(chunks=[b"x" * (web_tools._MAX_PAGE_CHARS + 100)]),
    )
    result = web_tools.fetch_url("https://example.com/long")
    assert result.startswith("Source: https://example.com/long\n\n")
    assert len(result.split("\n\n", 1)[1]) == web_tools._MAX_PAGE_CHARS


def test_fetch_url_reports_network_errors_and_rejects_local_urls(monkeypatch):
    assert "public addresses" in web_tools.fetch_url("http://127.0.0.1/private")
    assert "HTTP or HTTPS" in web_tools.fetch_url("file:///etc/passwd")

    public_dns(monkeypatch)
    monkeypatch.setattr(
        web_tools.requests,
        "get",
        lambda *args, **kwargs: (_ for _ in ()).throw(requests.Timeout("timed out")),
    )
    assert "timed out" in web_tools.fetch_url("https://example.com/news")


def test_only_market_agent_registers_web_tools_and_prompt_requires_sources():
    module = ast.parse((AGENT_ROOT / "deep_agents.py").read_text(encoding="utf-8"))
    registrations = {}
    for statement in module.body:
        if not isinstance(statement, ast.Assign) or not isinstance(statement.value, ast.Call):
            continue
        if not any(isinstance(target, ast.Name) and target.id.endswith("_agent") for target in statement.targets):
            continue
        name = statement.targets[0].id
        tools_arg = next(keyword.value for keyword in statement.value.keywords if keyword.arg == "tools")
        registrations[name] = {item.id for item in tools_arg.elts}

    assert {"web_search", "fetch_url"} <= registrations["atlas_agent"]
    assert {"web_search", "fetch_url"}.isdisjoint(registrations["acnologia_agent"])
    assert {"web_search", "fetch_url"}.isdisjoint(registrations["ignia_agent"])
    assert "publication dates" in ATLAS_SYSTEM_PROMPT
    assert "source URL" in ATLAS_SYSTEM_PROMPT
    assert "broker price data" in ATLAS_SYSTEM_PROMPT
    assert "web context is unavailable" in ATLAS_SYSTEM_PROMPT
