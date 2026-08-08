import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ApiError } from "../../api/fetcher";
import {
  getGetDashboardPreferenceApiPreferencesDashboardGetQueryKey,
  useSaveDashboardPreferenceApiPreferencesDashboardPut,
} from "../../api/generated/client";
import type { DashboardPreferenceResponse } from "../../api/generated/schemas";

export const dashboardModules = [
  { id: "source", label: "Source", target: "source-media" },
  { id: "frames", label: "Frames", target: "frames" },
  {
    id: "transcription",
    label: "Transcription & Translation",
    target: "transcribe",
  },
  { id: "detection", label: "Object Detection", target: "detect_objects" },
  { id: "metadata", label: "Metadata", target: "metadata" },
  { id: "map", label: "Map", target: "map" },
  { id: "notes", label: "Notes", target: "notes" },
  { id: "activity", label: "Activity log", target: "activity" },
] as const;

export type DashboardModuleId = (typeof dashboardModules)[number]["id"];

const moduleIds = new Set<string>(dashboardModules.map((module) => module.id));

export function normalizedModuleOrder(
  order: string[] | undefined,
): DashboardModuleId[] {
  if (
    order?.length === dashboardModules.length &&
    new Set(order).size === dashboardModules.length &&
    order.every((moduleId) => moduleIds.has(moduleId))
  ) {
    return order as DashboardModuleId[];
  }
  const legacyModuleIds = dashboardModules.filter(
    (module) => module.id !== "activity",
  );
  if (
    order?.length === legacyModuleIds.length &&
    new Set(order).size === legacyModuleIds.length &&
    order.every(
      (moduleId) => moduleId !== "activity" && moduleIds.has(moduleId),
    )
  ) {
    return [...(order as DashboardModuleId[]), "activity"];
  }
  return dashboardModules.map((module) => module.id);
}

export function DashboardCustomizer({
  preference,
  loadError,
  onClose,
}: {
  preference: DashboardPreferenceResponse | undefined;
  loadError: string | undefined;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [order, setOrder] = useState<DashboardModuleId[]>(() =>
    normalizedModuleOrder(preference?.module_order),
  );
  const [hidden, setHidden] = useState<Set<DashboardModuleId>>(
    () =>
      new Set(
        preference?.hidden_modules.filter((moduleId) =>
          moduleIds.has(moduleId),
        ) as DashboardModuleId[] | undefined,
      ),
  );
  const save = useSaveDashboardPreferenceApiPreferencesDashboardPut({
    mutation: {
      onSuccess: (response) => {
        if (response.status !== 200) return;
        queryClient.setQueryData(
          getGetDashboardPreferenceApiPreferencesDashboardGetQueryKey(),
          response,
        );
        onClose();
      },
    },
  });
  const saveError =
    save.error instanceof ApiError ? save.error.message : undefined;

  function move(index: number, offset: -1 | 1) {
    const destination = index + offset;
    if (destination < 0 || destination >= order.length) return;
    setOrder((current) => {
      const next = [...current];
      const moving = next[index];
      const displaced = next[destination];
      if (moving === undefined || displaced === undefined) return current;
      next[index] = displaced;
      next[destination] = moving;
      return next;
    });
  }

  function toggle(moduleId: DashboardModuleId) {
    setHidden((current) => {
      const next = new Set(current);
      if (next.has(moduleId)) next.delete(moduleId);
      else next.add(moduleId);
      return next;
    });
  }

  return (
    <section
      className="customize-dashboard"
      aria-labelledby="customize-heading"
    >
      <div className="customize-heading">
        <div>
          <p className="card-eyebrow">Saved for your account</p>
          <h2 id="customize-heading">Customize dashboard</h2>
          <p>
            Choose which cards are visible and arrange them. Analyses continue
            independently of this layout.
          </p>
        </div>
        <button className="button button-quiet" type="button" onClick={onClose}>
          Close
        </button>
      </div>
      <ol className="customize-module-list">
        {order.map((moduleId, index) => {
          const definition = dashboardModules.find(
            (module) => module.id === moduleId,
          );
          if (definition === undefined) return null;
          return (
            <li key={moduleId}>
              <label>
                <input
                  type="checkbox"
                  checked={!hidden.has(moduleId)}
                  onChange={() => toggle(moduleId)}
                />
                Show {definition.label}
              </label>
              <div className="customize-order-actions">
                <button
                  className="button button-quiet"
                  type="button"
                  disabled={index === 0}
                  aria-label={`Move ${definition.label} earlier`}
                  onClick={() => move(index, -1)}
                >
                  ←
                </button>
                <button
                  className="button button-quiet"
                  type="button"
                  disabled={index === order.length - 1}
                  aria-label={`Move ${definition.label} later`}
                  onClick={() => move(index, 1)}
                >
                  →
                </button>
              </div>
            </li>
          );
        })}
      </ol>
      {loadError === undefined && saveError === undefined ? null : (
        <p className="form-error" role="alert">
          {saveError ?? loadError}
        </p>
      )}
      <div className="customize-footer">
        <button
          className="button button-secondary"
          type="button"
          onClick={() => {
            setOrder(dashboardModules.map((module) => module.id));
            setHidden(new Set());
          }}
        >
          Reset layout
        </button>
        <button
          className="button button-primary"
          type="button"
          disabled={preference === undefined || save.isPending}
          onClick={() =>
            save.mutate({
              data: {
                module_order: order,
                hidden_modules: order.filter((moduleId) =>
                  hidden.has(moduleId),
                ),
                expected_revision: preference?.revision ?? 0,
              },
            })
          }
        >
          {save.isPending ? "Saving…" : "Save dashboard"}
        </button>
      </div>
    </section>
  );
}
