/** Browser-safe HTTP client. Never accepts or exposes AWS credentials. */
export class ApiError extends Error {
  constructor(message, { code = "REQUEST_FAILED", status = 0 } = {}) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

export function makeUrl(baseUrl = "", endpoint, params = {}) {
  if (!endpoint.startsWith("/api/")) throw new Error("Only EnviroSync API endpoints are allowed.");
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null) query.set(key, String(value));
  }
  const base = baseUrl.replace(/\/+$/, "");
  return `${base}${endpoint}${query.size ? `?${query}` : ""}`;
}

export async function requestJson(baseUrl, endpoint, params = {}, options = {}, fetcher = fetch) {
  let response;
  try {
    response = await fetcher(makeUrl(baseUrl, endpoint, params), {
      method: options.method || "GET",
      headers: {
        Accept: "application/json",
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...(options.token ? { Authorization: `Bearer ${options.token}` } : {}),
      },
      ...(options.body ? { body: JSON.stringify(options.body) } : {}),
      signal: options.signal,
      cache: "no-store",
    });
  } catch (error) {
    if (error?.name === "AbortError") throw error;
    throw new ApiError("Cannot reach EnviroSync API. Check the API endpoint or service status.", { code: "NETWORK_ERROR" });
  }
  let body;
  try {
    body = await response.json();
  } catch {
    throw new ApiError("The API returned a non-JSON response.", { code: "BAD_RESPONSE", status: response.status });
  }
  if (!response.ok) {
    throw new ApiError(body?.error?.message || `Request failed (HTTP ${response.status}).`, {
      code: body?.error?.code || "HTTP_ERROR",
      status: response.status,
    });
  }
  return body;
}

export function createApi(baseUrl = "", fetcher = fetch) {
  const request = (endpoint, params, options) => requestJson(baseUrl, endpoint, params, options, fetcher);
  return {
    health: (options) => request("/api/health", {}, options),
    datasets: (options) => request("/api/datasets", {}, options),
    observations: (params, options) => request("/api/observations", params, options),
    compare: (params, options) => request("/api/compare", params, options),
    adminSession: (token) => request("/api/admin/session", {}, { token }),
    uploadDataset: (payload, token) => request("/api/admin/datasets", {}, { method: "POST", body: payload, token }),
  };
}
