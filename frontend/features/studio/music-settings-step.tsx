"use client";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { Button, Field, Input, Textarea, Unsupported } from "@/components/ui";
import { useStudioStore } from "@/stores/studio-store";
import { musicSettingsSchema, type MusicSettingsValues } from "./studio-schema";

export function MusicSettingsStep() {
  const store = useStudioStore();
  const form = useForm<MusicSettingsValues>({
    resolver: zodResolver(musicSettingsSchema),
    defaultValues: {
      prompt: store.prompt,
      genre: store.genre,
      durationSeconds: store.durationSeconds,
      seed: store.seed,
    },
  });
  const submit = (value: MusicSettingsValues) => {
    store.patch({
      prompt: value.prompt,
      genre: value.genre,
      durationSeconds: value.durationSeconds,
      seed: value.seed === "" ? undefined : value.seed,
    });
    store.setStep("lyrics");
  };
  return (
    <form onSubmit={form.handleSubmit(submit)} className="studio-form">
      <Field
        label="음악 설명"
        htmlFor="prompt"
        error={form.formState.errors.prompt?.message}
      >
        <Textarea
          id="prompt"
          rows={5}
          placeholder="새벽 도시를 걷는 따뜻한 R&B 곡"
          {...form.register("prompt")}
        />
      </Field>
      <div className="form-grid">
        <Field label="장르" htmlFor="genre">
          <Input id="genre" {...form.register("genre")} />
        </Field>
        <Field label="길이 (초)" htmlFor="duration">
          <Input
            id="duration"
            type="number"
            {...form.register("durationSeconds", { valueAsNumber: true })}
          />
        </Field>
        <Field label="Seed (선택)" htmlFor="seed">
          <Input
            id="seed"
            type="number"
            {...form.register("seed", {
              setValueAs: (value) => (value === "" ? "" : Number(value)),
            })}
          />
        </Field>
      </div>
      <div className="feature-disabled">
        <Unsupported>BPM</Unsupported>
        <Unsupported>Model 선택</Unsupported>
        <Unsupported>고급 믹싱</Unsupported>
      </div>
      <Button type="submit">가사 단계로</Button>
    </form>
  );
}
