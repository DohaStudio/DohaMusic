import { describe, expect, it, vi } from "vitest";
import { newIdempotencyKey } from "@/features/composition/working-composition-history";

describe("persistent WorkingComposition history request identity", () => {
  it("creates a fresh opaque identity for each logical history action", () => {
    const randomUUID = vi.spyOn(crypto, "randomUUID")
      .mockReturnValueOnce("00000000-0000-4000-8000-000000000001")
      .mockReturnValueOnce("00000000-0000-4000-8000-000000000002");
    expect(newIdempotencyKey()).not.toBe(newIdempotencyKey());
    expect(randomUUID).toHaveBeenCalledTimes(2);
  });
});
