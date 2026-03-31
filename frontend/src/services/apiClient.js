export function createApiClient(baseUrl) {
  function createReplayNonce() {
    if (globalThis.crypto?.randomUUID) {
      return globalThis.crypto.randomUUID();
    }
    return `${Date.now()}-${Math.random().toString(36).slice(2, 12)}`;
  }

  function buildApiError(response, payload) {
    const message = payload?.detail || `Request failed (${response.status})`;
    const error = new Error(message);
    error.status = response.status;
    error.payload = payload;
    return error;
  }

  async function fetchCsrfToken() {
    const response = await fetch(`${baseUrl}/api/auth/csrf/`, { credentials: "include" });
    const data = await response.json();
    return data.csrfToken;
  }

  async function request(path, options = {}, includeCsrf = false) {
    const headers = { ...(options.headers || {}) };
    const method = (options.method || "GET").toUpperCase();
    const isMutating = ["POST", "PUT", "PATCH", "DELETE"].includes(method);
    if (includeCsrf) {
      headers["X-CSRFToken"] = await fetchCsrfToken();
    }
    if (isMutating) {
      headers["X-Request-Timestamp"] = new Date().toISOString();
      headers["X-Request-Nonce"] = createReplayNonce();
    }

    const response = await fetch(`${baseUrl}${path}`, {
      credentials: "include",
      ...options,
      headers,
    });

    let payload = null;
    if (response.status !== 204) {
      try {
        payload = await response.json();
      } catch {
        payload = null;
      }
    }

    if (!response.ok) {
      throw buildApiError(response, payload);
    }

    return payload;
  }

  return {
    fetchCsrfToken,
    request,
  };
}
