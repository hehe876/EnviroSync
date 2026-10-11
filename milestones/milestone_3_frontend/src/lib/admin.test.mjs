import test from "node:test";
import assert from "node:assert/strict";
import { createApi } from "./api.mjs";
import { adminConfigured } from "./admin.mjs";

test("admin sign-in is disabled when Cognito variables are absent", () => {
  assert.equal(adminConfigured, false);
});

test("admin upload sends a JSON POST with bearer token; does not persist credentials", async () => {
  const calls = [];
  const fetcher = async (url, options) => {
    calls.push({ url, options });
    return { ok: true, status: 201, json: async () => ({ created: true, dataset: { city: "berlin" } }) };
  };
  const api = createApi("", fetcher);
  const payload = { city: "berlin", filename: "berlin.csv", file_base64: "ZGF0YQ==" };
  const response = await api.uploadDataset(payload, "test-jwt");
  assert.equal(response.dataset.city, "berlin");
  assert.equal(calls[0].url, "/api/admin/datasets");
  assert.equal(calls[0].options.method, "POST");
  assert.equal(calls[0].options.headers.Authorization, "Bearer test-jwt");
  assert.deepEqual(JSON.parse(calls[0].options.body), payload);
  assert.equal(calls[0].options.cache, "no-store");
});

test("admin session is read-only and requires bearer token", async () => {
  const fetcher = async (url, options) => {
    assert.equal(url, "/api/admin/session");
    assert.equal(options.method, "GET");
    assert.equal(options.headers.Authorization, "Bearer test-jwt");
    return { ok: true, status: 200, json: async () => ({ admin: true }) };
  };
  assert.equal((await createApi("", fetcher).adminSession("test-jwt")).admin, true);
});
