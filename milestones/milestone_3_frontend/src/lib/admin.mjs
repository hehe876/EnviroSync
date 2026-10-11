/** Cognito OAuth2 authorization-code + PKCE. Access tokens are memory-only. */
const DOMAIN = (import.meta.env?.VITE_COGNITO_DOMAIN || "").replace(/\/+$/, "");
const CLIENT_ID = import.meta.env?.VITE_COGNITO_CLIENT_ID || "";
const STORAGE_KEY = "envirosync-pkce-4c";

export const adminConfigured = Boolean(DOMAIN && CLIENT_ID && /^https:\/\/[a-z0-9-]+\.auth\.ap-south-1\.amazoncognito\.com$/.test(DOMAIN));

function encodeUrl(bytes) {
  return btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function redirectUri() {
  return `${window.location.origin}/`;
}

export async function beginAdminSignIn() {
  if (!adminConfigured) throw new Error("Administrator authentication is not configured for this deployment.");
  const verifier = encodeUrl(crypto.getRandomValues(new Uint8Array(32)));
  const state = encodeUrl(crypto.getRandomValues(new Uint8Array(24)));
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ verifier, state, created: Date.now() }));
  const url = new URL(`${DOMAIN}/oauth2/authorize`);
  url.search = new URLSearchParams({
    response_type: "code",
    client_id: CLIENT_ID,
    scope: "openid email",
    redirect_uri: redirectUri(),
    state,
    code_challenge: encodeUrl(new Uint8Array(digest)),
    code_challenge_method: "S256",
  }).toString();
  window.location.assign(url.toString());
}

let completionPromise;
export function completeAdminSignIn(search = window.location.search, fetcher = fetch) {
  if (!completionPromise) completionPromise = performAdminSignIn(search, fetcher);
  return completionPromise;
}

async function performAdminSignIn(search, fetcher) {
  const params = new URLSearchParams(search);
  const code = params.get("code");
  if (!code) {
    if (params.get("error")) throw new Error("Administrator sign-in was cancelled or denied.");
    return null;
  }
  const data = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || "null");
  sessionStorage.removeItem(STORAGE_KEY);
  if (!adminConfigured || !data || data.state !== params.get("state") || Date.now() - data.created > 600_000) {
    throw new Error("Sign-in request expired or failed state verification. Please try again.");
  }
  const response = await fetcher(`${DOMAIN}/oauth2/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      client_id: CLIENT_ID,
      code,
      redirect_uri: redirectUri(),
      code_verifier: data.verifier,
    }),
  });
  if (!response.ok) throw new Error("Cognito could not complete administrator sign-in.");
  const tokens = await response.json();
  if (!tokens.access_token || tokens.token_type !== "Bearer") throw new Error("Invalid Cognito token response.");
  return { accessToken: tokens.access_token, expiresAt: Date.now() + (Math.min(tokens.expires_in || 900, 3600) - 30) * 1000 };
}

export function signOutAdmin() {
  sessionStorage.removeItem(STORAGE_KEY);
  if (!adminConfigured) return;
  const url = new URL(`${DOMAIN}/logout`);
  url.search = new URLSearchParams({ client_id: CLIENT_ID, logout_uri: redirectUri() }).toString();
  window.location.assign(url.toString());
}
