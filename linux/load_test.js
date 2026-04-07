/**
 * k6 부하 테스트 — 우리FISA 은행 월급날 시나리오
 * ─────────────────────────────────────────────────
 * 실행 방법 (PowerShell):
 *   k6 run load_test.js
 *
 * 서버 IP 변경 시:
 *   $env:TARGET_URL="http://172.21.31.39:5000"; k6 run load_test.js
 *
 * 관찰 포인트:
 *   SolarWinds APM Traces   → 느린 요청 (db-query-slow) 빨간색으로 보임
 *   SolarWinds Metrics      → http_requests_total, http_response_time_ms 급증
 *   http://서버IP:5000/logs  → WARNING 로그 + trace_id 확인
 */

import http from 'k6/http';
import { sleep, check } from 'k6';
import { Counter, Trend } from 'k6/metrics';

// ── 커스텀 메트릭 (k6 리포트에 표시) ─────────────────────────
const slowRequests = new Counter('slow_requests');   // 1초 이상 응답
const responseTrend = new Trend('response_time_ms', true);

// ── 대상 서버 주소 ────────────────────────────────────────────
const BASE_URL = __ENV.TARGET_URL || 'http://172.21.31.39:5000';

// ── 부하 시나리오 설정 ────────────────────────────────────────
// 총 3단계:
//   1단계 (30초): 0 → 100명 점진적 증가  (일반 트래픽)
//   2단계 (60초): 100 → 1000명 급증      (월급날 폭증 시뮬레이션)
//   3단계 (30초): 1000 → 0명 감소        (트래픽 진정)
export const options = {
  stages: [
    { duration: '30s', target: 100  },  // 점진적 증가
    { duration: '60s', target: 1000 },  // 월급날 폭증
    { duration: '30s', target: 0    },  // 감소
  ],

  // 성능 기준 (이 기준을 넘으면 k6가 실패로 표시)
  thresholds: {
    http_req_duration: ['p(95)<6000'],  // p95 응답시간 6초 이내 (DB 지연 감안)
    http_req_failed:   ['rate<0.1'],    // 에러율 10% 미만
  },
};

// ── 실제 사용자 행동 시뮬레이션 ──────────────────────────────
export default function () {
  // 월급날에 사용자가 하는 행동: 잔액 새로고침
  const res = http.get(`${BASE_URL}/api/account-summary`, {
    tags: { endpoint: 'account-summary' },
  });

  // 응답 검증
  check(res, {
    '200 OK':         r => r.status === 200,
    '응답 있음':       r => r.body.length > 0,
  });

  // 느린 응답 카운트 (1000ms 이상)
  if (res.timings.duration > 1000) {
    slowRequests.add(1);
  }
  responseTrend.add(res.timings.duration);

  // 실제 사용자처럼 잠깐 대기 (0.5~2초)
  // 이걸 제거하면 더 공격적인 테스트 가능
  sleep(Math.random() * 1.5 + 0.5);
}

/**
 * 테스트 완료 후 요약 출력
 * k6가 자동으로 출력하는 summary에 추가 정보 표시
 */
export function handleSummary(data) {
  const dur = data.metrics.http_req_duration;
  const reqs = data.metrics.http_reqs;

  console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('  우리FISA 은행 월급날 부하 테스트 결과');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log(`  총 요청 수    : ${reqs.values.count}`);
  console.log(`  평균 응답시간 : ${dur.values.avg.toFixed(0)}ms`);
  console.log(`  p95 응답시간  : ${dur.values['p(95)'].toFixed(0)}ms`);
  console.log(`  p99 응답시간  : ${dur.values['p(99)'].toFixed(0)}ms`);
  console.log(`  최대 응답시간 : ${dur.values.max.toFixed(0)}ms`);
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('  → SolarWinds에서 Duration Heatmap 확인!');
  console.log('  → http://서버IP:5000/logs 에서 trace_id 확인!');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

  return { stdout: '' };
}
