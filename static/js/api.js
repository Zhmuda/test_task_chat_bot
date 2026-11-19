export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

let onUnauthorized = () => {};

export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler;
}

async function request(method, url, body, { handle401 = true } = {}) {
  let response;
  try {
    response = await fetch(url, {
      method,
      credentials: "same-origin",
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, "Нет соединения с сервером");
  }

  if (response.status === 401 && handle401) onUnauthorized();

  if (!response.ok) {
    let message = `Ошибка сервера (${response.status})`;
    try {
      const data = await response.json();
      if (typeof data.detail === "string") message = data.detail;
    } catch {}
    throw new ApiError(response.status, message);
  }

  return response.status === 204 ? null : response.json();
}

export const api = {
  login: (accessKey) => request("POST", "/api/auth/login", { access_key: accessKey }, { handle401: false }),
  logout: () => request("POST", "/api/auth/logout"),
  checkSession: () => request("GET", "/api/auth/me", undefined, { handle401: false }),
  getMessages: () => request("GET", "/api/chat/messages"),
  sendMessage: (text) => request("POST", "/api/chat/messages", { text }),
  clearMessages: () => request("DELETE", "/api/chat/messages"),
};
