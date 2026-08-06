import { describe, expect, it } from "vitest";
import nextConfig from "../next.config";

describe("Next.js Backend proxy upload limit", () => {
  it("Voice Enrollment의 25MiB 파일과 multipart metadata를 자르지 않는다", () => {
    expect(nextConfig.experimental?.proxyClientMaxBodySize).toBe("26mb");
  });
});
