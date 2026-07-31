import { AppShell } from "@/components/app-shell";
import { Vinyl } from "@/components/brand";
import { StudioWorkspace } from "@/features/studio/studio-workspace";
export default function StudioPage() {
  return (
    <AppShell
      context={
        <div className="studio-context">
          <Vinyl small />
          <p className="eyebrow">DOHA STUDIO</p>
          <h2>한 번에 한 단계씩</h2>
          <p>
            입력은 임시 draft로만 sessionStorage에 보존됩니다. 서버 상태는 API가
            진실의 원천입니다.
          </p>
          <dl>
            <div>
              <dt>현재 Provider</dt>
              <dd>Backend metadata</dd>
            </div>
            <div>
              <dt>Audio</dt>
              <dd>Metadata only</dd>
            </div>
          </dl>
        </div>
      }
    >
      <StudioWorkspace />
    </AppShell>
  );
}
