const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
const TOKEN_KEY = "railway_access_token";

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
    this.name = "ApiError";
  }
}

export function getToken() {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

/** True when the backend rejected the stored token (missing, invalid or expired). */
export function isAuthError(error: unknown) {
  return error instanceof ApiError && error.status === 401;
}

// FastAPI returns `detail` as a string for HTTPException and as a list of
// {loc, msg} objects for request validation errors (422).
function errorMessage(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const messages = detail.map((item) => {
      const field = Array.isArray(item?.loc) ? item.loc[item.loc.length - 1] : undefined;
      const msg = typeof item?.msg === "string" ? item.msg : "Invalid value";
      return field ? `${field}: ${msg}` : msg;
    });
    if (messages.length) return messages.join("\n");
  }
  return "Request failed";
}

export async function apiRequest(path: string, options: RequestInit = {}) {
  const token = getToken();
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers
    }
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new ApiError(errorMessage(body.detail), response.status);
  return body;
}
