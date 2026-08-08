import { ApiError, readCookie } from "../../api/fetcher";
import type {
  ProblemResponse,
  SourceMediaResponse,
} from "../../api/generated/schemas";

export interface UploadProgress {
  loadedBytes: number;
  totalBytes: number | undefined;
}

/**
 * Upload a file with XMLHttpRequest because Fetch does not expose browser upload
 * progress. Reservation and completion still use the generated API client.
 */
export function uploadSourceMedia(
  mediaId: string,
  file: File,
  onProgress: (progress: UploadProgress) => void,
  signal?: AbortSignal,
): Promise<SourceMediaResponse> {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    const abortRequest = () => request.abort();

    const finish = (callback: () => void) => {
      signal?.removeEventListener("abort", abortRequest);
      callback();
    };

    request.open("PUT", `/api/uploads/${encodeURIComponent(mediaId)}/content`);
    request.withCredentials = true;
    request.setRequestHeader(
      "Content-Type",
      file.type || "application/octet-stream",
    );
    const csrfToken = readCookie("veridash_csrf");
    if (csrfToken !== undefined) {
      request.setRequestHeader("X-CSRF-Token", csrfToken);
    }

    request.upload.addEventListener("progress", (event) => {
      onProgress({
        loadedBytes: event.loaded,
        totalBytes: event.lengthComputable ? event.total : undefined,
      });
    });
    request.addEventListener("load", () => {
      const body = parseJson(request.responseText);
      if (request.status >= 200 && request.status < 300) {
        finish(() => resolve(body as SourceMediaResponse));
        return;
      }
      finish(() =>
        reject(
          new ApiError(
            request.status,
            isProblemResponse(body) ? body : undefined,
          ),
        ),
      );
    });
    request.addEventListener("error", () => {
      finish(() => reject(new Error("The video upload lost its connection.")));
    });
    request.addEventListener("abort", () => {
      finish(() =>
        reject(new DOMException("The upload was cancelled.", "AbortError")),
      );
    });

    if (signal?.aborted) {
      reject(new DOMException("The upload was cancelled.", "AbortError"));
      return;
    }
    signal?.addEventListener("abort", abortRequest, { once: true });
    request.send(file);
  });
}

function parseJson(value: string): unknown {
  if (value.length === 0) return undefined;
  try {
    return JSON.parse(value) as unknown;
  } catch {
    return undefined;
  }
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
