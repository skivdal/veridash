import { describe, expect, it, vi } from "vitest";

import { connectProjectEvents } from "./projectEvents";

class FakeEventSource {
  readonly listeners = new Map<string, EventListener>();
  closed = false;

  addEventListener(type: string, listener: EventListenerOrEventListenerObject) {
    if (typeof listener === "function") this.listeners.set(type, listener);
  }

  close() {
    this.closed = true;
  }

  emit(type: string, data = "") {
    this.listeners.get(type)?.(new MessageEvent(type, { data }));
  }
}

describe("project event stream", () => {
  it("connects to the encoded project and forwards durable event types", () => {
    const source = new FakeEventSource();
    const onEvent = vi.fn();
    const disconnect = connectProjectEvents("project/id", onEvent, (url) => {
      expect(url).toBe("/api/projects/project%2Fid/events");
      return source as unknown as EventSource;
    });

    source.emit("project-sync");
    source.emit("project-event", '{"event_type":"job.progress"}');
    source.emit("project-event", "invalid-json");
    disconnect();

    expect(onEvent.mock.calls).toEqual([
      [undefined],
      ["job.progress"],
      [undefined],
    ]);
    expect(source.closed).toBe(true);
  });
});
