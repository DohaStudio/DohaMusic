import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";
import path from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const root = path.dirname(fileURLToPath(import.meta.url));
const inProcess = process.env.DOHAMUSIC_TEST_IN_PROCESS === "1";
const tsconfig = ts.readConfigFile(path.join(root, "tsconfig.json"), ts.sys.readFile);
if (tsconfig.error) throw new Error(ts.flattenDiagnosticMessageText(tsconfig.error.messageText, "\n"));
const compilerOptions = ts.parseJsonConfigFileContent(tsconfig.config, ts.sys, root).options;

export default defineConfig({
  plugins: [
    ...(inProcess ? [{
      name: "typescript-in-process",
      enforce: "pre" as const,
      transform(code: string, id: string) {
        const filename = id.split("?")[0];
        if (filename.includes("node_modules") || !/\.tsx?$/.test(filename)) return;
        const result = ts.transpileModule(code, {
          fileName: filename,
          reportDiagnostics: true,
          compilerOptions: { ...compilerOptions, noEmit: false, sourceMap: true },
        });
        const errors = result.diagnostics?.filter((item) => item.category === ts.DiagnosticCategory.Error);
        if (errors?.length) {
          throw new Error(errors.map((item) => ts.flattenDiagnosticMessageText(item.messageText, "\n")).join("\n"));
        }
        return { code: result.outputText, map: result.sourceMapText };
      },
    }] : []),
    react(),
  ],
  // Vitest merges its JSX defaults into esbuild, so use the supported include filter.
  // The TypeScript plugin above transforms the actual TS/TSX source instead.
  esbuild: inProcess ? { include: /a^/ } : undefined,
  resolve: { alias: { "@": root }, preserveSymlinks: inProcess },
  test: {
    environment: "jsdom", setupFiles: ["./tests/setup.ts"], globals: true,
    exclude: ["tests/e2e/**", "node_modules/**"],
    ...(inProcess ? {
      pool: "threads" as const,
      deps: { optimizer: { client: { enabled: false }, ssr: { enabled: false } } },
    } : {}),
  },
});
