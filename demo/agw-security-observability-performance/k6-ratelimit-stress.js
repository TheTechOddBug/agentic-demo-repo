import http from 'k6/http';
import { check } from 'k6';
import { Counter } from 'k6/metrics';

const rateLimited = new Counter('rate_limited_requests');
const successful = new Counter('successful_requests');

// Configuration — set GATEWAY_ADDRESS env var before running
const GATEWAY_ADDRESS = __ENV.GATEWAY_ADDRESS || 'localhost:8080';

export const options = {
  // High VU count, short duration to trigger rate limits
  vus: 50,
  duration: '30s',
  thresholds: {
    rate_limited_requests: ['count>0'],  // Expect some 429s
  },
};

export default function () {
  const payload = JSON.stringify({
    model: 'claude-sonnet-4-5-20250929',
    messages: [
      { role: 'user', content: 'Hello' },
    ],
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
      'anthropic-version': '2023-06-01',
    },
    timeout: '30s',
  };

  const res = http.post(`http://${GATEWAY_ADDRESS}/anthropic`, payload, params);

  if (res.status === 429) {
    rateLimited.add(1);
  } else if (res.status === 200) {
    successful.add(1);
  }

  check(res, {
    'status is 200 or 429': (r) => r.status === 200 || r.status === 429,
  });

  // Log rate limit headers when present
  const remaining = res.headers['X-Ratelimit-Remaining'];
  const limit = res.headers['X-Ratelimit-Limit'];
  if (remaining !== undefined) {
    console.log(`Rate limit: ${remaining}/${limit} remaining`);
  }
}
