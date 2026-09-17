import type { Metadata } from "next";
import { Big_Shoulders_Display, IBM_Plex_Mono, Jost } from "next/font/google";

import { Providers } from "@/api/query-client";
import { ToastViewport } from "@/components/Toast";

import "./globals.css";

/* Atlantic's three voices. Monigue (display) and Epoch (UI) are the licensed
 * faces; Big Shoulders and Jost are the agreed fallbacks and are what actually
 * ships, so they are what next/font serves. The real names still lead the stack
 * in tailwind.config.ts, so a machine with them installed gets them.
 *
 * next/font self-hosts these at build time: no render-blocking request to
 * fonts.googleapis.com and no layout shift as the display face swaps in, which
 * matters most on the landing hero where the headline is 100px tall. */
const display = Big_Shoulders_Display({
  subsets: ["latin"],
  weight: ["400", "600", "700", "800", "900"],
  variable: "--font-display",
  display: "swap",
});

const ui = Jost({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600"],
  variable: "--font-ui",
  display: "swap",
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "GhostNet-AI — find the nets the ocean kept hidden",
  description:
    "GhostNet-AI reads side-scan sonar and flags abandoned fishing gear as polygons, not pins — with calibrated confidence and a human review gate.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${ui.variable} ${mono.variable}`}>
      <body className="font-sans">
        <Providers>
          {children}
          <ToastViewport />
        </Providers>
      </body>
    </html>
  );
}
