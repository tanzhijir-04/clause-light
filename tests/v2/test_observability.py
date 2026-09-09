from __future__ import annotations

import re
from types import SimpleNamespace

from starlette.routing import Match

from server.platform.observability import _route_template


async def test_request_id_is_returned(v2_client, org_api_key) -> None:
    response = await v2_client.get(
        "/api/v2/tenancy/me",
        headers={"X-API-Key": org_api_key, "X-Request-ID": "req-test-001"},
    )
    assert response.headers["X-Request-ID"] == "req-test-001"


async def test_invalid_request_id_is_replaced(v2_client, org_api_key) -> None:
    response = await v2_client.get(
        "/api/v2/tenancy/me",
        headers={"X-API-Key": org_api_key, "X-Request-ID": "contract body should not be an id"},
    )
    request_id = response.headers["X-Request-ID"]
    assert request_id != "contract body should not be an id"
    assert re.fullmatch(r"[0-9a-f]{32}", request_id)


async def test_metrics_expose_bounded_route_labels(v2_client, org_api_key) -> None:
    await v2_client.get("/api/v2/tenancy/me", headers={"X-API-Key": org_api_key})
    response = await v2_client.get("/metrics")
    assert response.status_code == 200
    assert "clauselight_http_requests_total" in response.text
    assert 'route="/api/v2/tenancy/me"' in response.text
    assert "clauselight_jobs_total" in response.text
    assert not re.search(r"[0-9a-f]{32}", response.text)


def test_route_template_falls_back_to_template_regex_when_route_is_deferred() -> None:
    class DeferredRoute:
        path = "/api/v2/contracts/{contract_id}"
        methods = {"GET"}
        path_regex = re.compile(r"^/api/v2/contracts/[^/]+$")

        @staticmethod
        def matches(scope):
            return Match.NONE, {}

    request = SimpleNamespace(
        scope={"path": "/api/v2/contracts/0123456789abcdef0123456789abcdef"},
        app=SimpleNamespace(routes=[DeferredRoute()]),
        method="GET",
    )

    assert _route_template(request) == "/api/v2/contracts/{contract_id}"
