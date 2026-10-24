export type User = {
  id: string;
  email: string;
  full_name: string;
  preferred_language: "en" | "hi";
  roles: Array<"USER" | "RECYCLER" | "ADMIN">;
  created_at: string;
};

export type ApiStatus = { status: string; service?: string; database?: string };

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = "ApiError";
  }
}

function csrfToken(): string | undefined {
  return document.cookie.split("; ").find((part) => part.startsWith("csrf_token="))?.split("=").slice(1).join("=");
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const token = csrfToken();
    if (token) headers.set("X-CSRF-Token", decodeURIComponent(token));
  }
  const response = await fetch(path, { ...init, method, headers, credentials: "include" });
  if (response.status === 204) return undefined as T;
  const data: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = data && typeof data === "object" && "detail" in data ? String(data.detail) : "Request failed";
    throw new ApiError(detail, response.status);
  }
  return data as T;
}

export async function getApiStatus(): Promise<ApiStatus> {
  return apiRequest<ApiStatus>("/api/v1/health/ready");
}

export async function getMe(): Promise<User | null> {
  try {
    return await apiRequest<User>("/api/v1/auth/me");
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
}

export async function login(input: { email: string; password: string }): Promise<User> {
  return apiRequest<User>("/api/v1/auth/login", { method: "POST", body: JSON.stringify(input) });
}

export async function register(input: { email: string; password: string; full_name: string; preferred_language: "en" | "hi"; enable_recycler: boolean }): Promise<User> {
  return apiRequest<User>("/api/v1/auth/register", { method: "POST", body: JSON.stringify(input) });
}

export async function logout(): Promise<void> {
  await apiRequest<void>("/api/v1/auth/logout", { method: "POST" });
}
