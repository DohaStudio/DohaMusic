"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AudioLines, Circle, Mic, Upload } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Badge, Button, ErrorAlert, Field, InfoCard, Input, Textarea } from "@/components/ui";
import { dohaApi } from "@/services/doha-api";
import { useStudioStore } from "@/stores/studio-store";
import type { VoiceEnrollmentSampleDto, VoiceEnrollmentStep } from "./voice-enrollment-types";
import {
  MAX_VOICE_SAMPLES,
  VOICE_CONSENT_POLICY_VERSION,
  VOICE_ENROLLMENT_SESSION_KEY,
} from "./voice-enrollment-types";
import {
  createIdempotencyKey,
  formatDuration,
  qualityWarningMessage,
  readEnrollmentSession,
  shouldClearEnrollmentSession,
  validateEnrollmentFile,
  validateRecordingDuration,
  voiceEnrollmentErrorMessage,
  writeEnrollmentSession,
} from "./voice-enrollment-utils";
import { useVoiceRecorder } from "./use-voice-recorder";
import {
  EnrollmentOperationProgress,
  EnrollmentSummary,
  VoiceAudioPlayer,
  VoiceSampleCard,
} from "./voice-enrollment-ui";

const STEPS: Array<{ id: VoiceEnrollmentStep; label: string }> = [
  { id: "guide", label: "안내" },
  { id: "consent", label: "동의" },
  { id: "method", label: "방법" },
  { id: "samples", label: "녹음·업로드" },
  { id: "quality", label: "품질 확인" },
  { id: "reference", label: "대표 선택" },
  { id: "review", label: "프로필 확인" },
  { id: "complete", label: "등록 완료" },
];

const PROMPTS = [
  { id: "ko_speech_neutral_01", category: "BASIC_SPEECH", title: "기본 말하기", text: "안녕하세요. 지금부터 제 목소리를 등록하기 위한 음성 녹음을 시작하겠습니다." },
  { id: "ko_speech_bright_01", category: "BRIGHT_SPEECH", title: "밝은 말하기", text: "오늘은 새로운 음악을 만들 생각에 기분이 좋습니다." },
  { id: "ko_speech_calm_01", category: "CALM_SPEECH", title: "차분한 말하기", text: "천천히 숨을 고르고 편안한 목소리로 이야기를 이어가겠습니다." },
  { id: "ko_song_original_01", category: "ACAPELLA_SINGING", title: "무반주 노래", text: "라라라, 오늘의 빛을 따라. 천천히 새로운 노래를 불러." },
] as const;

function sampleDisplayLabel(sample: VoiceEnrollmentSampleDto, index: number, displayNames: Record<string, string>) {
  return displayNames[sample.id]
    ?? PROMPTS.find((prompt) => prompt.id === sample.prompt_id)?.title
    ?? `Sample ${index + 1}`;
}

function previousStep(step: VoiceEnrollmentStep): VoiceEnrollmentStep {
  return STEPS[Math.max(0, STEPS.findIndex((item) => item.id === step) - 1)].id;
}

export function VoiceEnrollmentWizard() {
  const queryClient = useQueryClient();
  const patchStudio = useStudioStore((state) => state.patch);
  const [step, setStep] = useState<VoiceEnrollmentStep>("guide");
  const [enrollmentId, setEnrollmentId] = useState<string | undefined>(undefined);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [consents, setConsents] = useState([false, false, false, false]);
  const [method, setMethod] = useState<"record" | "upload">("record");
  const [promptIndex, setPromptIndex] = useState(0);
  const [referenceId, setReferenceId] = useState<string | undefined>(undefined);
  const [acknowledged, setAcknowledged] = useState<Set<string>>(new Set());
  const [displayNames, setDisplayNames] = useState<Record<string, string>>({});
  const [previewUrls, setPreviewUrls] = useState<Record<string, string>>({});
  const previewUrlsRef = useRef<Record<string, string>>({});
  const [clientError, setClientError] = useState<string | undefined>(undefined);
  const [restoring, setRestoring] = useState(true);
  const [lastFailedUpload, setLastFailedUpload] = useState<UploadInput | undefined>(undefined);
  const createKeyRef = useRef<string | undefined>(undefined);
  const createFingerprintRef = useRef<string | undefined>(undefined);
  const uploadKeysRef = useRef(new Map<string, string>());
  const submitKeyRef = useRef<string | undefined>(undefined);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const recorder = useVoiceRecorder();

  useEffect(() => {
    const restored = readEnrollmentSession(sessionStorage);
    queueMicrotask(() => {
      if (restored) {
        setEnrollmentId(restored.enrollmentId);
        setStep(restored.step);
      }
      setRestoring(false);
    });
  }, []);

  const enrollment = useQuery({
    queryKey: ["voice-enrollment", enrollmentId],
    queryFn: ({ signal }) => dohaApi.getVoiceEnrollment(enrollmentId!, signal),
    enabled: Boolean(enrollmentId) && !restoring,
    retry: false,
  });

  useEffect(() => {
    const data = enrollment.data;
    if (!data) return;
    queueMicrotask(() => {
      if (data.status === "COMPLETED" && data.voice_profile_id) {
        patchStudio({ voiceProfileId: data.voice_profile_id, voiceProfileName: data.name });
        setStep("complete");
        sessionStorage.removeItem(VOICE_ENROLLMENT_SESSION_KEY);
      }
      if (["CANCELLED", "EXPIRED"].includes(data.status)) {
        sessionStorage.removeItem(VOICE_ENROLLMENT_SESSION_KEY);
        setEnrollmentId(undefined);
      }
    });
  }, [enrollment.data, patchStudio]);

  useEffect(() => {
    if (enrollment.error && shouldClearEnrollmentSession(enrollment.error)) {
      sessionStorage.removeItem(VOICE_ENROLLMENT_SESSION_KEY);
      const message = voiceEnrollmentErrorMessage(enrollment.error);
      queueMicrotask(() => {
        setEnrollmentId(undefined);
        setStep("guide");
        setClientError(message);
      });
    }
  }, [enrollment.error]);

  useEffect(() => {
    if (enrollmentId && step !== "complete") {
      writeEnrollmentSession(sessionStorage, { enrollmentId, step });
    }
    headingRef.current?.focus();
  }, [enrollmentId, step]);

  const shouldGuard = recorder.status === "RECORDING" || recorder.status === "PAUSED" || Boolean(recorder.recording)
    || enrollment.isFetching;
  useEffect(() => {
    if (!shouldGuard) return;
    const protect = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", protect);
    return () => window.removeEventListener("beforeunload", protect);
  }, [shouldGuard]);

  useEffect(() => { previewUrlsRef.current = previewUrls; }, [previewUrls]);
  useEffect(() => () => {
    Object.values(previewUrlsRef.current).forEach((url) => URL.revokeObjectURL(url));
  }, []);

  const create = useMutation({
    mutationFn: async () => {
      const fingerprint = JSON.stringify({ name: name.trim(), description: description.trim() });
      if (createFingerprintRef.current !== fingerprint) {
        createKeyRef.current = createIdempotencyKey();
        createFingerprintRef.current = fingerprint;
      }
      return dohaApi.createVoiceEnrollment({
        name: name.trim(),
        description: description.trim() || null,
        consent_confirmed: true,
        consent_policy_version: VOICE_CONSENT_POLICY_VERSION,
      }, createKeyRef.current!);
    },
    onSuccess: (data) => {
      createKeyRef.current = undefined;
      createFingerprintRef.current = undefined;
      setEnrollmentId(data.id);
      queryClient.setQueryData(["voice-enrollment", data.id], data);
      setStep("samples");
    },
  });

  type UploadMutationInput = UploadInput;
  const upload = useMutation({
    mutationFn: (input: UploadMutationInput) => {
      let key = uploadKeysRef.current.get(input.localId);
      if (!key) {
        key = createIdempotencyKey();
        uploadKeysRef.current.set(input.localId, key);
      }
      return dohaApi.uploadVoiceEnrollmentSample({
        enrollmentId: enrollmentId!, file: input.file, sourceType: input.sourceType,
        category: input.category, promptId: input.promptId, idempotencyKey: key,
      });
    },
    onSuccess: async (sample, input) => {
      uploadKeysRef.current.delete(input.localId);
      setLastFailedUpload(undefined);
      if (input.displayName) setDisplayNames((current) => ({ ...current, [sample.id]: input.displayName! }));
      const retainedPreviewUrl = URL.createObjectURL(input.file);
      setPreviewUrls((current) => ({ ...current, [sample.id]: retainedPreviewUrl }));
      recorder.reset();
      await queryClient.invalidateQueries({ queryKey: ["voice-enrollment", enrollmentId] });
    },
    onError: (_error, input) => setLastFailedUpload(input),
  });

  const remove = useMutation({
    mutationFn: (sampleId: string) => dohaApi.deleteVoiceEnrollmentSample(enrollmentId!, sampleId),
    onSuccess: async (_data, sampleId) => {
      const previewUrl = previewUrls[sampleId];
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      setPreviewUrls((current) => { const next = { ...current }; delete next[sampleId]; return next; });
      await queryClient.invalidateQueries({ queryKey: ["voice-enrollment", enrollmentId] });
    },
  });

  const submit = useMutation({
    mutationFn: () => {
      submitKeyRef.current ??= createIdempotencyKey();
      const eligible = enrollment.data!.samples.filter((sample) => sample.submit_eligible);
      return dohaApi.submitVoiceEnrollment(enrollmentId!, {
        active_reference_sample_id: referenceId!,
        included_sample_ids: eligible.map((sample) => sample.id),
        acknowledged_warning_codes: eligible
          .filter((sample) => sample.quality.status === "WARNING" && acknowledged.has(sample.id))
          .map((sample) => ({ sample_id: sample.id, codes: sample.quality.warnings })),
        consent_confirmed: true,
        consent_policy_version: VOICE_CONSENT_POLICY_VERSION,
      }, submitKeyRef.current);
    },
    onSuccess: async (data) => {
      submitKeyRef.current = undefined;
      sessionStorage.removeItem(VOICE_ENROLLMENT_SESSION_KEY);
      recorder.stopStream();
      setEnrollmentId(data.id);
      queryClient.setQueryData(["voice-enrollment", data.id], data);
      if (data.voice_profile_id) patchStudio({ voiceProfileId: data.voice_profile_id, voiceProfileName: data.name });
      await queryClient.invalidateQueries({ queryKey: ["voice-profiles"] });
      setStep("complete");
    },
  });

  const cancelEnrollment = useMutation({
    mutationFn: () => dohaApi.cancelVoiceEnrollment(enrollmentId!),
    onSuccess: (data) => {
      sessionStorage.removeItem(VOICE_ENROLLMENT_SESSION_KEY);
      recorder.cancel();
      recorder.stopStream();
      setEnrollmentId(undefined);
      setStep("guide");
      setReferenceId(undefined);
      setAcknowledged(new Set());
      if (data.cleanup_status === "FAILED") setClientError("등록은 취소됐지만 임시 음성 파일 정리에 실패했습니다. 서버 상태를 확인해 주세요.");
      else if (data.cleanup_status === "PENDING") setClientError("등록은 취소됐고 임시 음성 파일을 삭제하는 중입니다.");
    },
  });

  const error = clientError || [create.error, upload.error, remove.error, submit.error, cancelEnrollment.error, enrollment.error]
    .find(Boolean);
  const errorMessage = typeof error === "string" ? error : error ? voiceEnrollmentErrorMessage(error) : undefined;
  const samples = enrollment.data?.samples.filter((sample) => !["DELETED"].includes(sample.status)) ?? [];
  const warningUnacknowledged = samples.some((sample) => sample.quality.status === "WARNING" && !acknowledged.has(sample.id));
  const selectedReference = samples.find((sample) => sample.id === referenceId);
  const canSubmit = Boolean(enrollment.data?.can_submit && selectedReference?.submit_eligible && !warningUnacknowledged);
  const completedReference = selectedReference
    ?? samples.find((sample) => sample.status === "PROMOTED")
    ?? samples.find((sample) => sample.submit_eligible);
  const currentStepIndex = STEPS.findIndex((item) => item.id === step);
  const operation = create.isPending
    ? { label: "등록 공간을 준비하고 있습니다…", value: 25 }
    : upload.isPending
      ? { label: "음성을 업로드하고 품질을 분석하고 있습니다…", value: 65 }
      : remove.isPending
        ? { label: "Sample을 안전하게 삭제하고 있습니다…", value: 70 }
        : submit.isPending
          ? { label: "Voice Profile을 만들고 있습니다…", value: 85 }
          : cancelEnrollment.isPending
            ? { label: "등록을 취소하고 임시 파일을 정리하고 있습니다…", value: 70 }
            : undefined;

  const changeStep = (target: VoiceEnrollmentStep) => {
    setClientError(undefined);
    setStep(target);
  };
  const startNew = () => {
    sessionStorage.removeItem(VOICE_ENROLLMENT_SESSION_KEY);
    setEnrollmentId(undefined);
    setStep("guide");
    setName(""); setDescription(""); setConsents([false, false, false, false]);
    setReferenceId(undefined); setAcknowledged(new Set()); setClientError(undefined);
  };

  if (restoring || (enrollmentId && enrollment.isPending)) {
    return <section className="surface-card enrollment-wizard enrollment-loading" aria-busy="true"><div className="skeleton-heading" aria-hidden="true" /><div className="skeleton-stepper" aria-hidden="true" /><EnrollmentOperationProgress label="진행 중인 음성 등록을 확인하고 있습니다…" value={35} /></section>;
  }

  return (
    <section className="surface-card enrollment-wizard" aria-labelledby="voice-enrollment-heading">
      <div className="enrollment-wizard-header">
        <div><p className="eyebrow">Guided Voice Enrollment</p><h2 id="voice-enrollment-heading">안내형 목소리 등록</h2></div>
        {enrollmentId && step !== "complete" && <Button className="danger" type="button" disabled={cancelEnrollment.isPending} onClick={() => {
          if (window.confirm("등록을 취소하면 아직 제출하지 않은 음성 Sample이 삭제됩니다.")) cancelEnrollment.mutate();
        }}>등록 취소</Button>}
      </div>
      <div className="enrollment-step-progress" aria-live="polite">
        <span>{currentStepIndex + 1} / {STEPS.length}</span>
        <strong>{STEPS[currentStepIndex]?.label}</strong>
      </div>
      <ol className="enrollment-stepper" aria-label="음성 등록 단계">
        {STEPS.map((item, index) => <li key={item.id} aria-current={item.id === step ? "step" : undefined} className={item.id === step ? "current" : ""}><span>{index + 1}</span>{item.label}</li>)}
      </ol>
      {errorMessage ? <ErrorAlert title="음성 등록을 계속할 수 없습니다" message={errorMessage} /> : <InfoCard title="녹음 형식 안내"><p>브라우저 녹음은 서버 환경에 따라 지원되지 않을 수 있습니다. <strong>WAV 파일 업로드는 언제든 사용할 수 있으며</strong>, FFmpeg가 없는 환경에서만 WebM·Ogg 처리가 제한됩니다.</p></InfoCard>}
      {operation && <EnrollmentOperationProgress label={operation.label} value={operation.value} />}
      <div className="enrollment-step" aria-busy={Boolean(operation)}>
        <h3 ref={headingRef} tabIndex={-1}>{STEPS.find((item) => item.id === step)?.label}</h3>
        {step === "guide" && <GuideStep />}
        {step === "consent" && <ConsentStep values={consents} onChange={setConsents} />}
        {step === "method" && <MethodStep name={name} description={description} method={method} onName={setName} onDescription={setDescription} onMethod={setMethod} />}
        {step === "samples" && enrollmentId && <SamplesStep recorder={recorder} samples={samples} method={method} promptIndex={promptIndex} onPromptIndex={setPromptIndex} uploading={upload.isPending} displayNames={displayNames} previewUrls={previewUrls} selectedId={referenceId} deletingId={remove.isPending ? remove.variables : undefined} onSelect={setReferenceId} onDelete={(sampleId) => remove.mutate(sampleId)} onUpload={(input) => upload.mutate(input)} onFiles={async (files) => {
          setClientError(undefined);
          let count = samples.length;
          for (const file of files) {
            const validation = validateEnrollmentFile(file);
            if (validation) { setClientError(`${file.name}: ${validation}`); continue; }
            if (count >= MAX_VOICE_SAMPLES) { setClientError("최대 10개의 음성 샘플만 등록할 수 있습니다."); break; }
            const localId = `${file.name}:${file.size}:${file.lastModified}`;
            try { await upload.mutateAsync({ localId, file, sourceType: "FILE_UPLOAD", category: "BASIC_SPEECH", displayName: file.name }); count += 1; }
            catch { break; }
          }
        }} />}
        {step === "quality" && <QualityStep samples={samples} acknowledged={acknowledged} onAcknowledge={(sampleId, checked) => setAcknowledged((current) => { const next = new Set(current); if (checked) next.add(sampleId); else next.delete(sampleId); return next; })} />}
        {step === "reference" && <ReferenceStep samples={samples} selectedId={referenceId} displayNames={displayNames} previewUrls={previewUrls} onSelect={setReferenceId} deletingId={remove.isPending ? remove.variables : undefined} onDelete={(sampleId) => remove.mutate(sampleId)} />}
        {step === "review" && enrollment.data && <ReviewStep name={enrollment.data.name} description={enrollment.data.description} samples={samples} selected={selectedReference} />}
        {step === "complete" && <CompleteStep name={enrollment.data?.name ?? name} sample={completedReference} sampleLabel={completedReference ? sampleDisplayLabel(completedReference, samples.indexOf(completedReference), displayNames) : undefined} previewUrl={completedReference ? previewUrls[completedReference.id] : undefined} onNew={startNew} />}
      </div>
      {lastFailedUpload && !upload.isPending && <div className="enrollment-retry"><p>같은 요청 키로 마지막 업로드를 다시 시도할 수 있습니다.</p><Button type="button" className="secondary" onClick={() => upload.mutate(lastFailedUpload)}>업로드 재시도</Button></div>}
      {step !== "complete" && <div className="enrollment-actions">
        {step !== "guide" && step !== "samples" && <Button type="button" className="secondary" disabled={create.isPending || upload.isPending || submit.isPending} onClick={() => changeStep(previousStep(step))}>이전</Button>}
        {step === "guide" && <Button type="button" onClick={() => changeStep("consent")}>등록 시작</Button>}
        {step === "consent" && <Button type="button" disabled={!consents.every(Boolean)} onClick={() => changeStep("method")}>동의하고 계속</Button>}
        {step === "method" && <Button type="button" disabled={!name.trim() || create.isPending} onClick={() => create.mutate()}>{create.isPending ? "등록 준비 중…" : "녹음·업로드 준비"}</Button>}
        {step === "samples" && <Button type="button" disabled={!samples.length || upload.isPending} onClick={() => changeStep("quality")}>품질 결과 확인</Button>}
        {step === "quality" && <Button type="button" disabled={!samples.some((sample) => sample.submit_eligible) || warningUnacknowledged} title={warningUnacknowledged ? "품질 경고를 확인해야 계속할 수 있습니다." : undefined} onClick={() => changeStep("reference")}>대표 Sample 선택</Button>}
        {step === "reference" && <Button type="button" disabled={!selectedReference?.submit_eligible} onClick={() => changeStep("review")}>프로필 확인</Button>}
        {step === "review" && <Button type="button" disabled={!canSubmit || submit.isPending} title={!canSubmit ? "대표 Sample과 품질 경고 확인이 필요합니다." : undefined} onClick={() => submit.mutate()}>{submit.isPending ? "Voice Profile 생성 중…" : "목소리 등록 완료"}</Button>}
      </div>}
    </section>
  );
}

interface UploadInput {
  localId: string;
  file: File | Blob;
  sourceType: "BROWSER_RECORDING" | "FILE_UPLOAD";
  category: string;
  promptId?: string;
  displayName?: string;
}

function GuideStep() {
  return <div className="guide-grid">
    <article><strong>권리와 개인정보</strong><p>본인 또는 사용 권리를 보유한 목소리만 등록할 수 있습니다. 다른 사람의 목소리가 포함되지 않게 해 주세요.</p></article>
    <article><strong>좋은 Sample</strong><p>조용한 장소에서 배경음악·반주·에코 없이 녹음하세요. WAV 파일을 우선 권장합니다.</p></article>
    <article><strong>등록 기준</strong><p>Sample당 5~60초, 최대 10개입니다. 완료 전 음성은 임시로 처리되며 취소·만료 시 삭제됩니다.</p></article>
    <article><strong>검사의 한계</strong><p>기본 파일·음향 검사는 Voice Provider 적합성이나 최종 변환 품질을 보장하지 않습니다.</p></article>
    <p className="muted full">브라우저가 WebM 또는 Ogg로 녹음하면 서버 환경에 따라 처리하지 못할 수 있습니다. 이 경우 권장 WAV 형식으로 다시 시도해 주세요.</p>
  </div>;
}

function ConsentStep({ values, onChange }: { values: boolean[]; onChange: (value: boolean[]) => void }) {
  const labels = [
    "본인의 목소리이거나 이 목적에 사용할 권리를 가진 음성임을 확인합니다.",
    "Voice Conversion용 참조 음성으로 처리되는 것에 동의합니다.",
    "등록 완료 전까지 원본과 정규화 음성이 임시 저장되는 것에 동의합니다.",
    "최종 제출 시 정규화된 대표 reference가 저장되는 것에 동의합니다.",
  ];
  return <div className="consent-list">{labels.map((label, index) => <label className="check" key={label}><input type="checkbox" checked={values[index]} onChange={(event) => { const next = [...values]; next[index] = event.target.checked; onChange(next); }} />{label}</label>)}<p className="muted">등록 음성은 Phase 7 Dataset이나 모델 학습에 자동 사용되지 않습니다. 현재 정책 버전: {VOICE_CONSENT_POLICY_VERSION}</p></div>;
}

function MethodStep({ name, description, method, onName, onDescription, onMethod }: { name: string; description: string; method: "record" | "upload"; onName: (value: string) => void; onDescription: (value: string) => void; onMethod: (value: "record" | "upload") => void }) {
  return <div className="studio-form"><Field label="목소리 이름" htmlFor="enrollment-name" hint="최종 제출 전에는 서버에서 이름을 수정할 수 없으므로 확인해 주세요."><Input id="enrollment-name" maxLength={100} required value={name} onChange={(event) => onName(event.target.value)} /></Field><Field label="설명 (선택)" htmlFor="enrollment-description"><Textarea id="enrollment-description" maxLength={500} value={description} onChange={(event) => onDescription(event.target.value)} /></Field><fieldset className="method-options"><legend>먼저 사용할 방법</legend><label className={method === "record" ? "selected" : ""}><input type="radio" name="voice-method" checked={method === "record"} onChange={() => onMethod("record")} /><strong>마이크로 직접 녹음</strong><span>안내 문장을 따라 5~60초 녹음합니다.</span></label><label className={method === "upload" ? "selected" : ""}><input type="radio" name="voice-method" checked={method === "upload"} onChange={() => onMethod("upload")} /><strong>기존 음성 파일 업로드</strong><span>WAV를 권장하며 WebM·Ogg도 선택할 수 있습니다.</span></label></fieldset><p className="muted">다음 단계에서 두 방식을 자유롭게 섞어 최대 10개 Sample을 추가할 수 있습니다.</p></div>;
}

function SamplesStep({ recorder, samples, method, promptIndex, onPromptIndex, uploading, displayNames, previewUrls, selectedId, deletingId, onSelect, onDelete, onUpload, onFiles }: { recorder: ReturnType<typeof useVoiceRecorder>; samples: VoiceEnrollmentSampleDto[]; method: "record" | "upload"; promptIndex: number; onPromptIndex: (index: number) => void; uploading: boolean; displayNames: Record<string, string>; previewUrls: Record<string, string>; selectedId?: string; deletingId?: string; onSelect: (id: string) => void; onDelete: (id: string) => void; onUpload: (input: UploadInput) => void; onFiles: (files: File[]) => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  const prompt = PROMPTS[promptIndex];
  const durationError = recorder.recording ? validateRecordingDuration(recorder.recording.durationSeconds) : undefined;
  const levelTone = recorder.level < 0.08 ? "warning" : recorder.level < 0.65 ? "success" : "danger";
  const levelText = recorder.level < 0.08 ? "작음" : recorder.level < 0.65 ? "적정" : "너무 큼";
  const selectedSample = samples.find((sample) => sample.id === selectedId);
  const uploadRecording = () => {
    if (!recorder.recording || durationError) return;
    onUpload({ localId: `recording:${Date.now()}`, file: recorder.recording.blob, sourceType: "BROWSER_RECORDING", category: prompt.category, promptId: prompt.id, displayName: `${prompt.title} 녹음` });
  };
  const statusText = recorder.status === "RECORDING" ? "녹음 중" : recorder.status === "PAUSED" ? "일시정지" : recorder.status === "PREVIEW" ? "미리 듣기" : recorder.status === "READY" ? "마이크 준비됨" : "마이크를 준비해 주세요";
  return <div className="sample-workspace">
    <div className="sample-main-column">
      <div className="recorder-panel">
        <div className="prompt-card"><div><span className="prompt-kicker">읽어주세요</span><Badge tone="neutral">{prompt.title}</Badge><p>{prompt.text}</p></div><select aria-label="안내 문장 선택" value={promptIndex} onChange={(event) => onPromptIndex(Number(event.target.value))}>{PROMPTS.map((item, index) => <option value={index} key={item.id}>{item.title}</option>)}</select></div>
        <div className={`recorder-status status-${recorder.status.toLowerCase()}`} aria-live="polite"><div><Circle aria-hidden="true" fill="currentColor" /><strong>{statusText}</strong><span>60초가 되면 자동으로 종료됩니다</span></div><time>{formatDuration(recorder.elapsedSeconds)} <small>/ 01:00</small></time></div>
        <div className="input-level-row"><span>마이크 입력 수준</span><Badge tone={levelTone}>{levelText}</Badge></div>
        <div className={`audio-level level-${levelTone}`} role="meter" aria-label={`마이크 입력 수준 ${levelText}`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(recorder.level * 100)}><span style={{ width: `${Math.round(recorder.level * 100)}%` }} /></div>
        {recorder.error && <ErrorAlert title="마이크를 사용할 수 없습니다" message={recorder.error} />}
        <div className="recorder-controls">{["IDLE", "FAILED"].includes(recorder.status) && <Button type="button" className="secondary" onClick={recorder.requestPermission}><Mic aria-hidden="true" /> 마이크 권한 요청</Button>}{recorder.status === "READY" && <Button type="button" onClick={recorder.start}><Circle aria-hidden="true" fill="currentColor" /> 녹음 시작</Button>}{recorder.status === "RECORDING" && <><Button type="button" className="secondary" onClick={recorder.pause}>일시정지</Button><Button type="button" onClick={recorder.stop}>녹음 종료</Button></>}{recorder.status === "PAUSED" && <><Button type="button" className="secondary" onClick={recorder.resume}>녹음 재개</Button><Button type="button" onClick={recorder.stop}>녹음 종료</Button></>}{recorder.status === "PREVIEW" && <><Button type="button" className="secondary" onClick={recorder.reset}>다시 녹음</Button><Button type="button" disabled={Boolean(durationError) || uploading} onClick={uploadRecording}>{uploading ? "업로드 중…" : "이 녹음 업로드"}</Button></>}</div>
        {recorder.recording && <div className="recorder-preview"><strong>방금 녹음한 Sample</strong><audio controls src={recorder.recording.previewUrl}>녹음 미리 듣기를 지원하지 않는 브라우저입니다.</audio></div>}
        {durationError && <p className="field-error" role="alert">{durationError}</p>}
      </div>
      <section className="sample-collection" aria-labelledby="sample-collection-heading">
        <div className="sample-collection-heading"><div><span className="eyebrow">My Samples</span><h4 id="sample-collection-heading">등록한 Sample</h4></div><Badge tone="neutral">{samples.length}개</Badge></div>
        {samples.length === 0 ? <div className="sample-empty"><AudioLines aria-hidden="true" /><strong>아직 등록된 Sample이 없습니다.</strong><p>녹음하거나 파일을 추가해 주세요.</p></div> : <div className="sample-card-grid">{samples.map((sample, index) => <VoiceSampleCard key={sample.id} sample={sample} label={sampleDisplayLabel(sample, index, displayNames)} previewUrl={previewUrls[sample.id]} selected={sample.id === selectedId} deleting={sample.id === deletingId} onSelect={() => onSelect(sample.id)} onDelete={() => { if (window.confirm("이 Sample을 삭제할까요?")) onDelete(sample.id); }} />)}</div>}
      </section>
    </div>
    <EnrollmentSummary samples={samples} selectedLabel={selectedSample ? sampleDisplayLabel(selectedSample, samples.indexOf(selectedSample), displayNames) : undefined} nextStep={samples.length ? "품질 결과 확인" : "Sample 추가"}>
      <div className={`file-drop${method === "upload" ? " preferred" : ""}`} onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); void onFiles(Array.from(event.dataTransfer.files)); }}><Upload aria-hidden="true" /><strong>기존 파일 추가</strong><p>WAV 권장 · WebM/Ogg 선택 가능<br />각 25MB 이하</p><input ref={inputRef} hidden type="file" multiple accept=".wav,.webm,.ogg,audio/wav,audio/webm,audio/ogg" onChange={(event) => void onFiles(Array.from(event.target.files ?? []))} /><Button type="button" className="secondary" disabled={uploading || samples.length >= MAX_VOICE_SAMPLES} onClick={() => inputRef.current?.click()}>파일 선택</Button><small className="sr-only">{samples.length}/{MAX_VOICE_SAMPLES} Sample</small></div>
    </EnrollmentSummary>
  </div>;
}

function QualityStep({ samples, acknowledged, onAcknowledge }: { samples: VoiceEnrollmentSampleDto[]; acknowledged: Set<string>; onAcknowledge: (sampleId: string, checked: boolean) => void }) {
  return <div className="quality-list">{samples.map((sample, index) => <article className={`quality-card quality-${sample.quality.status.toLowerCase()}`} key={sample.id}><div><Badge tone={sample.quality.status === "PASS" ? "success" : sample.quality.status === "WARNING" ? "warning" : "danger"}>{sample.quality.status}</Badge><strong>Sample {index + 1}</strong><span>{sample.duration_seconds?.toFixed(1) ?? "—"}초 · {sample.normalized_content_type ?? sample.original_content_type ?? "형식 확인 중"}</span></div>{sample.quality.status === "PASS" && <p>기본 검사를 통과했습니다.</p>}{sample.quality.status === "WARNING" && <>{sample.quality.warnings.map((warning) => <p key={warning}>{qualityWarningMessage(warning)}</p>)}<label className="check"><input type="checkbox" checked={acknowledged.has(sample.id)} onChange={(event) => onAcknowledge(sample.id, event.target.checked)} />이 Sample의 품질 경고를 확인했습니다.</label></>}{sample.quality.status === "FAIL" && <p>이 Sample은 제출에 사용할 수 없습니다. 삭제하고 다시 녹음하거나 다른 파일을 올려 주세요.</p>}</article>)}<p className="muted">이 검사는 파일 형식과 기본 음향 상태를 확인합니다. Voice Provider 적합성이나 최종 변환 품질을 보장하지 않습니다.</p></div>;
}

function ReferenceStep({ samples, selectedId, displayNames, previewUrls, onSelect, deletingId, onDelete }: { samples: VoiceEnrollmentSampleDto[]; selectedId?: string; displayNames: Record<string, string>; previewUrls: Record<string, string>; onSelect: (id: string) => void; deletingId?: string; onDelete: (id: string) => void }) {
  return <div><p>대표 Sample은 현재 Voice Conversion과 음악 생성 Pipeline에 사용됩니다.</p><div className="sample-card-grid" role="radiogroup" aria-label="대표 Sample 선택">{samples.map((sample, index) => <VoiceSampleCard key={sample.id} sample={sample} label={sampleDisplayLabel(sample, index, displayNames)} previewUrl={previewUrls[sample.id]} selected={selectedId === sample.id} selectionMode="radio" deleting={deletingId === sample.id} onSelect={() => onSelect(sample.id)} onDelete={() => { if (window.confirm("이 Sample을 삭제할까요?")) onDelete(sample.id); }} />)}</div></div>;
}

function ReviewStep({ name, description, samples, selected }: { name: string; description: string | null; samples: VoiceEnrollmentSampleDto[]; selected?: VoiceEnrollmentSampleDto }) {
  return <div className="review-grid"><article><span>목소리 이름</span><strong>{name}</strong></article><article><span>설명</span><strong>{description || "설명 없음"}</strong></article><article><span>포함 Sample</span><strong>{samples.filter((sample) => sample.submit_eligible).length}개</strong></article><article><span>대표 Sample</span><strong>{selected ? `${selected.duration_seconds?.toFixed(1) ?? "—"}초 · ${selected.quality.status}` : "선택 필요"}</strong></article><p className="muted full">이름이나 설명을 바꾸려면 현재 등록을 취소하고 새로 시작해야 합니다. 제출하면 대표 Sample의 정규화 reference로 Voice Profile이 생성됩니다.</p></div>;
}

function CompleteStep({ name, sample, sampleLabel, previewUrl, onNew }: { name: string; sample?: VoiceEnrollmentSampleDto; sampleLabel?: string; previewUrl?: string; onNew: () => void }) {
  return <div className="enrollment-complete"><span aria-hidden="true">✓</span><div className="complete-copy"><span>Voice Profile</span><h3>목소리 등록이 완료되었습니다</h3><p><strong>{name}</strong> Profile을 만들고 음악 만들기에 선택했습니다.</p></div>{sample && <article className="complete-reference"><div><span>대표 Sample</span><strong>{sampleLabel ?? "대표 Sample"}</strong><small>{sample.duration_seconds?.toFixed(1) ?? "—"}초 · {sample.quality.status}</small></div>{previewUrl && <VoiceAudioPlayer src={previewUrl} label={sampleLabel ?? "대표 Sample"} />}</article>}<div className="complete-actions"><Link className="button" href="/studio">Studio에서 사용하기</Link><Button type="button" className="secondary" onClick={onNew}>새 목소리 등록</Button></div></div>;
}
