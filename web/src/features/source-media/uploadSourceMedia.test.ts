import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApiError } from "../../api/fetcher";
import { uploadSourceMedia } from "./uploadSourceMedia";

type Listener = (event: ProgressEvent) => void;

class FakeEventTarget {
  readonly listeners = new Map<string, Listener>();

  addEventListener(name: string, listener: Listener) {
    this.listeners.set(name, listener);
  }

  emit(name: string, event = new ProgressEvent(name)) {
    this.listeners.get(name)?.(event);
  }
}

class FakeXMLHttpRequest extends FakeEventTarget {
  static latest: FakeXMLHttpRequest | undefined;

  readonly headers = new Headers();
  readonly upload = new FakeEventTarget();
  method = "";
  url = "";
  withCredentials = false;
  status = 0;
  responseText = "";
  body: Document | XMLHttpRequestBodyInit | null = null;

  constructor() {
    super();
    FakeXMLHttpRequest.latest = this;
  }

  open(method: string, url: string) {
    this.method = method;
    this.url = url;
  }

  setRequestHeader(name: string, value: string) {
    this.headers.set(name, value);
  }

  send(body: Document | XMLHttpRequestBodyInit | null) {
    this.body = body;
  }

  abort() {
    this.emit("abort");
  }
}

afterEach(() => {
  vi.unstubAllGlobals();
  FakeXMLHttpRequest.latest = undefined;
  // biome-ignore lint/suspicious/noDocumentCookie: jsdom does not implement Cookie Store API.
  document.cookie = "veridash_csrf=; Max-Age=0; path=/";
});

describe("uploadSourceMedia", () => {
  it("sends CSRF credentials and reports byte progress", async () => {
    // biome-ignore lint/suspicious/noDocumentCookie: jsdom does not implement Cookie Store API.
    document.cookie = "veridash_csrf=upload-token; path=/";
    vi.stubGlobal("XMLHttpRequest", FakeXMLHttpRequest);
    const onProgress = vi.fn();
    const file = new File(["video bytes"], "source.mp4", {
      type: "video/mp4",
    });

    const result = uploadSourceMedia("media-id", file, onProgress);
    const request = FakeXMLHttpRequest.latest;
    expect(request).toBeDefined();
    expect(request?.method).toBe("PUT");
    expect(request?.url).toBe("/api/uploads/media-id/content");
    expect(request?.withCredentials).toBe(true);
    expect(request?.headers.get("X-CSRF-Token")).toBe("upload-token");
    expect(request?.headers.get("Content-Type")).toBe("video/mp4");
    expect(request?.body).toBe(file);

    request?.upload.emit(
      "progress",
      new ProgressEvent("progress", {
        lengthComputable: true,
        loaded: 6,
        total: 12,
      }),
    );
    expect(onProgress).toHaveBeenCalledWith({
      loadedBytes: 6,
      totalBytes: 12,
    });

    if (request !== undefined) {
      request.status = 200;
      request.responseText = JSON.stringify({ id: "media-id" });
      request.emit("load");
    }
    await expect(result).resolves.toMatchObject({ id: "media-id" });
  });

  it("turns a server problem into an ApiError", async () => {
    vi.stubGlobal("XMLHttpRequest", FakeXMLHttpRequest);
    const result = uploadSourceMedia(
      "media-id",
      new File(["too large"], "source.mp4"),
      vi.fn(),
    );
    const request = FakeXMLHttpRequest.latest;
    if (request !== undefined) {
      request.status = 413;
      request.responseText = JSON.stringify({
        type: "urn:veridash:problem:upload_too_large",
        title: "Video is too large",
        status: 413,
        detail: "The source video exceeds the configured limit.",
        code: "upload_too_large",
      });
      request.emit("load");
    }

    await expect(result).rejects.toMatchObject({
      name: "ApiError",
      status: 413,
      message: "The source video exceeds the configured limit.",
    } satisfies Partial<ApiError>);
  });
});
