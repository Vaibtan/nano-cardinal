const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type RequestOptions = {
  method?: string;
  body?: unknown;
  params?: Record<string, string | number | boolean | null | undefined>;
};

async function request<T>(
  path: string,
  opts: RequestOptions = {},
): Promise<T> {
  const { method = "GET", body, params } = opts;

  let url = `${API_BASE}/api/v1${path}`;
  if (params) {
    const entries: [string, string][] = [];
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== null && value !== "") {
        entries.push([key, String(value)]);
      }
    }
    const qs = new URLSearchParams(entries).toString();
    url += `?${qs}`;
  }

  const headers: Record<string, string> = {};
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(
    path: string,
    params?: Record<string, string | number | boolean | null | undefined>,
  ) =>
    request<T>(path, { params }),

  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "POST", body }),

  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PATCH", body }),

  delete: (path: string) =>
    request<void>(path, { method: "DELETE" }),
};
