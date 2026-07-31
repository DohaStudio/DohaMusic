"use client";
import { useQuery } from "@tanstack/react-query";
import { dohaApi } from "@/services/doha-api";
import { Badge } from "./ui";
export function ApiStatus() {
  const query = useQuery({
    queryKey: ["health"],
    queryFn: dohaApi.health,
    retry: false,
  });
  return (
    <Badge
      tone={query.isSuccess ? "success" : query.isPending ? "neutral" : "error"}
    >
      {query.isSuccess
        ? "음악 만들기 가능"
        : query.isPending
          ? "연결 확인 중"
          : "음악 생성 서버에 연결할 수 없습니다"}
    </Badge>
  );
}
