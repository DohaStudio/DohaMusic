import { Badge } from "@/components/ui";
import { toBackendPublicUrl } from "@/services/doha-api";
import type {
  CompositionArtifactDto,
  CompositionReadItemDto,
  CompositionWorkspaceDto,
} from "@/types/api";

const roleLabels = {
  music: "Music",
  vocal: "Vocal",
  stem: "Stem",
  mix: "Mix",
} as const;

export function CompositionReadyView({ data }: { data: CompositionWorkspaceDto }) {
  const snapshot = data.snapshot;
  if (!snapshot) return null;

  const itemsById = new Map(data.items.map((item) => [item.snapshot_item_id, item]));

  return (
    <div className="composition-ready">
      <div className="composition-summary">
        <div>
          <p className="eyebrow">READY</p>
          <h3>Snapshot v{snapshot.snapshot_version}</h3>
          <p>선택된 불변 Snapshot의 exact AssetVersion을 표시합니다.</p>
        </div>
        <Badge tone="success">현재 선택</Badge>
      </div>
      <dl className="composition-identity">
        <Meta label="Snapshot ID" value={snapshot.composition_snapshot_id} />
        <Meta label="생성 시각" value={new Date(snapshot.created_at).toLocaleString("ko-KR")} />
      </dl>

      <section aria-labelledby="composition-tracks-title">
        <div className="composition-section-heading">
          <div>
            <p className="eyebrow">READ PROJECTION</p>
            <h4 id="composition-tracks-title">Composition Workspace Track Projection</h4>
          </div>
          <span>{data.track_projections.length}개</span>
        </div>
        <div className="composition-track-list">
          {data.track_projections.map((track) => {
            const item = itemsById.get(track.snapshot_item_id);
            return (
              <article key={track.projection_id} className="composition-track">
                <header>
                  <div>
                    <Badge>{roleLabels[track.item_role]}</Badge>
                    <strong>Track projection {track.sort_order + 1}</strong>
                  </div>
                  <small>Snapshot-local identity</small>
                </header>
                <dl className="composition-identity">
                  <Meta label="Snapshot Item" value={track.snapshot_item_id} />
                  <Meta label="Asset" value={track.asset_id} />
                  <Meta label="exact AssetVersion" value={track.asset_version_id} />
                  {item && <Meta label="Version" value={`v${item.asset_version.version_number} · ${item.asset_version.version_origin}`} />}
                  {item?.asset_version.parent_asset_version_id && (
                    <Meta label="Parent AssetVersion" value={item.asset_version.parent_asset_version_id} />
                  )}
                  {item?.asset_version.provider_id && <Meta label="Provider" value={item.asset_version.provider_id} />}
                  {item?.asset_version.model_manifest_id && (
                    <Meta label="Model Manifest" value={item.asset_version.model_manifest_id} />
                  )}
                </dl>
                {item && <ArtifactList item={item} />}
              </article>
            );
          })}
        </div>
      </section>

      <div className="composition-detail-grid">
        <section className="composition-detail-card" aria-labelledby="composition-section-title">
          <p className="eyebrow">SECTION</p>
          <h4 id="composition-section-title">Section 정보 없음</h4>
          <p>현재 계약은 <code>{data.section_projection.availability}</code>이며 Section을 추측해 만들지 않습니다.</p>
        </section>
        <section className="composition-detail-card" aria-labelledby="composition-mix-title">
          <p className="eyebrow">MIX SNAPSHOT</p>
          <h4 id="composition-mix-title">현재 Mix state</h4>
          {Object.keys(data.mix_settings_snapshot).length ? (
            <pre>{JSON.stringify(data.mix_settings_snapshot, null, 2)}</pre>
          ) : (
            <p>저장된 Mix 설정이 없습니다.</p>
          )}
        </section>
        <section className="composition-detail-card" aria-labelledby="composition-lineage-title">
          <p className="eyebrow">LINEAGE</p>
          <h4 id="composition-lineage-title">생성 계보</h4>
          <dl className="composition-identity">
            <Meta label="Processing Chain" value={data.lineage.processing_chain_id ?? "없음"} />
            <Meta label="Provider versions" value={formatRecord(data.lineage.provider_versions)} />
            <Meta label="Model manifests" value={formatRecord(data.lineage.model_manifest_ids)} />
          </dl>
        </section>
      </div>
    </div>
  );
}

function ArtifactList({ item }: { item: CompositionReadItemDto }) {
  if (!item.artifacts.length) return <p className="composition-muted">연결된 Artifact metadata가 없습니다.</p>;
  return (
    <div className="composition-artifacts">
      <h5>Artifact</h5>
      {item.artifacts.map((artifact) => (
        <article key={artifact.artifact_id}>
          <dl className="composition-identity">
            <Meta label="종류" value={artifact.artifact_kind} />
            <Meta label="Media type" value={artifact.media_type} />
            <Meta label="크기" value={formatBytes(artifact.size_bytes)} />
            <Meta label="상태" value={artifact.retention_status} />
            <Meta label="Artifact ID" value={artifact.artifact_id} />
          </dl>
          <ArtifactActions artifact={artifact} />
        </article>
      ))}
    </div>
  );
}

function ArtifactActions({ artifact }: { artifact: CompositionArtifactDto }) {
  const contentUrl = toBackendPublicUrl(artifact.content_url);
  const downloadUrl = toBackendPublicUrl(artifact.download_url);
  if (!contentUrl && !downloadUrl) return null;
  return (
    <div className="composition-artifact-actions">
      {contentUrl && <a className="button secondary" href={contentUrl}>미리보기</a>}
      {downloadUrl && <a className="button secondary" href={downloadUrl}>다운로드</a>}
    </div>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return <div><dt>{label}</dt><dd>{value}</dd></div>;
}

function formatRecord(value: Record<string, string>): string {
  const entries = Object.entries(value);
  return entries.length ? entries.map(([key, item]) => `${key}: ${item}`).join(", ") : "없음";
}

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}
