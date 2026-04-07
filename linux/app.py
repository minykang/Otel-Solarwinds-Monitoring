"""
app.py — 우리FISA 은행 API 서버 (비즈니스 로직만)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OTel 설정은 telemetry.py에서 담당.
이 파일은 Flask 라우트와 은행 비즈니스 로직만 다룸.

엔드포인트:
  GET  /                      → 은행 메인 UI (templates/index.html)
  GET  /api/account-summary   → 잔액 조회 (핵심 관찰 대상)
  GET  /api/salary-mode       → 월급날 모드 상태 확인
  POST /api/salary-mode       → 월급날 모드 ON/OFF
  GET  /logs                  → 실시간 로그 (대시보드/브라우저 콘솔 확인용)
  GET  /metrics               → 시스템 메트릭 (CPU, Memory)
"""

import time
import random
import psutil
from flask import Flask, jsonify, render_template, request
from opentelemetry import trace as otel_trace
from opentelemetry.instrumentation.flask import FlaskInstrumentor

# OTel 설정은 telemetry.py에서 전부 담당 — 여기선 가져다 쓰기만 함
from telemetry import (
    tracer,
    request_counter,
    error_counter,
    response_time_histogram,
    active_requests,
    log_buffer,
    logger,
)

# ── Flask 앱 설정 ────────────────────────────────────────────────
app = Flask(__name__)

# FlaskInstrumentor: 모든 HTTP 요청에 자동으로 OTel span 생성
# → GET /api/account-summary 요청이 들어오면 자동으로 span 시작/종료
FlaskInstrumentor().instrument_app(app)


def get_trace_id() -> str:
    """현재 span의 trace_id를 문자열로 반환. span 없으면 'no-trace'"""
    span = otel_trace.get_current_span()
    if span:
        ctx = span.get_span_context()
        if ctx.is_valid:
            return format(ctx.trace_id, '032x')
    return "no-trace"


# ── 서버 상태 ─────────────────────────────────────────────────────
# 월급날 모드: ON이면 DB 조회가 2~5초로 느려짐 (월급날 DB 과부하 시뮬레이션)
salary_mode = {"active": False}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 라우트
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.route("/")
def index():
    """은행 메인 UI 서빙 — templates/index.html"""
    return render_template("index.html")


@app.route("/api/account-summary")
def account_summary():
    """
    잔액 조회 API — 핵심 관찰 대상

    k6 부하 테스트 시 이 엔드포인트에 1000명이 동시에 요청.
    평소:    50~150ms (db-query-normal span)
    월급날:  2~5초    (db-query-slow span) ← SolarWinds에서 빨간 trace로 보임

    관찰 포인트:
      Metrics: response_time_histogram → p95가 2초 넘으면 DB 지연 발생 중
      Traces:  db-query-slow span 길이 → 어디서 막히는지 정확히 보임
      Logs:    WARNING + trace_id → 왜 느려졌는지 설명
    """
    start = time.time()

    # 동시 처리 중인 요청 수 +1 (요청 시작)
    active_requests.add(1, {"endpoint": "/api/account-summary"})

    with tracer.start_as_current_span("account-summary") as span:
        # span 속성: SolarWinds APM에서 필터링/검색에 활용
        span.set_attribute("salary_mode.active", salary_mode["active"])
        span.set_attribute("user.name", "김민영")
        span.set_attribute("account.number", "123-456-78-90")

        # ── DB 조회 시뮬레이션 ───────────────────────────────
        # 월급날 모드 ON  → 항상 느림 (DB 과부하 시뮬레이션)
        # 월급날 모드 OFF → 20% 확률로 느림 (평소에도 가끔 발생)
        is_slow = salary_mode["active"]

        if is_slow:
            delay = random.uniform(2.0, 5.0)

            # span 속성으로 느린 이유 기록 → SolarWinds에서 바로 확인 가능
            span.set_attribute("db.slow_query", True)
            span.set_attribute("db.delay_seconds", round(delay, 2))
            span.set_attribute("db.slow_reason",
                "salary_batch_overload" if salary_mode["active"] else "occasional_lock")

            # 명시적 WARNING 로그 — LogBufferHandler가 현재 span의 trace_id를 자동 첨부
            # → /logs 에서 확인 가능, trace_id로 SolarWinds APM trace와 연결
            logger.warning(
                f"[trace_id={get_trace_id()}] DB 쿼리 지연 발생 — {delay:.1f}초 예상 "
                f"(원인: {'월급날 배치 과부하' if salary_mode['active'] else '간헐적 Lock'})"
            )

            # 별도 span으로 분리 → SolarWinds trace에서 병목 위치를 정확히 볼 수 있음
            with tracer.start_as_current_span("db-query-slow"):
                time.sleep(delay)

        else:
            with tracer.start_as_current_span("db-query-normal"):
                time.sleep(random.uniform(0.05, 0.15))

        # ── 응답 준비 ────────────────────────────────────────
        elapsed_ms = round((time.time() - start) * 1000, 1)
        balance    = random.randint(5000, 6000) * 1000

        span.set_attribute("response.time_ms", elapsed_ms)
        span.set_attribute("response.balance", balance)

        # INFO 로그 — 정상 완료 기록 (trace_id 자동 첨부)
        logger.info(f"[trace_id={get_trace_id()}] 잔액 조회 완료 — ₩{balance:,} ({elapsed_ms}ms)")

        # 메트릭 기록
        request_counter.add(1, {"endpoint": "/api/account-summary"})
        response_time_histogram.record(elapsed_ms, {
            "endpoint":   "/api/account-summary",
            "slow_query": str(is_slow),
        })

    # 동시 처리 중인 요청 수 -1 (요청 완료)
    active_requests.add(-1, {"endpoint": "/api/account-summary"})

    return jsonify({
        "user":        "김민영",
        "account":     "123-456-78-90",
        "balance":     f"{balance:,}",
        "balance_raw": balance,
        "response_ms": elapsed_ms,
        "slow":        is_slow,
    })


@app.route("/api/salary-mode", methods=["GET", "POST"])
def salary_mode_control():
    """
    월급날 모드 ON/OFF

    POST {"active": true}  → 월급날 모드 켜기 (이후 account-summary가 2~5초)
    POST {"active": false} → 평상시 모드 (이후 account-summary가 50~150ms)
    GET                    → 현재 상태 확인
    """
    if request.method == "POST":
        data = request.get_json() or {}
        salary_mode["active"] = data.get("active", not salary_mode["active"])

        state = "ON 🔥" if salary_mode["active"] else "OFF ✅"
        logger.warning(
            f"=== 월급날 모드 {state} === "
            f"({'account-summary 응답이 2~5초로 느려짐' if salary_mode['active'] else '정상 응답 복구'})"
        )

    return jsonify({
        "active":  salary_mode["active"],
        "message": "월급날 모드 활성화 중 — DB 과부하 시뮬레이션" if salary_mode["active"]
                   else "평상시 모드",
    })


@app.route("/logs")
def get_logs():
    """
    최근 로그 반환 (최대 100개)
    브라우저에서 직접 확인: http://서버IP:5000/logs
    각 로그에 trace_id 포함 → SolarWinds APM에서 해당 trace 검색 가능
    """
    return jsonify({"logs": list(log_buffer)[-100:]})


@app.route("/metrics")
def app_metrics():
    """시스템 메트릭 — 대시보드 또는 직접 확인용"""
    cpu    = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk   = psutil.disk_usage("/")
    return jsonify({
        "cpu_percent":    cpu,
        "memory_percent": memory.percent,
        "memory_used_mb": round(memory.used / 1024 / 1024, 1),
        "disk_percent":   round(disk.percent, 1),
        "salary_mode":    salary_mode["active"],
    })


# ── 서버 시작 ─────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info("  우리FISA 은행 API 서버 시작")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info("  은행 UI    : http://0.0.0.0:5000/")
    logger.info("  로그 확인  : http://0.0.0.0:5000/logs")
    logger.info("  메트릭     : http://0.0.0.0:5000/metrics")
    logger.info("  OTel 전송  : telemetry.py → OTel Collector → SolarWinds")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    app.run(host="0.0.0.0", port=5000, debug=False)
