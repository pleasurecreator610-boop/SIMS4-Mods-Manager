"""Tests unitaires pour le décorateur resilient_network_call."""

import httpx
import pytest
from src.infrastructure.network.resilience import resilient_network_call


def test_resilience_success_first_try():
    calls = 0

    @resilient_network_call(max_retries=2)
    def my_fetch():
        nonlocal calls
        calls += 1
        return "OK"

    assert my_fetch() == "OK"
    assert calls == 1


def test_resilience_retry_on_429():
    calls = 0
    sleeps = []

    def mock_sleep(sec):
        sleeps.append(sec)

    request = httpx.Request("GET", "https://example.com/api")
    response_429 = httpx.Response(429, request=request, headers={"Retry-After": "2"})
    err_429 = httpx.HTTPStatusError("Too Many Requests", request=request, response=response_429)

    @resilient_network_call(max_retries=3, sleep_fn=mock_sleep)
    def flaky_api():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise err_429
        return "recovered"

    result = flaky_api()
    assert result == "recovered"
    assert calls == 3
    assert len(sleeps) == 2
    assert sleeps[0] == 2.0


def test_resilience_max_retries_exceeded():
    sleeps = []

    def mock_sleep(sec):
        sleeps.append(sec)

    request = httpx.Request("GET", "https://example.com/api")
    response_429 = httpx.Response(429, request=request)
    err_429 = httpx.HTTPStatusError("Too Many Requests", request=request, response=response_429)

    @resilient_network_call(max_retries=2, base_delay=0.1, sleep_fn=mock_sleep)
    def always_fails():
        raise err_429

    with pytest.raises(httpx.HTTPStatusError):
        always_fails()

    assert len(sleeps) == 2
