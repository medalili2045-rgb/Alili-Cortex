import test from "node:test";
import assert from "node:assert/strict";
import worker from "../src/index.js";

const request = (path, { method = "GET", token, body, headers = {} } = {}) =>
  new Request(`https://api.example.test${path}`, {
    method,
    headers: {
      ...(token ? { authorization: `Bearer ${token}` } : {}),
      ...(body !== undefined ? { "content-type": "application/json" } : {}),
      ...headers,
    },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });

test("health is public and does not expose provider secrets", async () => {
  const response = await worker.fetch(request("/health"), { GEMINI_API_KEY: "hidden" });
  const data = await response.json();
  assert.equal(response.status, 200);
  assert.equal(data.ok, true);
  assert.equal(JSON.stringify(data).includes("hidden"), false);
});

test("private routes reject missing and incorrect credentials", async () => {
  const env = { APP_API_KEY: "correct-secret" };
  assert.equal((await worker.fetch(request("/v1/providers/status"), env)).status, 401);
  assert.equal((await worker.fetch(request("/v1/providers/status", { token: "wrong" }), env)).status, 401);
  assert.equal((await worker.fetch(request("/v1/providers/status", { token: "correct-secret" }), env)).status, 200);
});

test("chat fails closed when no provider has an explicitly confirmed free tier", async () => {
  const response = await worker.fetch(request("/v1/chat", {
    method: "POST", token: "secret", body: { messages: [{ role: "user", content: "hello" }] },
  }), { APP_API_KEY: "secret", GEMINI_API_KEY: "configured" });
  const data = await response.json();
  assert.equal(response.status, 503);
  assert.equal(data.error, "no_free_provider_configured");
});

test("chat rejects oversized bodies before parsing or provider calls", async () => {
  const messages = Array.from({ length: 5 }, (_, index) => ({
    role: index % 2 === 0 ? "user" : "assistant",
    content: "x".repeat(15000),
  }));
  const response = await worker.fetch(request("/v1/chat", {
    method: "POST",
    token: "secret",
    body: { messages },
  }), { APP_API_KEY: "secret" });
  assert.equal(response.status, 413);
  assert.equal((await response.json()).error, "request_too_large");
});

test("chat validates the message contract before provider calls", async () => {
  const response = await worker.fetch(request("/v1/chat", {
    method: "POST", token: "secret", body: { messages: [] },
  }), { APP_API_KEY: "secret" });
  assert.equal(response.status, 400);
});

test("Gemini provider is called only after free tier confirmation", async (t) => {
  const originalFetch = globalThis.fetch;
  t.after(() => { globalThis.fetch = originalFetch; });
  globalThis.fetch = async () => new Response(JSON.stringify({
    candidates: [{ content: { parts: [{ text: "مرحباً" }] } }],
  }), { status: 200, headers: { "content-type": "application/json" } });

  const response = await worker.fetch(request("/v1/chat", {
    method: "POST", token: "secret", body: { messages: [{ role: "user", content: "مرحبا" }] },
  }), {
    APP_API_KEY: "secret",
    GEMINI_API_KEY: "test-key",
    FREE_GEMINI_CONFIRMED: "true",
  });
  const data = await response.json();
  assert.equal(response.status, 200);
  assert.equal(data.ok, true);
  assert.equal(data.provider, "gemini");
  assert.equal(data.message.content, "مرحباً");
});

test("Wikipedia search is authenticated and returns bounded source links", async (t) => {
  const originalFetch = globalThis.fetch;
  t.after(() => { globalThis.fetch = originalFetch; });
  globalThis.fetch = async (url) => {
    assert.match(String(url), /^https:\/\/ar\.wikipedia\.org\/w\/api\.php\?/);
    return new Response(JSON.stringify({ query: { search: [{ title: "الذكاء الاصطناعي", snippet: "<span>مجال <b>علمي</b> حديث &amp; متطور</span>" }] } }), { status: 200, headers: { "content-type": "application/json" } });
  };
  const denied = await worker.fetch(request("/v1/search", { method: "POST", body: { query: "الذكاء الاصطناعي" } }), { APP_API_KEY: "secret" });
  assert.equal(denied.status, 401);
  const response = await worker.fetch(request("/v1/search", { method: "POST", token: "secret", body: { query: "الذكاء الاصطناعي" } }), { APP_API_KEY: "secret" });
  const data = await response.json();
  assert.equal(response.status, 200);
  assert.equal(data.provider, "wikipedia");
  assert.equal(data.results.length, 1);
  assert.equal(data.results[0].snippet, "مجال علمي حديث & متطور");
  assert.match(data.results[0].url, /^https:\/\/ar\.wikipedia\.org\/wiki\//);
});

test("Wikipedia search rejects invalid query lengths", async () => {
  const response = await worker.fetch(request("/v1/search", { method: "POST", token: "secret", body: { query: "x" } }), { APP_API_KEY: "secret" });
  assert.equal(response.status, 400);
  assert.equal((await response.json()).error, "invalid_search_query");
});