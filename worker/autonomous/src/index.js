const JSON_HEADERS = {
  "content-type": "application/json; charset=utf-8",
  "cache-control": "no-store",
  "x-content-type-options": "nosniff",
};

const WORKER_NAME = "alili-cortex-autonomous-worker";
const MAX_HISTORY = 10;

function json(data, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: JSON_HEADERS });
}

async function inspectCoreApi(env) {
  if (!env.AC_API || typeof env.AC_API.fetch !== "function") {
    return { reachable: false, status: "service_binding_missing" };
  }
  try {
    const response = await env.AC_API.fetch(new Request("https://ac-internal/health", {
      method: "GET",
      headers: { accept: "application/json" },
    }));
    if (!response.ok) {
      return { reachable: false, status: "http_error", http_status: response.status };
    }
    const raw = await response.text();
    if (raw.length > 8192) return { reachable: false, status: "response_too_large" };
    let body;
    try { body = JSON.parse(raw); } catch {
      return { reachable: false, status: "invalid_json" };
    }
    return {
      reachable: body?.ok === true || body?.status === "healthy",
      status: "responded",
      http_status: response.status,
      service: typeof body?.service === "string" ? body.service.slice(0, 100) : null,
      version: typeof body?.version === "string" ? body.version.slice(0, 40) : null,
    };
  } catch {
    return { reachable: false, status: "connection_failed" };
  }
}

async function latestRuns(env) {
  const result = await env.AC_STATE.prepare(
    "SELECT id, started_at, trigger_type, status, details FROM worker_runs ORDER BY started_at DESC LIMIT ?",
  ).bind(MAX_HISTORY).all();
  return result.results ?? [];
}

async function recordRun(env, { id, startedAt, triggerType, api }) {
  const status = api.reachable ? "completed" : "api_unavailable";
  const details = JSON.stringify({
    api_reachable: api.reachable,
    api_status: api.status,
    api_http_status: api.http_status ?? null,
    api_service: api.service ?? null,
    api_version: api.version ?? null,
    note: "Connectivity heartbeat only. No model training, external code execution, or production mutation.",
  });
  await env.AC_STATE.prepare(
    "INSERT OR IGNORE INTO worker_runs (id, worker_name, started_at, trigger_type, status, details) VALUES (?, ?, ?, ?, ?, ?)",
  ).bind(id, WORKER_NAME, startedAt, triggerType, status, details).run();
  return status;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method !== "GET" || !["/", "/health", "/api-status"].includes(url.pathname)) {
      return json({ ok: false, error: "not_found" }, 404);
    }

    const api = await inspectCoreApi(env);
    if (url.pathname === "/api-status") {
      const runs = await latestRuns(env);
      return json({
        service: "Alili Cortex",
        worker: WORKER_NAME,
        api,
        latest_runs: runs,
        autonomous_learning: "not_enabled",
      });
    }

    return json({
      ok: true,
      service: "Alili Cortex",
      worker: WORKER_NAME,
      status: "active",
      core_api: api,
      autonomous_learning: "not_enabled",
    });
  },

  async scheduled(controller, env) {
    const scheduledTime = Number(controller.scheduledTime) || Date.now();
    const startedAt = new Date(scheduledTime).toISOString();
    const api = await inspectCoreApi(env);
    await recordRun(env, {
      id: "cron-" + scheduledTime,
      startedAt,
      triggerType: "cron",
      api,
    });
  },
};
