"""
telemetry.py — OTel 관측 설정 전담 모듈 (Windows 네이티브)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import logging
import platform
from collections import deque
from datetime import datetime

from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

# OTel Logs SDK — 버전에 따라 경로가 다름, 두 경로 모두 시도
try:
    from opentelemetry.sdk.logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk.logs.export import BatchLogRecordProcessor
    from opentelemetry.exporter.otlp.proto.grpc.exporter import OTLPLogExporter
    from opentelemetry import _logs
except ImportError:
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
    from opentelemetry import _logs

# ── OTel Collector 주소 ──────────────────────────────────────────
OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

# ── 서비스 정보 ───────────────────────────────────────────────────
resource = Resource.create({
    "service.name":           "fisa-windows-bank",
    "service.version":        "2.1.0",
    "deployment.environment": "demo",
    "host.name":              platform.node(),
})

# ── Trace Provider ────────────────────────────────────────────────
_trace_provider = TracerProvider(resource=resource)
_trace_exporter = OTLPSpanExporter(endpoint=OTEL_ENDPOINT, insecure=True)
_trace_provider.add_span_processor(BatchSpanProcessor(_trace_exporter))
trace.set_tracer_provider(_trace_provider)

tracer = trace.get_tracer("fisa-bank")

# ── Metric Provider ───────────────────────────────────────────────
_metric_exporter = OTLPMetricExporter(endpoint=OTEL_ENDPOINT, insecure=True)
_metric_reader   = PeriodicExportingMetricReader(_metric_exporter, export_interval_millis=5000)
_meter_provider  = MeterProvider(resource=resource, metric_readers=[_metric_reader])
metrics.set_meter_provider(_meter_provider)

meter = metrics.get_meter("fisa-bank")

request_counter          = meter.create_counter(name="http_requests_total", unit="1")
error_counter            = meter.create_counter(name="http_errors_total", unit="1")
response_time_histogram  = meter.create_histogram(name="http_response_time_ms", unit="ms")
active_requests          = meter.create_up_down_counter(name="active_requests", unit="1")

# ── Log Provider ──────────────────────────────────────────────────
_log_provider = LoggerProvider(resource=resource)
_log_exporter = OTLPLogExporter(endpoint=OTEL_ENDPOINT, insecure=True)
_log_provider.add_log_record_processor(BatchLogRecordProcessor(_log_exporter))
_logs.set_logger_provider(_log_provider)

otel_log_handler = LoggingHandler(level=logging.INFO, logger_provider=_log_provider)

# ── LogBufferHandler — /logs 엔드포인트용 ────────────────────────
log_buffer = deque(maxlen=500)

class LogBufferHandler(logging.Handler):
    def emit(self, record):
        span     = trace.get_current_span()
        trace_id = None
        if span:
            ctx = span.get_span_context()
            if ctx.is_valid:
                trace_id = format(ctx.trace_id, '032x')
        log_buffer.append({
            "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
            "level":     record.levelname,
            "message":   record.getMessage(),
            "trace_id":  trace_id,
        })

# ── 로거 설정 ──────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("fisa-bank")

# ★ 핵심: propagate=False — root logger로 전파 차단
logger.propagate = False

logger.addHandler(logging.StreamHandler())  # 콘솔 출력
logger.addHandler(LogBufferHandler())       # /logs 엔드포인트용
logger.addHandler(otel_log_handler)         # SolarWinds 전송 (trace_id 자동 주입)
