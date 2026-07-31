"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { useEffect } from "react";
import { useSettingsStore } from "@/stores/settings-store";
import { Onboarding } from "@/components/onboarding";

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { retry: 1, staleTime: 5_000 },
          mutations: { retry: false },
        },
      }),
  );
  return (
    <QueryClientProvider client={client}>
      <SettingsSync />
      <Onboarding />
      {children}
    </QueryClientProvider>
  );
}

function SettingsSync() {
  const reducedMotion = useSettingsStore((state) => state.reducedMotion);
  useEffect(() => {
    document.documentElement.dataset.reduceMotion = String(
      reducedMotion ??
        window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    );
  }, [reducedMotion]);
  return null;
}
