"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import {
  Badge,
  Button,
  ErrorAlert,
  Field,
  Input,
  Textarea,
} from "@/components/ui";
import { mapLyrics } from "@/lib/mappers";
import { isDeveloperInfoEnabled } from "@/lib/developer-info";
import { userErrorMessage } from "@/services/api-client";
import { dohaApi } from "@/services/doha-api";
import { useStudioStore } from "@/stores/studio-store";
import type { LyricsDocumentDto, LyricsValidationDto } from "@/types/api";

export function isRevisionSupported(document: LyricsDocumentDto): boolean {
  const capabilities = document.metadata.capabilities;
  return Boolean(
    capabilities &&
    typeof capabilities === "object" &&
    "revision" in capabilities &&
    (capabilities as { revision?: unknown }).revision === true,
  );
}

export function LyricsLab() {
  const router = useRouter();
  const patch = useStudioStore((state) => state.patch);
  const [topic, setTopic] = useState("");
  const [genre, setGenre] = useState("댄스 팝");
  const [mood, setMood] = useState("따뜻한");
  const [text, setText] = useState("");
  const [doc, setDoc] = useState<LyricsDocumentDto>();
  const [validation, setValidation] = useState<LyricsValidationDto>();
  const [instruction, setInstruction] = useState("");
  const create = useMutation({
    mutationFn: () =>
      dohaApi.createLyrics({
        topic,
        genre,
        mood,
        language: "ko",
        keywords: [],
        structure: ["verse", "chorus", "verse", "chorus"],
        target_duration_seconds: 30,
        allow_template_fallback: false,
      }),
    onSuccess: (value) => {
      setDoc(value);
      setText(value.full_text);
    },
  });
  const validate = useMutation({
    mutationFn: () => dohaApi.validateLyrics(text),
    onSuccess: setValidation,
  });
  const revise = useMutation({
    mutationFn: () => dohaApi.reviseLyrics(doc!.id, instruction),
    onSuccess: (value) => {
      setDoc(value);
      setText(value.full_text);
    },
  });
  const remove = useMutation({
    mutationFn: () => dohaApi.deleteLyrics(doc!.id),
    onSuccess: () => {
      setDoc(undefined);
      setText("");
      setValidation(undefined);
    },
  });
  const error = create.error || validate.error || revise.error || remove.error;
  const view = doc ? mapLyrics(doc) : undefined;
  const revisionSupported = doc ? isRevisionSupported(doc) : false;

  return (
    <section className="page-stack">
      <header className="page-heading">
        <p className="eyebrow">가사 만들기</p>
        <h1>가사를 어떻게 준비할까요?</h1>
        <p>주제와 분위기를 알려주면 초안을 만들고, 직접 고쳐 음악에 사용할 수 있습니다.</p>
      </header>
      <div className="two-panel">
        <form
          className="surface-card"
          onSubmit={(event) => {
            event.preventDefault();
            create.mutate();
          }}
        >
          <h2>AI가 만들어주기</h2>
          <Field label="주제" htmlFor="topic">
            <Input
              id="topic"
              value={topic}
              onChange={(event) => setTopic(event.target.value)}
              required
            />
          </Field>
          <div className="form-grid">
            <Field label="장르" htmlFor="lyrics-genre">
              <Input
                id="lyrics-genre"
                value={genre}
                onChange={(event) => setGenre(event.target.value)}
              />
            </Field>
            <Field label="분위기" htmlFor="mood">
              <Input
                id="mood"
                value={mood}
                onChange={(event) => setMood(event.target.value)}
              />
            </Field>
          </div>
          <Button disabled={create.isPending || !topic}>
            {create.isPending ? "만드는 중…" : "가사 만들어보기"}
          </Button>
          <hr />
          <h2>직접 쓰기</h2>
          <Field label="가사 전문" htmlFor="lyrics-text">
            <Textarea
              id="lyrics-text"
              rows={14}
              value={text}
              onChange={(event) => setText(event.target.value)}
            />
          </Field>
          <Button
            type="button"
            className="secondary"
            disabled={!text || validate.isPending}
            onClick={() => validate.mutate()}
          >
            작성 내용 확인
          </Button>
        </form>
        <article className="surface-card lyrics-result">
          <div className="result-head">
            <h2>{view?.title ?? "가사 결과"}</h2>
            {view && isDeveloperInfoEnabled() && (
              <div>
                <Badge tone="success">{view.providerLabel}</Badge>
                <Badge>{view.modelLabel}</Badge>
              </div>
            )}
          </div>
          {error && (
            <ErrorAlert
              message={
                userErrorMessage(error)
              }
            />
          )}
          {!view && !validation && !error && (
            <div className="empty">
              <span>♪</span>
              <p>생성하거나 검증한 가사가 여기에 표시됩니다.</p>
            </div>
          )}
          {view?.sections.map((section, index) => (
            <section
              key={`${section.section_type}-${index}`}
              className="lyric-section"
            >
              <h3>[{section.section_type}]</h3>
              {section.lines.map((line, lineIndex) => (
                <p key={lineIndex}>{line}</p>
              ))}
            </section>
          ))}
          {validation && <ValidationResult value={validation} />}
          {view && (
            <>
              {revisionSupported ? (
                <>
                  <Field label="수정 지시" htmlFor="revision">
                    <Input
                      id="revision"
                      value={instruction}
                      onChange={(event) => setInstruction(event.target.value)}
                      placeholder="후렴을 더 기억하기 쉽게"
                    />
                  </Field>
                  <Button
                    className="secondary"
                    disabled={!instruction || revise.isPending}
                    onClick={() => revise.mutate()}
                  >
                    의미 기반 수정
                  </Button>
                </>
              ) : (
                <div className="notice">
                  <strong>AI에게 다시 고쳐달라고 요청하는 기능은 준비 중입니다.</strong>
                  <p>지금은 왼쪽의 가사를 직접 편집하거나 새 가사를 만들어 주세요.</p>
                </div>
              )}
              <div className="actions">
                <Button
                  className="danger"
                  disabled={remove.isPending}
                  onClick={() => remove.mutate()}
                >
                  삭제
                </Button>
                <Button
                  onClick={() => {
                    patch({
                      lyricsDocumentId: view.id,
                      lyricsText: text,
                      currentStep: "voice",
                    });
                    router.push("/studio");
                  }}
                >
                  이 가사 사용하기
                </Button>
              </div>
            </>
          )}
        </article>
      </div>
    </section>
  );
}

export function ValidationResult({ value }: { value: LyricsValidationDto }) {
  return (
    <div className={`validation-card ${value.valid ? "valid" : "invalid"}`}>
      <h3>{value.valid ? "검증 통과" : "수정 필요"}</h3>
      <p>
        {value.line_count}줄 · {value.section_count}개 섹션 · 반복률{" "}
        {Math.round(value.repetition_ratio * 100)}%
      </p>
      {value.errors.map((item) => (
        <p className="validation-bad" key={item}>
          오류 · {item}
        </p>
      ))}
      {value.warnings.map((item) => (
        <p className="validation-warn" key={item}>
          주의 · {item}
        </p>
      ))}
    </div>
  );
}
