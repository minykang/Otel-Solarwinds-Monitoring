<div align="center">

<img src="https://img.shields.io/badge/OpenTelemetry-000000?style=for-the-badge&logo=opentelemetry&logoColor=white"/>
<img src="https://img.shields.io/badge/SolarWinds-F5A623?style=for-the-badge&logo=solarwinds&logoColor=white"/>
<img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
<img src="https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white"/>
<img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white"/>
<img src="https://img.shields.io/badge/k6-7D64FF?style=for-the-badge&logo=k6&logoColor=white"/>

<br/><br/>

# 🔭 Modern Observability
### OpenTelemetry + SolarWinds로 구현하는 현대적 관측 가능성

<br/>

> **"시스템이 왜 느린가?"**
> 단순 모니터링 알람을 넘어, Traces · Metrics · Logs 세 가지 신호를 `trace_id` 하나로 연결하여
> 장애 원인을 수 분 내에 드릴다운하는 **풀스택 Observability 파이프라인** 구현 프로젝트

<br/>

</div>

---

## 📋 목차

| # | 섹션 |
|---|------|
| 1 | [💡 Monitoring vs Observability](#-monitoring-vs-observability) |
| 2 | [🧩 3 Pillars — Traces · Metrics · Logs](#-3-pillars--traces--metrics--logs) |
| 3 | [🏦 장애 시나리오 — OO은행 월급날](#-장애-시나리오--oo은행-월급날) |
| 4 | [🏗️ 아키텍처](#️-아키텍처) |
| 5 | [📁 프로젝트 구조](#-프로젝트-구조) |
| 6 | [🔑 핵심 구현](#-핵심-구현) |
| 7 | [🚀 실행 방법](#-실행-방법) |
| 8 | [📊 부하 테스트 결과](#-부하-테스트-결과) |
| 9 | [📈 SolarWinds 관찰 결과](#-solarwinds-관찰-결과) |
| 10 | [⚠️ 무료 플랜 한계](#️-solarwinds-무료-플랜-한계) |

---

## 💡 Monitoring vs Observability

```
Monitoring                          Observability
─────────────────────               ─────────────────────────────
"무엇이 잘못됐나?"                  "왜 잘못됐나?"
임계값 기반 알람 → 감지             데이터 연결 → 원인 추론
알려진 문제만 탐지                  Unknown-Unknowns도 분석 가능
```

<table>
<tr>
<th width="50%">🚨 Monitoring만 있을 때</th>
<th width="50%">🔭 Observability가 있을 때</th>
</tr>
<tr>
<td>

```
알람: AVG 응답시간 > 2,000ms 🔔
         ↓
담당자 긴급 호출 📞
         ↓
로그 파일 수동 grep... 🔍
         ↓
원인 파악까지 수십 분 ⏱️
```

</td>
<td>

```
알람: AVG 응답시간 > 2,000ms 🔔
         ↓
Metrics → 언제부터 튀었나? 📊
         ↓
Traces → 어느 Span이 느린가? 🕵️
         ↓
Logs → trace_id로 원인 확정 ✅
         ↓
수 분 내 근본 원인 파악 ⚡
```

</td>
</tr>
</table>

---

## 🧩 3 Pillars — Traces · Metrics · Logs

세 가지 신호가 `trace_id` 하나로 연결될 때 비로소 시스템의 내부 상태를 완전히 이해할 수 있습니다.

```mermaid
graph LR
    A["📊 Metrics<br/>응답시간이 튀었다!<br/>AVG 3,524ms"] -->|이상 감지| B["🔑 trace_id"]
    C["🕵️ Traces<br/>db-query-slow<br/>4.2초 병목 특정"] -->|원인 추적| B
    D["📄 Logs<br/>WARNING: DB 과부하<br/>원인 최종 확정"] -->|맥락 확인| B
    B --> E["✅ 장애 원인 파악 완료"]
```

| 신호 | 역할 | 예시 |
|------|------|------|
| 📊 **Metrics** | 수치형 지표 집계 — **감지** | AVG 3,524ms · ERR 0.5% · RPS 1.2k |
| 🕵️ **Traces** | 요청 1건의 전체 흐름 추적 — **추적** | `account-summary` → `db-query-slow` 4.2s |
| 📄 **Logs** | 특정 시점 텍스트 이벤트 — **확인** | `[trace_id=a3f2...] DB 과부하 경고` |

> **핵심:** Metrics로 **감지**하고, Traces로 **찾고**, Logs로 **확인**한다.

---

## 🏦 장애 시나리오 — OO은행 월급날

```
09:00  월급날 오전, 전 직원이 동시에 은행 앱을 열고 잔액을 조회
         ↓
       1,000명+ 동시 접속 · 무한 새로고침
         ↓
09:01  "서버 응답이 없습니다" 메시지 출력 · 앱 로딩 멈춤
         ↓
       월급날 배치 처리 → DB LOCK 발생
       → 잔액 조회 API 응답시간 2~5초로 급증
```

**실험 목표:** OpenTelemetry가 DB 병목 구간을 어떻게 정확히 포착하는지 검증

이번 실험에서는 `salary_mode` 플래그로 DB LOCK 상황을 재현합니다.

```bash
# 월급날 모드 ON — 이후 모든 요청이 2~5초 지연
curl -X POST http://localhost:5000/api/salary-mode \
  -H "Content-Type: application/json" \
  -d '{"active": true}'
```

---

## 🏗️ 아키텍처

![Architecture](./images/architecture.jpg)

```mermaid
flowchart LR
    subgraph LOCAL["💻 Local PC"]
        K6["k6 Load Test\n1,000 VU (Linux)\n2,000 VU (Windows)"]
    end

    subgraph LINUX["🐧 Linux VM — Docker"]
        LA["Flask API\n:5000"]
        LO["OTel SDK\nTracer · Meter · Logger"]
        LC["OTel Collector\n:4317"]
        LA --> LO --> LC
    end

    subgraph WINDOWS["🪟 Windows VM — Native"]
        WA["Flask API\n:5000"]
        WO["OTel SDK\nTracer · Meter · Logger"]
        WC["OTel Collector\n:4317"]
        WA --> WO --> WC
    end

    subgraph SW["☁️ SolarWinds Cloud APM"]
        T["Traces"]
        M["Metrics"]
        L["Logs"]
        AL["Alerts"]
    end

    K6 -->|HTTP GET| LA
    K6 -->|HTTP GET| WA
    LC -->|OTLP/gRPC TLS| SW
    WC -->|OTLP/gRPC TLS| SW
```

**OTel Collector 파이프라인**

```
Receiver (OTLP gRPC :4317)   →   Processor (Batch)   →   Exporter (SolarWinds :443)
     ↑                                                          ↓
Flask app sends                                        Traces · Metrics · Logs
Traces / Metrics / Logs                                모두 동일 경로로 전송
```

---

## 📁 프로젝트 구조

```
Otel-Solarwinds-Monitoring/
│
├── linux/                        🐧 Linux VM — Docker 컨테이너 실행
│   ├── app.py                    Flask 은행 API + 비즈니스 로직
│   ├── telemetry.py              OTel SDK 초기화 전담 (3 Provider)
│   ├── otel-config.yaml          Collector 파이프라인 설정
│   ├── load_test.js              k6 시나리오 (1,000 VU · 3단계)
│   ├── docker-compose.yml        bank-app + otel-collector
│   ├── Dockerfile
│   ├── requirements.txt
│   └── templates/index.html      은행 메인 UI
│
└── window/                       🪟 Windows VM — 네이티브 Python 실행
    ├── app.py                    Flask 은행 API (disk_usage 경로 분리)
    ├── telemetry.py
    ├── otel-config.yaml
    ├── load_test_win.js          k6 시나리오 (2,000 VU)
    ├── docker-compose.yml
    ├── requirements.txt
    └── templates/index.html
```

---

## 🔑 핵심 구현

### 1️⃣ `app.py` — Span 계층으로 병목 위치 특정

```python
@app.route("/api/account-summary")
def account_summary():
    with tracer.start_as_current_span("account-summary") as span:
        span.set_attribute("salary_mode.active", salary_mode["active"])

        if salary_mode["active"]:                        # 월급날 모드 ON
            delay = random.uniform(2.0, 5.0)
            span.set_attribute("db.slow_reason", "salary_batch_overload")

            logger.warning(                              # trace_id를 텍스트에 직접 삽입
                f"[trace_id={get_trace_id()}] DB 쿼리 지연 — {delay:.1f}초 예상"
            )

            with tracer.start_as_current_span("db-query-slow"):
                time.sleep(delay)                        # ← SolarWinds에서 빨간 Span

        else:                                            # 평상시
            with tracer.start_as_current_span("db-query-normal"):
                time.sleep(random.uniform(0.05, 0.15))  # 50~150ms
```

SolarWinds **Span Waterfall** 에서 이렇게 보입니다:

```
account-summary    ████████████████████████████  3,247ms
  └─ db-query-slow ████████████████████████████  3,205ms  ← 여기!
```

---

### 2️⃣ `telemetry.py` — 3 Provider 한 파일에 초기화

```python
# ── TracerProvider ──────────────────────────────
tracer_provider = TracerProvider(resource=resource)
tracer_provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint=OTEL_ENDPOINT))
)
trace.set_tracer_provider(tracer_provider)

# ── MeterProvider (5초마다 전송) ────────────────
meter_provider = MeterProvider(
    resource=resource,
    metric_readers=[PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=OTEL_ENDPOINT),
        export_interval_millis=5000
    )]
)
metrics.set_meter_provider(meter_provider)

# ── LoggerProvider ──────────────────────────────
log_provider = LoggerProvider(resource=resource)
log_provider.add_log_record_processor(
    BatchLogRecordProcessor(OTLPLogExporter(endpoint=OTEL_ENDPOINT))
)

logger.propagate = False   # ★ OTel context 손실 방지 핵심 설정
logger.addHandler(otel_log_handler)    # SolarWinds 전송
logger.addHandler(LogBufferHandler())  # /logs 엔드포인트
```

> `propagate=False` 없이는 로그가 root logger로 중복 전파되어 `trace_id`가 손실됩니다.

---

### 3️⃣ `get_trace_id()` — SolarWinds 무료 플랜 Log 연결 핵심

SolarWinds **무료 플랜**은 Trace ↔ Log 자동 연결을 제공하지 않습니다.
`trace_id`를 로그 **텍스트에 직접 삽입**하여 수동 검색으로 연결합니다.

```python
def get_trace_id() -> str:
    """현재 활성 Span의 trace_id를 32자리 hex 문자열로 반환"""
    span = otel_trace.get_current_span()
    if span:
        ctx = span.get_span_context()
        if ctx.is_valid:
            return format(ctx.trace_id, '032x')  # 예: a3f2c1d8e9f04b12...
    return "no-trace"

# 로그 메시지에 trace_id 직접 포함
logger.warning(f"[trace_id={get_trace_id()}] DB 쿼리 지연 — {delay:.1f}초")
logger.info(f"[trace_id={get_trace_id()}] 잔액 조회 완료 — ₩{balance:,} ({elapsed_ms}ms)")
```

SolarWinds Logs 탭에서 `trace_id=a3f2...` 로 검색하면 해당 요청의 로그만 필터링됩니다.

---

### 4️⃣ `otel-config.yaml` — Collector 파이프라인

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317       # Flask app → Collector
  hostmetrics:                        # 호스트 CPU/메모리/디스크 자동 수집
    collection_interval: 10s
    scrapers: [cpu, memory, disk, network]

processors:
  batch:                              # 효율적인 묶음 전송

exporters:
  otlp:
    endpoint: "otel.collector.ap-01.cloud.solarwinds.com:443"
    tls:
      insecure: false
    headers:
      authorization: "Bearer YOUR_SOLARWINDS_API_TOKEN"  # ← 교체 필요

service:
  pipelines:
    traces:   { receivers: [otlp],              processors: [batch], exporters: [otlp] }
    metrics:  { receivers: [otlp, hostmetrics], processors: [batch], exporters: [otlp] }
    logs:     { receivers: [otlp],              processors: [batch], exporters: [otlp] }
```

---

## 🚀 실행 방법

### 🐧 Linux VM — Docker Compose

```bash
# 1. 클론
git clone https://github.com/minykang/Otel-Solarwinds-Monitoring.git
cd Otel-Solarwinds-Monitoring/linux

# 2. API 토큰 설정
vi otel-config.yaml
# authorization: "Bearer YOUR_TOKEN" 부분 수정

# 3. 실행
docker compose up -d

# ✅ 동작 확인
curl http://localhost:5000/api/account-summary   # 잔액 조회 API
curl http://localhost:5000/logs                  # trace_id 포함 로그
curl http://localhost:5000/metrics               # CPU · 메모리

# 🔥 월급날 모드 ON
curl -X POST http://localhost:5000/api/salary-mode \
  -H "Content-Type: application/json" -d '{"active": true}'

# ✅ 월급날 모드 OFF
curl -X POST http://localhost:5000/api/salary-mode \
  -H "Content-Type: application/json" -d '{"active": false}'
```

**API 응답 예시:**
```json
{
  "user": "김민영",
  "account": "123-456-78-90",
  "balance": "5,340,000",
  "response_ms": 3247.5,
  "slow": true
}
```

### 🪟 Windows VM — 네이티브 Python

```powershell
cd Otel-Solarwinds-Monitoring\window

# 의존성 설치
pip install -r requirements.txt

# OTel Collector 실행 (별도 터미널)
.\otelcol-contrib.exe --config otel-config.yaml

# Flask 앱 실행
python app.py
```

**`requirements.txt`**
```
flask
psutil
opentelemetry-api
opentelemetry-sdk
opentelemetry-instrumentation-flask
opentelemetry-exporter-otlp-proto-grpc
```

---

## 📊 부하 테스트 결과

### 시나리오 — 3단계 트래픽

```
0 ─────────────────────────── 시간 (초) ──────────────────────────→ 120s
│
1000 VU           ┌──────────────────────┐
                  │  월급날 폭증 구간    │
100 VU  ──────────┘                      └──────────── 0 VU
│       (30s)           (60s)                 (30s)
└───────────────────────────────────────────────────────
  점진 증가        최대 부하             트래픽 진정
```

### k6 터미널 출력 (salary_mode ON)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  우리FISA 은행 월급날 부하 테스트 결과
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  총 요청 수    : 10,897
  평균 응답시간 : 3,524ms
  p95 응답시간  : 4,865ms
  p99 응답시간  : 5,102ms
  최대 응답시간 : 5,487ms
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  → SolarWinds에서 Duration Heatmap 확인!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 환경별 비교

| 환경 | 실행 방식 | VU | 총 요청 | 평균 응답 | p95 |
|------|----------|-----|---------|-----------|-----|
| 🐧 Linux VM | Docker | 1,000 | 10,897건 | 3,524 ms | **4,865 ms** |
| 🪟 Windows VM | Native Python | 2,000 | — | ~3,500 ms | ~4,800 ms |
| 평상시 (OFF) | — | — | — | **50~150 ms** | < 200 ms |

> salary_mode ON 시 응답시간 **약 70배 증가** (50ms → 3,524ms)

---

## 📈 SolarWinds 관찰 결과

### 🌡️ Duration Heatmap — salary_mode 전/후

```
응답시간
  ↑
5s │                        ░░▒▒▓▓██████▓▓▒▒░   ← salary_mode ON
4s │                        ░░▒▒▓▓██████▓▓▒▒░
3s │                     ░░░░▒▒▓▓▓███████▓▒▒
2s │               ░░░░░░░░░░░░░░░▒▒▒▒▒▒▒▒░
1s │
0s │ ░░░░░░░░░░░░░░           ░░░░░░░░░░        ← salary_mode OFF
   └──────────────────────────────────────────→ 시간
               ▲ salary_mode ON
```

점들이 **아래(빠름) → 위(느림)** 로 폭발적으로 퍼지는 순간이 장애 시작 시점입니다.

---

### 🕵️ Span Waterfall — 병목 구간 특정

```
[GET /api/account-summary]   ████████████████████████████████  3,247ms
  ├─ account-summary         ████████████████████████████████  3,243ms
  │    ├─ db-query-slow      ███████████████████████████████   3,205ms  ⬅️ 병목!
  │    │    span.attribute:
  │    │      db.slow_reason = "salary_batch_overload"
  │    │      db.delay_seconds = 3.21
  │    └─ (response prep)    █  38ms
  └─ (Flask overhead)        █  4ms
```

---

### 📊 Metrics 그래프 — AVG 응답시간 급증

```
응답시간(ms)
  ↑
4000│               ╭────────────────────────╮
3000│           ╭───╯                        ╰───╮
2000│       ╭───╯                                ╰──╮
1000│   ╭───╯                                      ╰──────╮
 200│───╯                                                  ╰────────
   └────────────────────────────────────────────────────────────→ 시간
              ↑ salary_mode ON                ↑ salary_mode OFF
         알람 발생 (AVG > 2,000ms)
```

---

### 📄 Logs — trace_id로 검색

SolarWinds Logs 탭에서 `trace_id=a3f2c1d8...` 로 검색:

```log
14:23:44  WARNING  [trace_id=a3f2c1d8e9f04b12...] DB 쿼리 지연 — 3.2초 예상 (원인: 월급날 배치 과부하)
14:23:47  INFO     [trace_id=a3f2c1d8e9f04b12...] 잔액 조회 완료 — ₩5,340,000 (3247ms)
```

`/logs` 엔드포인트로 직접 확인도 가능합니다:

```bash
curl http://localhost:5000/logs | python -m json.tool

# 응답 예시
{
  "logs": [
    {
      "timestamp": "14:23:44.821",
      "level": "WARNING",
      "message": "[trace_id=a3f2c1d8...] DB 쿼리 지연 — 3.2초 예상",
      "trace_id": "a3f2c1d8e9f04b12..."
    }
  ]
}
```

---

### 🔔 Alert 설정

| 항목 | 설정값 |
|------|--------|
| 조건 | `http_response_time_ms` 평균 > **2,000ms** |
| Duration Condition | **3~5분** (잦은 알람 방지) |
| 알람 채널 | Email |

> Duration Condition을 0분으로 설정하면 느린 요청 1건마다 알람이 발생합니다.
> 3~5분으로 설정하여 실제 장애 상황에서만 알람이 오도록 조정하세요.

---

## 드릴다운 분석 흐름

```mermaid
flowchart TD
    A["🔔 Alert 수신\nAVG 응답시간 > 2,000ms\n이메일 도착"] --> B

    B["📊 Metrics 확인\nAVG 3,524ms\nDB 지연 신호 감지"] --> C

    C["🕵️ Traces — Duration Heatmap\nsalary_mode ON 시점 특정\n점들이 위로 폭발"] --> D

    D["🔍 Span Waterfall\ndb-query-slow span 4.2초\n병목 위치 정확히 특정"] --> E

    E["📄 Logs 검색\ntrace_id=a3f2... 로 필터링\nWARNING: 월급날 배치 과부하"] --> F

    F["✅ 근본 원인 확정\nsalary_mode OFF\n또는 DB 배치 스케줄 조정"]

    style A fill:#ff6b6b,color:#fff
    style F fill:#51cf66,color:#fff
```

### 기존 방식 vs Modern Observability

```
기존 방식                              Modern Observability
────────────────────                  ──────────────────────────
로그 파일 수동 grep                    trace_id 하나로 3개 신호 연결
담당 개발자 긴급 호출                  맥락(Context) 기반 즉시 추적
원인 파악까지 수십 분                  수 분 내 근본 원인 확정
```

---

## ⚠️ SolarWinds 무료 플랜 한계

| 기능 | 무료 | 유료 |
|------|:----:|:----:|
| Duration Heatmap | ✅ | ✅ |
| Span Waterfall | ✅ | ✅ |
| Alert (Email) | ✅ | ✅ |
| Trace ↔ Log 자동 연결 | ❌ | ✅ |
| TRANSACTIONS 탭 | ❌ | ✅ |
| p95/p99 Metrics 드롭다운 | ❌ | ✅ |

> **무료 플랜 우회 전략:** `trace_id`를 로그 텍스트에 직접 삽입 → 수동 검색으로 연결

---

## 🔗 참고 문서

- [OpenTelemetry Python SDK 공식 문서](https://opentelemetry-python.readthedocs.io/)
- [OpenTelemetry Collector Contrib](https://github.com/open-telemetry/opentelemetry-collector-contrib)
- [SolarWinds APM](https://www.solarwinds.com/solarwinds-observability)
- [k6 공식 문서](https://k6.io/docs/)

---

<div align="center">

**강민영** · 우리FISA 클라우드 엔지니어링 과정
2차 기술세미나 — Modern Observability · 2026.04

</div>
