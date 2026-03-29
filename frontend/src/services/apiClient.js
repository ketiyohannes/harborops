export function createApiClient(baseUrl) {
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
    if (includeCsrf) {
      headers["X-CSRFToken"] = await fetchCsrfToken();
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
