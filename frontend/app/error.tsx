"use client";
import { Button } from "@/components/ui";
export default function ErrorPage({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="not-found" id="main-content">
      <p className="eyebrow">STUDIO ERROR</p>
      <h1>화면을 불러오지 못했습니다.</h1>
      <p>입력 draft는 이 session에 남아 있습니다.</p>
      <Button onClick={reset}>다시 시도</Button>
    </main>
  );
}
