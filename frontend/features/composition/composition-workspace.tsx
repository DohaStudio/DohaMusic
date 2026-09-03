"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { ErrorAlert } from "@/components/ui";
import { ApiError, userErrorMessage } from "@/services/api-client";
import { dohaApi } from "@/services/doha-api";
import { CompositionEmptyState } from "./composition-empty-state";
import { CompositionReadyView } from "./composition-ready-view";
import { SnapshotSelector } from "./snapshot-selector";

export function CompositionWorkspace({ projectId }: { projectId: string }) {
  const [candidateId, setCandidateId] = useState<string | null>(null);
  const composition = useQuery({
    queryKey: ["project-composition", projectId],
    queryFn: ({ signal }) => dohaApi.getProjectComposition(projectId, signal),
  });
  const snapshots = useQuery({
    queryKey: ["project-composition-snapshots", projectId],
    queryFn: ({ signal }) => dohaApi.listProjectCompositionSnapshots(projectId, signal),
    enabled: composition.data?.state === "selection_required",
  });
  const selection = useMutation({
    mutationFn: (snapshotId: string) => dohaApi.selectProjectComposition(projectId, snapshotId),
    onSuccess: async () => {
      setCandidateId(null);
      await composition.refetch();
    },
  });

  return (
    <section className="surface-card composition-workspace" aria-labelledby="composition-workspace-title">
      <header className="composition-workspace-heading">
        <div>
          <p className="eyebrow">DAW EDITOR</p>
          <h2 id="composition-workspace-title">곡 편집</h2>
        </div>
        <span>트랙과 클립을 편집하고 미리듣기와 버전을 관리합니다.</span>
      </header>
      {composition.isPending && <CompositionLoading />}
      {composition.error && (
        <ErrorAlert title="Composition을 불러오지 못했습니다" message={compositionErrorMessage(composition.error)} />
      )}
      {composition.data?.state === "empty" && <CompositionEmptyState />}
      {composition.data?.state === "selection_required" && (
        snapshots.isPending ? (
          <CompositionLoading label="Snapshot 목록을 불러오는 중" />
        ) : snapshots.error ? (
          <ErrorAlert title="Snapshot 목록을 불러오지 못했습니다" message={compositionErrorMessage(snapshots.error)} />
        ) : (
          <SnapshotSelector
            snapshots={snapshots.data ?? []}
            selectedId={candidateId}
            isSubmitting={selection.isPending}
            error={selection.error ? compositionErrorMessage(selection.error) : undefined}
            onSelect={(snapshotId) => {
              selection.reset();
              setCandidateId(snapshotId);
            }}
            onApply={() => {
              if (candidateId && !selection.isPending) selection.mutate(candidateId);
            }}
          />
        )
      )}
      {composition.data?.state === "ready" && <CompositionReadyView data={composition.data} />}
    </section>
  );
}

function CompositionLoading({ label = "Composition을 불러오는 중" }: { label?: string }) {
  return (
    <div className="composition-loading" role="status" aria-label={label}>
      <span />
      <span />
      <span />
    </div>
  );
}

function compositionErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.status === 401) return "로그인이 필요합니다. 다시 로그인해 주세요.";
  if (error instanceof ApiError && error.status === 403) return "이 Project에 접근할 권한이 없습니다.";
  if (
    error instanceof ApiError
    && [
      "NETWORK_ERROR",
      "REQUEST_TIMEOUT",
      "HTTP_ERROR",
      "PROJECT_NOT_FOUND",
      "COMPOSITION_SNAPSHOT_NOT_FOUND",
      "COMPOSITION_SNAPSHOT_CONFLICT",
      "WORKSPACE_BOOTSTRAP_REQUIRED",
    ].includes(error.code)
  ) {
    return userErrorMessage(error);
  }
  return "Composition 요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.";
}
