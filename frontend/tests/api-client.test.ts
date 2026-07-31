import { describe, expect, it } from "vitest";
import { ApiError, normalizeApiError } from "@/services/api-client";
describe("API error normalization",()=>{it("Backend 오류 코드와 메시지를 보존한다",()=>{const error=normalizeApiError(404,{error:{code:"RESOURCE_NOT_FOUND",message:"없습니다."}});expect(error).toBeInstanceOf(ApiError);expect(error.status).toBe(404);expect(error.code).toBe("RESOURCE_NOT_FOUND");expect(error.message).toBe("없습니다.")});it("알 수 없는 body를 안전한 오류로 바꾼다",()=>{expect(normalizeApiError(500,"secret stack").message).toBe("요청을 처리하지 못했습니다.")})});
