import type { Route } from "@playwright/test";

export interface HistoryEntry {
  clipId: string;
  applyBefore(): void;
  applyAfter(): void;
}

type Completion = { fingerprint: string; data: Record<string, unknown> };

export class PersistentHistoryFixture {
  private entries: HistoryEntry[] = [];
  private cursor = 0;
  private completions = new Map<string, Completion>();

  constructor(
    private readonly workingCompositionId: string,
    private readonly revision: { get(): number; increment(): number },
  ) {}

  projection() {
    return {
      working_composition_id: this.workingCompositionId,
      revision: this.revision.get(),
      cursor: this.cursor,
      command_count: this.entries.length,
      can_undo: this.cursor > 0,
      can_redo: this.cursor < this.entries.length,
    };
  }

  append(entry: HistoryEntry) {
    this.entries = this.entries.slice(0, this.cursor);
    this.entries.push(entry);
    this.cursor = this.entries.length;
  }

  barrier() {
    this.entries = [];
    this.cursor = 0;
  }

  async mutate(route: Route, direction: "undo" | "redo") {
    const request = route.request();
    const body = request.postDataJSON() as Record<string, unknown>;
    const key = request.headers()["idempotency-key"] ?? "";
    const fingerprint = `${direction}:${JSON.stringify(body)}`;
    const replay = this.completions.get(key);
    if (replay) {
      if (replay.fingerprint !== fingerprint) return error(route, 409, "IDEMPOTENCY_KEY_REUSED");
      return ok(route, { data: { ...replay.data, replayed: true } });
    }
    if (Object.keys(body).sort().join(",") !== "expected_revision,working_composition_id"
      || body.working_composition_id !== this.workingCompositionId) {
      return error(route, 422, "VALIDATION_ERROR");
    }
    if (body.expected_revision !== this.revision.get()) {
      return error(route, 409, "WORKING_COMPOSITION_REVISION_CONFLICT");
    }
    const index = direction === "undo" ? this.cursor - 1 : this.cursor;
    const entry = this.entries[index];
    if (!entry) return error(route, 409, "WORKING_HISTORY_EMPTY");
    if (direction === "undo") {
      entry.applyBefore();
      this.cursor -= 1;
    } else {
      entry.applyAfter();
      this.cursor += 1;
    }
    const data = { clip_id: entry.clipId, completed_revision: this.revision.increment(), replayed: false };
    if (key) this.completions.set(key, { fingerprint, data });
    return ok(route, { data });
  }
}

function ok(route: Route, json: unknown) {
  return route.fulfill({ status: 200, json });
}

function error(route: Route, status: number, code: string) {
  return route.fulfill({ status, json: { error: { code, message: code } } });
}
