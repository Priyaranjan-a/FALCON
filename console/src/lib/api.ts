/**
 * HTTP client for the FALCON API.
 *
 * * Same-origin only: the session is an HttpOnly cookie the browser attaches.
 * * Every request carries X-Falcon-Request, which the server requires on
 *   state-changing calls (browsers cannot add it cross-site without CORS).
 * * Failures arrive as RFC 9457 problem documents and surface as ApiError.
 */

export interface FieldError {
  field: string;
  message: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly title: string;
  readonly errors: FieldError[];

  constructor(status: number, code: string, title: string, detail: string, errors: FieldError[] = []) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.title = title;
    this.errors = errors;
  }

  /** Message for one form field, if the server reported one. */
  field(name: string): string | undefined {
    return this.errors.find((e) => e.field === name || e.field.endsWith(`.${name}`))?.message;
  }
}

type Listener = (error: ApiError) => void;
const unauthenticatedListeners = new Set<Listener>();

/** Subscribe to "your session ended" failures (used by the session layer). */
export function onUnauthenticated(listener: Listener): () => void {
  unauthenticatedListeners.add(listener);
  return () => unauthenticatedListeners.delete(listener);
}

type Query = Record<string, string | number | boolean | null | undefined | Array<string | number>>;

function url(path: string, query?: Query): string {
  if (!query) return `/api/v1${path}`;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) value.forEach((v) => params.append(key, String(v)));
    else params.set(key, String(value));
  }
  const qs = params.toString();
  return `/api/v1${path}${qs ? `?${qs}` : ""}`;
}

async function request<T>(method: string, path: string, body?: unknown, query?: Query, signal?: AbortSignal): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url(path, query), {
      method,
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        "X-Falcon-Request": "1",
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal,
    });
  } catch (cause) {
    if ((cause as Error).name === "AbortError") throw cause;
    throw new ApiError(0, "network", "Connection lost", "FALCON could not be reached. Check your connection and try again.");
  }

  if (response.status === 204) return undefined as T;
  const text = await response.text();
  const data = text ? safeJson(text) : undefined;

  if (!response.ok) {
    const error = toApiError(response.status, response.statusText, text);
    if (response.status === 401) unauthenticatedListeners.forEach((l) => l(error));
    throw error;
  }
  return data as T;
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return undefined;
  }
}

function toApiError(status: number, statusText: string, text: string): ApiError {
  const problem = ((text && safeJson(text)) ?? {}) as Partial<{ code: string; title: string; detail: string; errors: FieldError[] }>;
  return new ApiError(status, problem.code ?? `http_${status}`, problem.title ?? statusText, problem.detail ?? "Something went wrong. Please try again.", problem.errors ?? []);
}

/**
 * Multipart upload with progress. fetch() cannot report upload progress, so
 * this one call uses XMLHttpRequest; errors surface as ApiError like the rest.
 */
export function upload<T>(path: string, form: FormData, { onProgress, signal }: { onProgress?: (fraction: number) => void; signal?: AbortSignal } = {}): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url(path));
    xhr.withCredentials = true;
    xhr.setRequestHeader("Accept", "application/json");
    xhr.setRequestHeader("X-Falcon-Request", "1");
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress?.(e.loaded / e.total);
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve((xhr.responseText ? safeJson(xhr.responseText) : undefined) as T);
        return;
      }
      const error = toApiError(xhr.status, xhr.statusText, xhr.responseText);
      if (xhr.status === 401) unauthenticatedListeners.forEach((l) => l(error));
      reject(error);
    };
    xhr.onerror = () => reject(new ApiError(0, "network", "Connection lost", "The upload was interrupted. Check your connection and try again."));
    xhr.onabort = () => reject(new DOMException("Upload cancelled", "AbortError"));
    signal?.addEventListener("abort", () => xhr.abort(), { once: true });
    xhr.send(form);
  });
}

/**
 * Fetches a file the server generates (exports, snapshots) and hands it to the
 * browser's download manager under the server's file name. Fetching first,
 * rather than following a link, lets the console show progress and report
 * failures in place.
 */
export async function download(path: string, query?: Query): Promise<string> {
  let response: Response;
  try {
    response = await fetch(url(path, query), { credentials: "same-origin", headers: { "X-Falcon-Request": "1" } });
  } catch {
    throw new ApiError(0, "network", "Connection lost", "FALCON could not be reached. Check your connection and try again.");
  }
  if (!response.ok) {
    const error = toApiError(response.status, response.statusText, await response.text());
    if (response.status === 401) unauthenticatedListeners.forEach((l) => l(error));
    throw error;
  }
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const filename = /filename="([^"]+)"/.exec(disposition)?.[1] ?? "falcon-report";
  const href = URL.createObjectURL(await response.blob());
  const anchor = Object.assign(document.createElement("a"), { href, download: filename, rel: "noopener" });
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(href), 30_000);
  return filename;
}

export const api = {
  get: <T>(path: string, query?: Query, signal?: AbortSignal) => request<T>("GET", path, undefined, query, signal),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body ?? {}),
  put: <T>(path: string, body: unknown) => request<T>("PUT", path, body),
  patch: <T>(path: string, body: unknown) => request<T>("PATCH", path, body),
  delete: <T = void>(path: string) => request<T>("DELETE", path),
};
