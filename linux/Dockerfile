# ── 우리FISA 은행 앱 Docker 이미지 ──────────────────────────────
# OTel SDK를 앱 코드(telemetry.py)에 직접 내장하는 방식.
# → opentelemetry-instrument 자동계측 에이전트 불필요.
# → CMD는 그냥 "python app.py"로 실행.

FROM python:3.11-slim

WORKDIR /app

# 패키지 먼저 설치 (레이어 캐싱 활용 — 코드만 바뀌면 pip install 재실행 안 함)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 전체 복사
# app.py, telemetry.py, templates/ 모두 포함
COPY . .

EXPOSE 5000

# OTel 설정은 telemetry.py가 담당하므로 그냥 python으로 실행
CMD ["python", "app.py"]
