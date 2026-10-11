/** Browser-safe HTTP client. ALL AWS credentials remain in the Python backend. */
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
      method: "GET",
      headers: { Accept: "application/json" },
      signal: options.signal,
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
  };
}
