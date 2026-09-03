import { describe, expect, it } from "vitest";
import nextConfig from "../next.config";

describe("Next.js Backend proxy upload limit", () => {
  it("Voice Enrollment의 25MiB 파일과 multipart metadata를 자르지 않는다", () => {
    expect(nextConfig.experimental?.proxyClientMaxBodySize).toBe("26mb");
  });

  it("127.0.0.1 local dev origin의 hydration asset 요청만 명시적으로 허용한다", () => {
    expect(nextConfig.allowedDevOrigins).toEqual(["127.0.0.1"]);
  });
});
