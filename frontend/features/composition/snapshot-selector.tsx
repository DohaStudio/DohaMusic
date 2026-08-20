import { Button, ErrorAlert } from "@/components/ui";
import type { CompositionSnapshotSummaryDto } from "@/types/api";

export function SnapshotSelector({
  snapshots,
  selectedId,
  isSubmitting,
  error,
  onSelect,
  onApply,
}: {
  snapshots: CompositionSnapshotSummaryDto[];
  selectedId: string | null;
  isSubmitting: boolean;
  error?: string;
  onSelect: (snapshotId: string) => void;
  onApply: () => void;
}) {
  return (
    <div className="composition-selector">
      <div>
        <p className="eyebrow">SELECTION REQUIRED</p>
        <h3>열 Snapshot을 직접 선택해 주세요.</h3>
        <p>
          최신 항목을 자동으로 선택하지 않습니다. 선택을 적용해야 현재
          Composition이 바뀝니다.
        </p>
      </div>
      {error && <ErrorAlert title="Snapshot을 선택하지 못했습니다" message={error} />}
      <fieldset className="snapshot-options" disabled={isSubmitting}>
        <legend>Composition Snapshot</legend>
        {snapshots.map((snapshot) => {
          const id = snapshot.composition_snapshot_id;
          return (
            <label key={id} className={selectedId === id ? "selected" : ""}>
              <input
                type="radio"
                name="composition-snapshot"
                value={id}
                checked={selectedId === id}
                onChange={() => onSelect(id)}
              />
              <span>
                <strong>Snapshot v{snapshot.snapshot_version}</strong>
                <small>{new Date(snapshot.created_at).toLocaleString("ko-KR")}</small>
                <code>{id}</code>
              </span>
            </label>
          );
        })}
      </fieldset>
      <div className="composition-actions">
        <span role="status" aria-live="polite">
          {isSubmitting
            ? "선택을 적용하는 중입니다."
            : selectedId
              ? "적용할 Snapshot을 확인했습니다."
              : "현재 선택 없음"}
        </span>
        <Button type="button" disabled={!selectedId || isSubmitting} onClick={onApply}>
          {isSubmitting ? "적용 중…" : "선택 적용"}
        </Button>
      </div>
    </div>
  );
}
