"use client";

import { useEffect, useRef } from "react";
import { Button } from "@/components/ui";

export function CancelDialog({ open, pending, onClose, onConfirm }: { open: boolean; pending: boolean; onClose: () => void; onConfirm: () => void }) {
  const dialog = useRef<HTMLDivElement>(null);
  useEffect(() => { if (open) dialog.current?.querySelector<HTMLButtonElement>("button")?.focus(); }, [open]);
  if (!open) return null;
  function onKeyDown(event: React.KeyboardEvent) {
    if (event.key === "Escape" && !pending) { onClose(); return; }
    if (event.key !== "Tab") return;
    const items = dialog.current?.querySelectorAll<HTMLElement>("button:not([disabled])");
    if (!items?.length) return;
    const first = items[0]; const last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  }
  return <div className="modal-backdrop" role="presentation"><div ref={dialog} className="onboarding-dialog" role="dialog" aria-modal="true" aria-labelledby="cancel-title" aria-describedby="cancel-description" aria-busy={pending} onKeyDown={onKeyDown}><h2 id="cancel-title">음악 만들기를 취소할까요?</h2><p id="cancel-description">현재 처리 중인 단계가 정리된 뒤 취소될 수 있습니다. 취소된 작업은 만든 음악에서 다시 확인할 수 있습니다.</p><div className="actions"><Button className="secondary" disabled={pending} onClick={onClose}>계속 만들기</Button><Button className="danger" disabled={pending} onClick={onConfirm}>{pending ? "취소 요청 중" : "취소하기"}</Button></div></div></div>;
}
