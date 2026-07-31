import type { Metadata } from "next";
import { Inter, Manrope } from "next/font/google";
import { Providers } from "./providers";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-body" });
const manrope = Manrope({ subsets: ["latin"], variable: "--font-display" });
export const metadata: Metadata = { title: { default: "Doha Music Studio", template: "%s · Doha Music" }, description: "Provider-neutral AI music creation studio" };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="ko"><body className={`${inter.variable} ${manrope.variable}`}><a className="skip-link" href="#main-content">본문으로 건너뛰기</a><Providers>{children}</Providers></body></html>; }
