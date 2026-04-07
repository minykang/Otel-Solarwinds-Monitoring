# 🔭 Modern Observability with OpenTelemetry & SolarWinds

> **Flask 기반 은행 API에 OpenTelemetry 3 Pillars(Traces · Metrics · Logs)를 직접 계측하고, OTel Collector를 통해 SolarWinds로 전송하는 풀스택 Observability 데모 프로젝트**

<br/>

## 📌 프로젝트 개요

월급날 은행 서버에 DB 과부하가 발생하는 시나리오를 재현하여, 단순 모니터링(알람)으로는 알 수 없는 **"왜 느린가?"** 를 Observability 3 Pillars로 드릴다운하는 과정을 실습합니다.

| 구분 | 내용 |
|------|------|
| **시나리오** | 월급날 오전, 배치 처리 DB LOCK → 잔액 조회 API 응답 2~5초 |
| **계측 대상** | `/api/account-summary` — Traces + Metrics + Logs 동시 관찰 |
| **부하 도구** | k6 (Linux: 1,000 VU / Windows: 2,000 VU) |
| **관측 플랫폼** | SolarWinds Cloud APM (무료 플랜) |
| **핵심 연결고리** | `trace_id` — Trace ↔ Log 수동 연결 (무료 플랜 방식) |

<br/>

## 🏗️ 아키텍처

![Architecture Diagram](./images/architecture.jpg)

```
[Local PC]          [Linux VM]               [Windows VM]
  k6 (1000VU)  →   Flask App :5000           Flask App :5000
                   OTel SDK                  OTel SDK
                   OTel Collector :4317  →   OTel Collector :4317
                         ↓                          ↓
                   ┌─────────────────────────────────────┐
                   │   SolarWinds Cloud APM              │
                   │   Traces · Metrics · Logs           │
                   └─────────────────────────────────────┘
```

**OTel Collector 파이프라인**

```
Receiver (OTLP gRPC :4317)
    ↓
Processor (Batch)
    ↓
Exporter (OTLP → otel.collector.ap-01.cloud.solarwinds.com:443)
```

<br/>

## 🛠️ 기술 스택

| Category | Stack |
|----------|-------|
| **API Server** | Python 3.11 · Flask |
| **Observability SDK** | OpenTelemetry Python SDK |
| **Collector** | OpenTelemetry Collector Contrib |
| **Observability Platform** | SolarWinds Cloud APM |
| **Load Test** | k6 |
| **Container (Linux)** | Docker · Docker Compose |
| **System Info** | psutil |

<br/>

## 📁 프로젝트 구조

```
Otel-Solarwinds-Monitoring/
├── linux/                          # Linux VM (Docker 실행)
│   ├── app.py                      # Flask 은행 API (비즈니스 로직)
│   ├── telemetry.py                # OTel SDK 초기화 전담 모듈
│   ├── otel-config.yaml            # OTel Collector 파이프라인 설정
│   ├── load_test.js                # k6 부하 테스트 (1,000 VU)
│   ├── docker-compose.yml          # bank-app + otel-collector 구성
│   ├── Dockerfile
│   ├── requirements.txt
│   └── templates/
│       └── index.html              # 은행 메인 UI
│
└── window/                         # Windows VM (네이티브 실행)
    ├── app.py                      # Flask 은행 API (Windows 경로)
    ├── telemetry.py
    ├── otel-config.yaml
    ├── load_test_win.js            # k6 부하 테스트 (2,000 VU)
    ├── docker-compose.yml
    ├── requirements.txt
    └── templates/
        └── index.html
```

<br/>

## 🔑 핵심 구현: 3 Pillars + trace_id 연결

### 1️⃣ Traces — Span으로 병목 위치 정확히 특정

```python
# app.py
with tracer.start_as_current_span("account-summary") as span:
    span.set_attribute("salary_mode.active", salary_mode["active"])
    span.set_attribute("db.delay_seconds", round(delay, 2))

    if is_slow:
        with tracer.start_as_current_span("db-query-slow"):
            time.sleep(delay)           # 2~5초 지연 (DB LOCK 시뮬레이션)
    else:
        with tracer.start_as_current_span("db-query-normal"):
            time.sleep(random.uniform(0.05, 0.15))
```

SolarWinds **Duration Heatmap**에서 salary_mode ON 전/후 응답시간 분포가 즉각 시각화됩니다.

---

### 2️⃣ Metrics — 응답시간 히스토그램

```python
# telemetry.py
response_time_histogram = meter.create_histogram(
    name="http_response_time_ms",
    unit="ms",
    description="HTTP 응답시간 분포 (p50/p95/p99)",
)

# app.py — 요청마다 기록
response_time_histogram.record(elapsed_ms, {
    "endpoint":   "/api/account-summary",
    "slow_query": str(is_slow),
})
```

---

### 3️⃣ Logs — trace_id를 텍스트에 직접 심기

> **SolarWinds 무료 플랜**은 Trace ↔ Log 자동 연결을 지원하지 않습니다.
> 로그 메시지 **텍스트 안에 trace_id를 직접 삽입**하여 수동 검색으로 연결합니다.

```python
# app.py
def get_trace_id() -> str:
    """현재 활성 span의 trace_id를 32자리 hex 문자열로 반환"""
    span = otel_trace.get_current_span()
    if span:
        ctx = span.get_span_context()
        if ctx.is_valid:
            return format(ctx.trace_id, '032x')
    return "no-trace"

# 로그 메시지에 trace_id 직접 포함
logger.warning(
    f"[trace_id={get_trace_id()}] DB 쿼리 지연 발생 — {delay:.1f}초 예상 "
    f"(원인: 월급날 배치 과부하)"
)
logger.info(
    f"[trace_id={get_trace_id()}] 잔액 조회 완료 — ₩{balance:,} ({elapsed_ms}ms)"
)
```

**SolarWinds Logs 탭에서 `trace_id=a3f2...` 로 검색** → 해당 요청의 모든 로그 확인 가능

---

### 🔗 telemetry.py — 3 Provider 한 파일 초기화

```python
# telemetry.py

# TracerProvider — Span 생성·전송
_trace_provider = TracerProvider(resource=resource)
_trace_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(...)))
trace.set_tracer_provider(_trace_provider)

# MeterProvider — Metrics 집계·전송 (5초마다)
_meter_provider = MeterProvider(resource=resource, metric_readers=[...])
metrics.set_meter_provider(_meter_provider)

# LoggerProvider — OTel 표준 로그 전송
_log_provider = LoggerProvider(resource=resource)
_log_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter(...)))

# ★ 핵심: propagate=False — OTel context 손실 방지
logger.propagate = False
logger.addHandler(otel_log_handler)   # SolarWinds 전송
logger.addHandler(LogBufferHandler()) # /logs 엔드포인트용
```

> `propagate=False`가 없으면 로그가 root logger로 중복 전파되어 OTel trace_id가 손실됩니다.

---

### ⚙️ otel-config.yaml — Collector 파이프라인

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
  hostmetrics:                          # 호스트 CPU/메모리/디스크 자동 수집
    collection_interval: 10s
    scrapers: [cpu, memory, disk, network]

processors:
  batch:

exporters:
  otlp:
    endpoint: "otel.collector.ap-01.cloud.solarwinds.com:443"
    headers:
      authorization: "Bearer YOUR_SOLARWINDS_API_TOKEN"   # ← 본인 토큰으로 교체

service:
  pipelines:
    traces:   { receivers: [otlp],              processors: [batch], exporters: [otlp] }
    metrics:  { receivers: [otlp, hostmetrics], processors: [batch], exporters: [otlp] }
    logs:     { receivers: [otlp],              processors: [batch], exporters: [otlp] }
```

<br/>

## 🚀 실행 방법

### Linux VM — Docker Compose

```bash
# 1. 레포 클론
git clone https://github.com/minykang/Otel-Solarwinds-Monitoring.git
cd Otel-Solarwinds-Monitoring/linux

# 2. SolarWinds API 토큰 입력
vi otel-config.yaml   # authorization: "Bearer YOUR_TOKEN" 부분 수정

# 3. 실행
docker compose up -d

# 4. 동작 확인
curl http://localhost:5000/api/account-summary   # 잔액 조회
curl http://localhost:5000/logs                  # trace_id 포함 로그
curl http://localhost:5000/metrics               # CPU/메모리

# 5. 월급날 모드 ON (DB LOCK 시뮬레이션)
curl -X POST http://localhost:5000/api/salary-mode \
  -H "Content-Type: application/json" \
  -d '{"active": true}'
```

### Windows VM — 네이티브 Python

```powershell
cd Otel-Solarwinds-Monitoring\window

# 의존성 설치
pip install -r requirements.txt

# OTel Collector 별도 실행 (contrib 바이너리 필요)
# otelcol-contrib.exe --config otel-config.yaml

# Flask 앱 실행
python app.py
```

<br/>

## 📊 부하 테스트 (k6)

### 시나리오

```
0 → 100명 (30초)     : 일반 트래픽
100 → 1,000명 (60초) : 월급날 폭증 시뮬레이션
1,000 → 0명 (30초)   : 트래픽 진정
```

### 실행

```bash
# Linux 대상
k6 run linux/load_test.js

# Windows 대상 (서버 IP 지정)
$env:TARGET_URL="http://172.21.31.4:5000"
k6 run window/load_test_win.js
```

### 결과 (salary_mode ON)

| 환경 | VU | 총 요청 | 평균 응답 | p95 |
|------|----|---------|-----------|-----|
| Linux VM | 1,000 | 10,897건 | 3,524 ms | 4,865 ms |
| Windows VM | 2,000 | - | ~3,500 ms | ~4,800 ms |

> **평상시 (salary_mode OFF)**: 평균 50~150ms → salary_mode ON 시 **약 70배** 증가

<br/>

## 📈 SolarWinds 관찰 결과

### Duration Heatmap — salary_mode ON/OFF 전/후 비교

> `Traces` 탭 → `Duration Heatmap` 선택
> salary_mode ON 시점부터 점들이 위쪽(느린 응답)으로 폭발적으로 퍼짐

### Span Waterfall — 병목 위치 특정

```
account-summary  [████████████████████████ 3,247ms]
  └─ db-query-slow  [████████████████████ 3,205ms]  ← 여기서 막힘!
```

### Logs — trace_id로 로그 연결

SolarWinds Logs 탭에서 `trace_id=<32자리hex>` 로 검색:

```
[trace_id=a3f2c1d8...] DB 쿼리 지연 발생 — 3.2초 예상 (원인: 월급날 배치 과부하)
[trace_id=a3f2c1d8...] 잔액 조회 완료 — ₩5,340,000 (3247ms)
```

### Alert — 응답시간 임계값 초과 알람

| 설정 | 값 |
|------|-----|
| 조건 | `http_response_time_ms` 평균 > 2,000ms |
| Duration Condition | 3~5분 (잦은 알람 방지) |
| 채널 | Email |

<br/>

## 💡 주요 학습 포인트

### Monitoring vs Observability

| | Monitoring | Observability |
|---|---|---|
| 질문 | **무엇이** 잘못됐나 | **왜** 잘못됐나 |
| 방식 | 임계값 기반 알람 | 데이터 탐색 · 드릴다운 |
| 한계 | 알려진 문제만 감지 | 미지의 문제도 분석 |

### trace_id가 핵심인 이유

```
Metrics 알람 수신
    ↓
Traces에서 "db-query-slow span이 3초" 확인
    ↓
trace_id로 Logs 검색
    ↓
"월급날 배치 과부하" 원인 특정 → 문제 해결
```

세 신호를 `trace_id` 하나로 연결하면, **알람 수신 → 원인 파악**까지 한 흐름으로 처리됩니다.

<br/>

## ⚠️ SolarWinds 무료 플랜 한계

| 기능 | 무료 플랜 | 유료 플랜 |
|------|----------|----------|
| Trace ↔ Log 자동 연결 | ❌ (수동 검색) | ✅ |
| TRANSACTIONS 탭 | ❌ | ✅ |
| p95/p99 Metrics 드롭다운 | ❌ (k6로 확인) | ✅ |
| Duration Heatmap | ✅ | ✅ |
| Alert | ✅ | ✅ |

<br/>

## 🔗 관련 기술 문서

- [OpenTelemetry Python SDK](https://opentelemetry-python.readthedocs.io/)
- [OpenTelemetry Collector Contrib](https://github.com/open-telemetry/opentelemetry-collector-contrib)
- [SolarWinds APM](https://www.solarwinds.com/solarwinds-observability)
- [k6 Documentation](https://k6.io/docs/)

<br/>

---

<div align="center">

**강민영** · 우리FISA 클라우드 엔지니어링 과정
2차 기술세미나 — Modern Observability (2026.04)

</div>
