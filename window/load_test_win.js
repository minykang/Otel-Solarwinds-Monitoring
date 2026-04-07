import http from 'k6/http';
import { sleep, check } from 'k6';
import { Counter, Trend } from 'k6/metrics';

// ── 커스텀 메트릭 설정 ─────────────────────────
const slowRequests = new Counter('slow_requests_win'); 
const responseTrend = new Trend('win_response_time_ms', true);

// ── 대상 서버 주소 ────────────────────────────
// 민영 님의 윈도우 VM IP로 고정했습니다.
const BASE_URL = __ENV.TARGET_URL || 'http://172.21.31.4:5000';

// ── 부하 시나리오 (월급날 폭증) ────────────────────
export const options = {
  stages: [
    { duration: '30s', target: 500  },  // 0 -> 100명 점진적 증가
    { duration: '60s', target: 2000 },  // 100 -> 1000명 급증 (피크타임)
    { duration: '30s', target: 0    },  // 트래픽 감소
  ],
  thresholds: {
    http_req_duration: ['p(95)<8000'],  // p95 응답시간 8초 이내
    http_req_failed:   ['rate<0.1'],    // 에러율 10% 미만
  },
};

export default function () {
  // [수정 사항] 엔드포인트를 /api/balance에서 /api/account-summary로 변경
  // 파이썬 앱(app.py)에 정의된 정확한 경로를 호출해야 404 에러가 나지 않습니다.
  const res = http.get(`${BASE_URL}/api/account-summary`, {
    tags: { endpoint: 'win-account-summary' },
  });

  // 응답 검증 (200 OK가 나와야 성공)
  check(res, {
    '200 OK': (r) => r.status === 200,
    '응답 데이터 확인': (r) => r.body.length > 0,
  });

  // 1초 이상 걸리는 요청은 '느린 요청'으로 기록
  if (res.timings.duration > 1000) {
    slowRequests.add(1);
  }
  responseTrend.add(res.timings.duration);

  // 실제 사용자처럼 0.5~1.5초 간격으로 행동 시뮬레이션
  sleep(Math.random() * 1.0 + 0.5);
}

// ── 테스트 종료 후 요약 출력 ──────────────────────
export function handleSummary(data) {
  const dur = data.metrics.http_req_duration;
  const reqs = data.metrics.http_reqs;

  console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('  우리FISA 은행 [Windows] 부하 테스트 결과');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log(`  수행자        : 김민영 님`); 
  console.log(`  총 요청 수    : ${reqs.values.count}`);
  console.log(`  평균 응답시간 : ${dur.values.avg.toFixed(0)}ms`);
  console.log(`  p(95) 응답시간 : ${dur.values['p(95)'].toFixed(0)}ms`);
  console.log(`  최대 응답시간 : ${dur.values.max.toFixed(0)}ms`);
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('  → SolarWinds APM에서 실시간 Trace 확인 중...');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

  return { stdout: '' };
}