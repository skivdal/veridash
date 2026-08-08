import type { ProblemResponse } from "./generated/schemas";

export class ApiError<TProblem = ProblemResponse> extends Error {
  readonly status: number;
  readonly problem: TProblem | undefined;

  constructor(status: number, problem: TProblem | undefined) {
    super(
      isProblemResponse(problem)
        ? problem.detail
        : `The server returned HTTP ${status}.`,
    );
    this.name = "ApiError";
    this.status = status;
    this.problem = problem;
  }
}

export type ErrorType<TProblem> = ApiError<TProblem>;
export type BodyType<TBody> = TBody;

const unsafeMethods = new Set(["POST", "PUT", "PATCH", "DELETE"]);

export function readCookie(name: string): string | undefined {
  const prefix = `${encodeURIComponent(name)}=`;
  const item = document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(prefix));

  return item === undefined
    ? undefined
    : decodeURIComponent(item.slice(prefix.length));
}

function isProblemResponse(value: unknown): value is ProblemResponse {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Partial<ProblemResponse>;
  return (
    typeof candidate.status === "number" &&
    typeof candidate.code === "string" &&
    typeof candidate.detail === "string"
  );
}

async function parseResponse(response: Response): Promise<unknown> {
  if ([204, 205, 304].includes(response.status)) return undefined;
  const contentType = response.headers.get("Content-Type")?.toLowerCase() ?? "";
  if (response.ok && !contentType.includes("json")) return response.blob();

  const body = await response.text();
  if (body.length === 0) return undefined;

  try {
    return JSON.parse(body) as unknown;
  } catch {
    return undefined;
  }
}

export async function apiFetch<T>(
  url: string,
  options: RequestInit,
): Promise<T> {
  const headers = new Headers(options.headers);
  const method = options.method?.toUpperCase() ?? "GET";
  if (unsafeMethods.has(method) && !headers.has("X-CSRF-Token")) {
    const csrfToken = readCookie("veridash_csrf");
    if (csrfToken !== undefined) headers.set("X-CSRF-Token", csrfToken);
  }

  const response = await fetch(url, {
    ...options,
    credentials: "same-origin",
    headers,
  });
  const body = await parseResponse(response);
  if (!response.ok) {
    throw new ApiError(response.status, body as ProblemResponse | undefined);
  }
  return {
    data: body,
    status: response.status,
    headers: response.headers,
  } as T;
}
