"use client";
import { useQuery } from "@tanstack/react-query";
import { dohaApi } from "@/services/doha-api";
import { Badge } from "./ui";
export function ApiStatus() { const query = useQuery({ queryKey: ["health"], queryFn: dohaApi.health, retry: false }); return <Badge tone={query.isSuccess ? "success" : query.isPending ? "neutral" : "error"}>{query.isSuccess ? "API 연결됨" : query.isPending ? "API 확인 중" : "API 오프라인"}</Badge>; }
