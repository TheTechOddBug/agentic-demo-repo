import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Trend } from 'k6/metrics';

// Custom metrics for LLM-specific tracking
const inputTokens = new Counter('llm_input_tokens');
const outputTokens = new Counter('llm_output_tokens');
const llmLatency = new Trend('llm_latency_ms');

// Configuration — set GATEWAY_ADDRESS env var before running
const GATEWAY_ADDRESS = __ENV.GATEWAY_ADDRESS || 'localhost:8080';

export const options = {
  stages: [
    { duration: '30s', target: 5 },   // Ramp up to 5 VUs
    { duration: '2m', target: 10 },    // Sustain 10 VUs
    { duration: '30s', target: 0 },    // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<15000'],  // 95% of requests under 15s
    http_req_failed: ['rate<0.1'],       // Less than 10% error rate
  },
};

const prompts = [
  'Explain Kubernetes networking in one sentence.',
  'What is a service mesh?',
  'Describe the Gateway API in Kubernetes.',
  'What is an MCP server?',
  'Explain agent-to-agent communication.',
];

export default function () {
  const prompt = prompts[Math.floor(Math.random() * prompts.length)];

  const payload = JSON.stringify({
    model: 'claude-sonnet-4-5-20250929',
    messages: [
      { role: 'user', content: prompt },
    ],
  });

  const params = {
    headers: {
      'Content-Type': 'application/json',
      'anthropic-version': '2023-06-01',
    },
    timeout: '30s',
  };

  const startTime = Date.now();
  const res = http.post(`http://${GATEWAY_ADDRESS}/anthropic`, payload, params);
  const duration = Date.now() - startTime;

  llmLatency.add(duration);

  check(res, {
    'status is 200': (r) => r.status === 200,
    'response has content': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.content && body.content.length > 0;
      } catch (e) {
        return false;
      }
    },
  });

  // Extract token usage from response
  if (res.status === 200) {
    try {
      const body = JSON.parse(res.body);
      if (body.usage) {
        inputTokens.add(body.usage.input_tokens || 0);
        outputTokens.add(body.usage.output_tokens || 0);
      }
    } catch (e) {
      // Response parsing failed
    }
  }

  sleep(1);
}
