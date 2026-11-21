const JSON_HEADERS = {
  "content-type": "application/json; charset=utf-8",
  "cache-control": "no-store",
  "x-content-type-options": "nosniff",
};

const MAX_BODY_BYTES = 64 * 1024;
const MAX_MESSAGES = 50;
const MAX_MESSAGE_CHARS = 16000;
const PROVIDER_ORDER = ["gemini", "groq", "nvidia", "cloudflare"];

function json(data, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...JSON_HEADERS, ...extraHeaders },
  });
}

function corsHeaders(request, env) {
  const origin = request.headers.get("origin");
  const allowed = String(env.CORS_ORIGINS || "").split(",").map((v) => v.trim()).filter(Boolean);
  const headers = { "vary": "Origin" };
  if (origin && (allowed.includes("*") || allowed.includes(origin))) {
    headers["access-control-allow-origin"] = allowed.includes("*") ? "*" : origin;
    headers["access-control-allow-methods"] = "GET, POST, OPTIONS";
    headers["access-control-allow-headers"] = "authorization, content-type";
    headers["access-control-max-age"] = "86400";
  }
  return headers;
}

function authorized(request, env) {
  const expected = String(env.APP_API_KEY || "");
  const supplied = String(request.headers.get("authorization") || "");
  if (!expected || !supplied.startsWith("Bearer ")) return false;
  const actual = supplied.slice(7);
  if (actual.length !== expected.length) return false;
  let mismatch = 0;
  for (let i = 0; i < expected.length; i += 1) mismatch |= expected.charCodeAt(i) ^ actual.charCodeAt(i);
  return mismatch === 0;
}

function providerEnabled(env, name) {
  const secretName = {
    gemini: "GEMINI_API_KEY",
    groq: "GROQ_API_KEY",
    nvidia: "NVIDIA_API_KEY",
    cloudflare: "AI",
  }[name];
  return Boolean(env[secretName]) && String(env[`FREE_${name.toUpperCase()}_CONFIRMED`] || "").toLowerCase() === "true";
}

function providerStatus(env) {
  return PROVIDER_ORDER.map((name) => ({
    provider: name,
    enabled: providerEnabled(env, name),
    reason: providerEnabled(env, name)
      ? "free_tier_operator_confirmed"
      : "not_configured_or_free_tier_not_confirmed",
  }));
}

function validateMessages(value) {
  if (!value || !Array.isArray(value.messages) || value.messages.length === 0) {
    return "messages must be a non-empty array";
  }
  if (value.messages.length > MAX_MESSAGES) return `messages cannot exceed ${MAX_MESSAGES}`;
  for (const message of value.messages) {
    if (!message || !["system", "user", "assistant"].includes(message.role) ||
        typeof message.content !== "string" || !message.content.trim() ||
        message.content.length > MAX_MESSAGE_CHARS) {
      return "each message must have a supported role and non-empty text content";
    }
  }
  return null;
}

async function callGemini(env, messages) {
  const model = env.GEMINI_MODEL || "gemini-2.5-flash";
  const system = messages.filter((m) => m.role === "system").map((m) => m.content).join("\n");
  const contents = messages.filter((m) => m.role !== "system").map((m) => ({
    role: m.role === "assistant" ? "model" : "user",
    parts: [{ text: m.content }],
  }));
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json", "x-goog-api-key": env.GEMINI_API_KEY },
    body: JSON.stringify({
      ...(system ? { systemInstruction: { parts: [{ text: system }] } } : {}),
      contents,
      generationConfig: { maxOutputTokens: 2048, temperature: 0.7 },
    }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(`Gemini HTTP ${response.status}`);
  const text = data.candidates?.[0]?.content?.parts?.map((p) => p.text || "").join("").trim();
  if (!text) throw new Error("Gemini returned an empty response");
  return { text, model, provider: "gemini" };
}

async function callOpenAICompatible(env, name, baseUrl, key, model, messages) {
  const response = await fetch(`${baseUrl}/chat/completions`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      authorization: `Bearer ${key}`,
    },
    body: JSON.stringify({ model, messages, temperature: 0.7, max_tokens: 2048 }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(`${name} HTTP ${response.status}`);
  const text = data.choices?.[0]?.message?.content;
  if (typeof text !== "string" || !text.trim()) throw new Error(`${name} returned an empty response`);
  return { text: text.trim(), model: data.model || model, provider: name };
}

async function callProvider(env, name, messages) {
  if (name === "gemini") return callGemini(env, messages);
  if (name === "groq") {
    return callOpenAICompatible(env, "groq", "https://api.groq.com/openai/v1",
      env.GROQ_API_KEY, env.GROQ_MODEL || "llama-3.3-70b-versatile", messages);
  }
  if (name === "nvidia") {
    return callOpenAICompatible(env, "nvidia", "https://integrate.api.nvidia.com/v1",
      env.NVIDIA_API_KEY, env.NVIDIA_MODEL || "meta/llama-3.3-70b-instruct", messages);
  }
  if (name === "cloudflare") {
    const model = env.CF_AI_MODEL || "@cf/meta/llama-3.1-8b-instruct";
    const result = await env.AI.run(model, { messages });
    const text = result?.response || result?.result?.response;
    if (typeof text !== "string" || !text.trim()) throw new Error("Cloudflare AI returned an empty response");
    return { text: text.trim(), model, provider: "cloudflare" };
  }
  throw new Error("Unknown provider");
}

async function readLimitedBody(request) {
  const declaredLength = Number(request.headers.get("content-length") || 0);
  if (Number.isFinite(declaredLength) && declaredLength > MAX_BODY_BYTES) {
    return { tooLarge: true };
  }
  if (!request.body) return { text: "" };

  const reader = request.body.getReader();
  const chunks = [];
  let total = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.byteLength;
    if (total > MAX_BODY_BYTES) {
      await reader.cancel();
      return { tooLarge: true };
    }
    chunks.push(value);
  }

  const bytes = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return { text: new TextDecoder().decode(bytes) };
}

function cleanSearchSnippet(value) {
  return String(value || "").replace(/<[^>]*>/g, " ").replace(/&quot;/g, '"').replace(/&#39;|&apos;/g, "'").replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/\s+/g, " ").trim().slice(0, 700);
}

async function handleSearch(request, env) {
  const bodyResult = await readLimitedBody(request);
  if (bodyResult.tooLarge) return json({ ok: false, error: "request_too_large" }, 413);
  let body;
  try { body = JSON.parse(bodyResult.text); } catch { return json({ ok: false, error: "invalid_json" }, 400); }
  const query = typeof body?.query === "string" ? body.query.trim() : "";
  if (query.length < 2 || query.length > 200) return json({ ok: false, error: "invalid_search_query" }, 400);
  const language = String(env.WIKIPEDIA_LANGUAGE || "ar").toLowerCase();
  if (!/^[a-z-]{2,12}$/.test(language)) return json({ ok: false, error: "invalid_search_configuration" }, 500);
  const url = new URL("https://" + language + ".wikipedia.org/w/api.php");
  url.search = new URLSearchParams({ action: "query", list: "search", srsearch: query, srlimit: "5", format: "json", utf8: "1" }).toString();
  let response;
  try { response = await fetch(url, { headers: { "user-agent": "AliliCortex/0.1 (knowledge search)" }, signal: AbortSignal.timeout(10000) }); }
  catch { return json({ ok: false, error: "search_provider_unavailable" }, 502); }
  if (!response.ok) return json({ ok: false, error: "search_provider_unavailable" }, 502);
  let data;
  try { data = await response.json(); } catch { return json({ ok: false, error: "search_provider_invalid_response" }, 502); }
  const results = (Array.isArray(data?.query?.search) ? data.query.search : []).slice(0, 5).map((item) => {
    const title = String(item?.title || "").slice(0, 300);
    return { title, snippet: cleanSearchSnippet(item?.snippet), url: "https://" + language + ".wikipedia.org/wiki/" + encodeURIComponent(title.replace(/ /g, "_")) };
  }).filter((item) => item.title);
  return json({ ok: true, provider: "wikipedia", language, query, results, limited_scope: "Wikipedia knowledge search; not a general web search engine." });
}
async function handleChat(request, env) {
  const bodyResult = await readLimitedBody(request);
  if (bodyResult.tooLarge) {
    return json({ ok: false, error: "request_too_large" }, 413);
  }
  const raw = bodyResult.text;
  let body;
  try { body = JSON.parse(raw); } catch { return json({ ok: false, error: "invalid_json" }, 400); }
  const validationError = validateMessages(body);
  if (validationError) return json({ ok: false, error: "invalid_request", detail: validationError }, 400);

  const enabled = PROVIDER_ORDER.filter((name) => providerEnabled(env, name));
  if (enabled.length === 0) {
    return json({
      ok: false,
      error: "no_free_provider_configured",
      detail: "Configure a provider key and explicitly confirm its currently free tier before enabling it.",
    }, 503);
  }

  const failures = [];
  for (const name of enabled) {
    try {
      const result = await callProvider(env, name, body.messages);
      return json({
        ok: true,
        provider: result.provider,
        model: result.model,
        message: { role: "assistant", content: result.text },
        fallback_used: failures.length > 0,
        failed_providers: failures,
      });
    } catch (error) {
      failures.push({ provider: name, error: String(error?.message || "provider_error").slice(0, 180) });
    }
  }
  return json({ ok: false, error: "all_providers_failed", failed_providers: failures }, 502);
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const cors = corsHeaders(request, env);

    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
    if (request.method === "GET" && (url.pathname === "/" || url.pathname === "/health")) {
      return json({ ok: true, service: "Alili Cortex API", version: "0.1.0", status: "healthy" }, 200, cors);
    }

    if (!authorized(request, env)) {
      return json({ ok: false, error: env.APP_API_KEY ? "unauthorized" : "server_auth_not_configured" },
        env.APP_API_KEY ? 401 : 503, cors);
    }

    if (request.method === "GET" && url.pathname === "/v1/providers/status") {
      return json({ ok: true, providers: providerStatus(env) }, 200, cors);
    }
    if (request.method === "POST" && url.pathname === "/v1/chat") {
      const response = await handleChat(request, env);
      const headers = new Headers(response.headers);
      for (const [key, value] of Object.entries(cors)) headers.set(key, value);
      return new Response(response.body, { status: response.status, headers });
    }
    if (request.method === "POST" && url.pathname === "/v1/search") {
      const response = await handleSearch(request, env);
      const headers = new Headers(response.headers);
      for (const [key, value] of Object.entries(cors)) headers.set(key, value);
      return new Response(response.body, { status: response.status, headers });
    }
    return json({ ok: false, error: "not_found" }, 404, cors);
  },
};
