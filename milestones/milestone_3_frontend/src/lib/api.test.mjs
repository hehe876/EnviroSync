import test from "node:test";
import assert from "node:assert/strict";
import { createApi, makeUrl, requestJson } from "./api.mjs";

test("only real /api routes are requested and query parameters are encoded", () => {
  const link = makeUrl("http://localhost:8000/", "/api/observations", { city: "london", start: "2025-07-01", end: "2025-07-31" });
  assert.equal(link, "http://localhost:8000/api/observations?city=london&start=2025-07-01&end=2025-07-31");
  assert.throws(() => makeUrl("", "/fake/demo"), /Only EnviroSync/);
});

test("real API contract is consumed without mock weather values", async () => {
  const requested = [];
  const fakeFetch = async (url) => {
    requested.push(url);
    return { ok: true, status: 200, json: async () => ({ schema_version: "1.0", datasets: [{ city: "london", aws_region: "eu-west-2" }] }) };
  };
  const result = await createApi("", fakeFetch).datasets();
  assert.deepEqual(requested, ["/api/datasets"]);
  assert.equal(result.datasets[0].aws_region, "eu-west-2");
});

test("API errors preserve backend code and helpful message", async () => {
  const fakeFetch = async () => ({ ok: false, status: 502, json: async () => ({ error: { code: "INVALID_REMOTE_DATA", message: "Dataset integrity failed" } }) });
  await assert.rejects(() => requestJson("", "/api/datasets", {}, {}, fakeFetch), (err) => {
    assert.equal(err.code, "INVALID_REMOTE_DATA");
    assert.equal(err.status, 502);
    assert.match(err.message, /integrity/);
    return true;
  });
});

test("network errors are explicit; do not silently use bundled example data", async () => {
  const fakeFetch = async () => { throw new TypeError("Failed to fetch"); };
  await assert.rejects(() => createApi("", fakeFetch).datasets(), (err) => err.code === "NETWORK_ERROR");
});

test("abort is propagated as abort rather than a false offline error", async () => {
  const fakeFetch = async () => { const error = new Error("Aborted"); error.name = "AbortError"; throw error; };
  await assert.rejects(() => createApi("", fakeFetch).health(), (err) => err.name === "AbortError");
});

test("hosting with an empty catalog returns zero datasets without inventing observations", async () => {
  const fakeFetch = async () => ({ ok: true, status: 200, json: async () => ({ schema_version: "1.0", datasets: [] }) });
  const catalog = await createApi("", fakeFetch).datasets();
  assert.equal(catalog.schema_version, "1.0");
  assert.deepEqual(catalog.datasets, []);
});
