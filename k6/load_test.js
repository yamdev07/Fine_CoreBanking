/**
 * CoreBanking — Tests de charge k6
 * Scénario 1 : Charge nominale  → 100 VU, 5 min
 * Scénario 2 : Charge de pointe → rampe progressive jusqu'à 1 000 VU, 2 min
 *
 * Usage :
 *   k6 run --env SCENARIO=nominal  k6/load_test.js
 *   k6 run --env SCENARIO=pointe   k6/load_test.js
 */

import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend, Counter } from "k6/metrics";
import { setTimeout } from "k6/timers";

// ── Custom metrics ─────────────────────────────────────────────────────────────
const errorRate   = new Rate("error_rate");
const dashTime    = new Trend("dashboard_ms",   true);
const entriesTime = new Trend("entries_ms",     true);
const reportsTime = new Trend("reports_ms",     true);
const totalReqs   = new Counter("total_requests");

// ── Config ─────────────────────────────────────────────────────────────────────
const BASE_ACC = "http://localhost:8000";
const BASE_REP = "http://localhost:8001";
const AS_OF    = "2026-06-13";
const START    = "2026-01-01";
const END      = "2026-06-13";

const scenario = __ENV.SCENARIO || "nominal";

export const options =
  scenario === "pointe"
    ? {
        scenarios: {
          pointe: {
            executor: "ramping-vus",
            startVUs: 0,
            stages: [
              { duration: "30s", target: 200  },
              { duration: "30s", target: 500  },
              { duration: "30s", target: 1000 },
              { duration: "30s", target: 0    },
            ],
          },
        },
        thresholds: {
          http_req_duration: ["p(50)<500", "p(95)<1500", "p(99)<3000"],
          error_rate:        ["rate<0.05"],
          http_req_failed:   ["rate<0.05"],
        },
      }
    : {
        scenarios: {
          nominal: {
            executor: "constant-vus",
            vus: 100,
            duration: "5m",
          },
        },
        thresholds: {
          http_req_duration: ["p(50)<300", "p(95)<800", "p(99)<1500"],
          error_rate:        ["rate<0.02"],
          http_req_failed:   ["rate<0.02"],
        },
      };

// ── Pool de 30 utilisateurs (1 par VU en rotation) ────────────────────────────
const USERS = Array.from({ length: 30 }, (_, i) => ({
  username: `testuser${String(i + 1).padStart(2, "0")}`,
  password: "Test1234!",
}));

// ── Setup : login tous les utilisateurs, retourne un tableau de tokens ─────────
export function setup() {
  const tokens = [];

  for (const u of USERS) {
    const res = http.post(
      `${BASE_ACC}/api/v1/auth/login`,
      JSON.stringify({ username: u.username, password: u.password }),
      { headers: { "Content-Type": "application/json" } }
    );
    if (res.status === 200) {
      tokens.push(JSON.parse(res.body).access_token);
    } else {
      console.warn(`Login échoué pour ${u.username}: ${res.status}`);
    }
    sleep(0.35); // 350ms entre chaque login pour rester sous le rate limit
  }

  console.log(`✓ ${tokens.length}/${USERS.length} tokens obtenus`);
  return { tokens };
}

// ── Scénario utilisateur ───────────────────────────────────────────────────────
export default function (data) {
  // Chaque VU utilise un token différent (rotation sur 30 utilisateurs)
  const token   = data.tokens[(__VU - 1) % data.tokens.length];
  const headers = {
    "Content-Type":  "application/json",
    "Authorization": `Bearer ${token}`,
  };

  const r = Math.random();

  if (r < 0.30) {
    // 30% — Dashboard temps réel
    const t0  = Date.now();
    const res = http.get(`${BASE_REP}/api/v1/reports/dashboard?as_of_date=${AS_OF}`, { headers });
    dashTime.add(Date.now() - t0);
    totalReqs.add(1);
    errorRate.add(!check(res, { "dashboard 200": (r) => r.status === 200 }));

  } else if (r < 0.55) {
    // 25% — Liste des écritures
    const t0  = Date.now();
    const res = http.get(`${BASE_ACC}/api/v1/journal-entries/?size=20&status=POSTED`, { headers });
    entriesTime.add(Date.now() - t0);
    totalReqs.add(1);
    errorRate.add(!check(res, { "entries 200": (r) => r.status === 200 }));

  } else if (r < 0.70) {
    // 15% — Balance générale
    const t0  = Date.now();
    const res = http.get(
      `${BASE_REP}/api/v1/reports/trial-balance?start_date=${START}&end_date=${END}`,
      { headers }
    );
    reportsTime.add(Date.now() - t0);
    totalReqs.add(1);
    errorRate.add(!check(res, { "trial-balance 200": (r) => r.status === 200 }));

  } else if (r < 0.82) {
    // 12% — Plan de comptes
    const res = http.get(`${BASE_ACC}/api/v1/accounts/?size=50`, { headers });
    totalReqs.add(1);
    errorRate.add(!check(res, { "accounts 200": (r) => r.status === 200 }));

  } else if (r < 0.92) {
    // 10% — Bilan comptable
    const t0  = Date.now();
    const res = http.get(
      `${BASE_REP}/api/v1/reports/balance-sheet?as_of_date=${AS_OF}`,
      { headers }
    );
    reportsTime.add(Date.now() - t0);
    totalReqs.add(1);
    errorRate.add(!check(res, { "balance-sheet 200": (r) => r.status === 200 }));

  } else {
    // 8% — Health check (sans auth)
    const res = http.get(`${BASE_ACC}/api/v1/health/ready`);
    totalReqs.add(1);
    errorRate.add(!check(res, { "health 200": (r) => r.status === 200 }));
  }

  sleep(Math.random() * 1 + 0.5);
}
