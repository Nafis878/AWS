/* Cognito Hosted UI sign-in using the OAuth 2.0 authorization-code flow with PKCE.
 * The app client is public (no client secret), so nothing secret ships to the browser.
 * Tokens are kept in sessionStorage and cleared when the tab closes. */
(function () {
  const cfg = window.AQMON_CONFIG;
  const redirectUri = window.location.origin + "/";
  const store = window.sessionStorage;

  function b64url(bytes) {
    return btoa(String.fromCharCode(...new Uint8Array(bytes))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }

  function randomString(len) {
    return b64url(crypto.getRandomValues(new Uint8Array(len)));
  }

  function decodeJwt(token) {
    const payload = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(decodeURIComponent(escape(atob(payload))));
  }

  async function login() {
    const verifier = randomString(48);
    const state = randomString(16);
    const challenge = b64url(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier)));
    store.setItem("pkce_verifier", verifier);
    store.setItem("oauth_state", state);
    const params = new URLSearchParams({
      response_type: "code",
      client_id: cfg.userPoolClientId,
      redirect_uri: redirectUri,
      scope: "openid email profile",
      state,
      code_challenge_method: "S256",
      code_challenge: challenge,
    });
    window.location.assign(`https://${cfg.cognitoDomain}/oauth2/authorize?${params}`);
  }

  async function tokenRequest(body) {
    const res = await fetch(`https://${cfg.cognitoDomain}/oauth2/token`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ client_id: cfg.userPoolClientId, ...body }),
    });
    if (!res.ok) throw new Error(`token request failed (${res.status})`);
    const tokens = await res.json();
    store.setItem("id_token", tokens.id_token);
    if (tokens.refresh_token) store.setItem("refresh_token", tokens.refresh_token);
  }

  /* Exchange ?code=... for tokens after the Hosted UI redirects back. */
  async function handleRedirect() {
    const url = new URL(window.location.href);
    const code = url.searchParams.get("code");
    if (!code) return;
    const state = url.searchParams.get("state");
    const expected = store.getItem("oauth_state");
    window.history.replaceState({}, "", redirectUri);
    if (!expected || state !== expected) throw new Error("sign-in state mismatch, please sign in again");
    await tokenRequest({ grant_type: "authorization_code", code, redirect_uri: redirectUri, code_verifier: store.getItem("pkce_verifier") });
    store.removeItem("pkce_verifier");
    store.removeItem("oauth_state");
  }

  async function getIdToken() {
    const token = store.getItem("id_token");
    if (!token) return null;
    if (decodeJwt(token).exp * 1000 > Date.now() + 60_000) return token;
    const refresh = store.getItem("refresh_token");
    if (!refresh) return null;
    try {
      await tokenRequest({ grant_type: "refresh_token", refresh_token: refresh });
      return store.getItem("id_token");
    } catch (e) {
      store.clear();
      return null;
    }
  }

  function claims() {
    const token = store.getItem("id_token");
    return token ? decodeJwt(token) : null;
  }

  function logout() {
    store.clear();
    const params = new URLSearchParams({ client_id: cfg.userPoolClientId, logout_uri: redirectUri });
    window.location.assign(`https://${cfg.cognitoDomain}/logout?${params}`);
  }

  if (cfg && cfg.localMode) {
    // code/tools/local_server.py: no Cognito locally, the local API accepts any token.
    const local = { email: "local-developer", sub: "local-user", "cognito:groups": ["uploaders"] };
    window.AQAuth = { login() {}, logout() {}, async handleRedirect() {}, async getIdToken() { return "local"; }, claims: () => local };
    return;
  }
  window.AQAuth = { login, logout, handleRedirect, getIdToken, claims };
})();
