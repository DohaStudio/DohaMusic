import { AppShell } from "@/components/app-shell";
import { StudioWorkspace } from "@/features/studio/studio-workspace";
import { StudioHelp } from "@/features/studio/studio-help";
export default function StudioPage() {
  return (
    <AppShell
      context={<StudioHelp />}
    >
      <StudioWorkspace />
    </AppShell>
  );
}
