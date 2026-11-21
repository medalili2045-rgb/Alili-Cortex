import test from "node:test";
import assert from "node:assert/strict";
import worker from "../src/index.js";

function envFor(apiResponse = { ok: true, service: "Alili Cortex API", version: "0.1.0", status: "healthy" }) {
  const writes = [];
  const env = {
    writes,
    AC_API: {
      async fetch() {
        return new Response(JSON.stringify(apiResponse), { status: 200 });
      },
    },
    AC_STATE: {
      prepare(sql) {
        if (sql.startsWith("SELECT")) {
          return { bind: () => ({ all: async () => ({ results: [] }) }) };
        }
        return { bind: (...values) => ({ run: async () => { writes.push(values); return { success: true }; } }) };
      },
    },
  };
  return env;
}

test("health endpoint checks the connected Alili Cortex API", async () => {
  const env = envFor();
  const response = await worker.fetch(new Request("https://worker.test/health"), env);
  const body = await response.json();
  assert.equal(response.status, 200);
  assert.equal(body.core_api.reachable, true);
  assert.equal(body.core_api.service, "Alili Cortex API");
});

test("API failure is reported without exposing internal error details", async () => {
  const env = envFor();
  env.AC_API.fetch = async () => { throw new Error("private detail"); };
  const response = await worker.fetch(new Request("https://worker.test/health"), env);
  const body = await response.json();
  assert.equal(body.core_api.reachable, false);
  assert.equal(body.core_api.status, "connection_failed");
  assert.equal(JSON.stringify(body).includes("private detail"), false);
});

test("scheduled heartbeat persists API connectivity state", async () => {
  const env = envFor();
  await worker.scheduled({ scheduledTime: 1795220100000 }, env);
  assert.equal(env.writes.length, 1);
  assert.equal(env.writes[0][0], "cron-1795220100000");
  assert.equal(env.writes[0][4], "completed");
});

test("scheduled heartbeat records an unavailable API", async () => {
  const env = envFor();
  env.AC_API.fetch = async () => new Response("unavailable", { status: 503 });
  await worker.scheduled({ scheduledTime: 1795220100000 }, env);
  assert.equal(env.writes[0][4], "api_unavailable");
});
