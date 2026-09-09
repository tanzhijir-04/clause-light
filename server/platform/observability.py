"""HTTP 请求追踪、Prometheus 指标和可选 OpenTelemetry 接入。"""

from __future__ import annotations

import logging
import re
import time
import uuid
from contextvars import ContextVar
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.routing import Match

from server.config import settings

logger = logging.getLogger(__name__)

REQUEST_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,63}")
request_id_var: ContextVar[str] = ContextVar("request_id", default="")

REQUEST_COUNT = Counter(
    "clauselight_http_requests_total",
    "Total HTTP requests handled by ClauseLight",
    ["method", "route", "status"],
)
REQUEST_DURATION = Histogram(
    "clauselight_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "route"],
)
JOBS_TOTAL = Counter(
    "clauselight_jobs_total",
    "Processing jobs observed by ClauseLight",
    ["job_type", "status"],
)
JOB_FAILURES = Counter(
    "clauselight_job_failures_total",
    "Processing job failures observed by ClauseLight",
    ["job_type"],
)

# 即使尚未有任务，也让 /metrics 暴露任务指标名称。
JOBS_TOTAL.labels("unknown", "none")
JOB_FAILURES.labels("unknown")


def _route_template(request: Request) -> str:
    """获取稳定的路由模板，避免把动态 ID 放进 Prometheus 标签。"""
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    if route_path:
        return route_path

    # 新版 Starlette 在中间件执行阶段可能尚未写入 scope["route"]，
    # 从应用路由表匹配完整路径，仍然只记录模板而不是动态参数。
    for candidate in request.app.routes:
        match, _ = candidate.matches(request.scope)
        if match is Match.FULL:
            route_path = getattr(candidate, "path", None)
            if route_path:
                return route_path

    # Starlette 1.6 在中间件阶段可能无法用 matches() 还原路由，
    # 用路由模板正则兼容，且不把动态参数值写进指标标签。
    request_path = request.scope.get("path", "")
    for candidate in request.app.routes:
        route_path = getattr(candidate, "path", None)
        route_regex = getattr(candidate, "path_regex", None)
        methods = getattr(candidate, "methods", None)
        if not route_path or route_regex is None:
            continue
        if methods and request.method not in methods:
            continue
        if route_regex.fullmatch(request_path):
            return route_path
    return "unmatched"


def record_job(job_type: str, status: str) -> None:
    """记录任务状态事件；标签只使用有限集合字段。"""
    JOBS_TOTAL.labels(job_type or "unknown", status or "unknown").inc()


def record_job_failure(job_type: str) -> None:
    """记录任务失败事件。"""
    JOB_FAILURES.labels(job_type or "unknown").inc()


def _configure_otel(app: FastAPI) -> None:
    """按配置启用 FastAPI instrumentation；依赖缺失时保持服务可启动。"""
    if not settings.OTEL_ENABLED:
        return
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider(
            resource=Resource.create({"service.name": "clauselight"})
        )
        exporter_kwargs: dict[str, Any] = {}
        if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
            exporter_kwargs["endpoint"] = settings.OTEL_EXPORTER_OTLP_ENDPOINT
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(**exporter_kwargs)))
        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
    except Exception as error:  # pragma: no cover - depends on optional runtime setup
        logger.warning("OpenTelemetry 初始化失败，继续提供 Prometheus 指标: %s", type(error).__name__)


def configure_observability(app: FastAPI) -> None:
    """注册请求上下文、结构化摘要日志和 metrics 端点。"""
    if getattr(app.state, "clauselight_observability_configured", False):
        return
    app.state.clauselight_observability_configured = True

    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next):
        incoming = request.headers.get("X-Request-ID", "")
        request_id = incoming if REQUEST_ID_PATTERN.fullmatch(incoming) else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        response = None
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            route_path = _route_template(request)
            duration = time.perf_counter() - started
            REQUEST_COUNT.labels(request.method, route_path, str(status_code)).inc()
            REQUEST_DURATION.labels(request.method, route_path).observe(duration)
            organization_id = getattr(request.state, "organization_id", "")
            logger.info(
                "http_request request_id=%s method=%s route=%s status=%s duration_ms=%.2f organization_id=%s",
                request_id,
                request.method,
                route_path,
                status_code,
                duration * 1000,
                organization_id or "unknown",
            )
            request_id_var.reset(token)

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        if not settings.METRICS_ENABLED:
            return Response(status_code=404)
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    _configure_otel(app)
