import type { Metadata } from "next";

import { Providers } from "@/api/query-client";
import { ToastViewport } from "@/components/Toast";

import "./globals.css";

export const metadata: Metadata = {
  title: "GhostNet-AI",
  description: "Marine Sonar Intelligence Platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="font-sans">
        <Providers>
          {children}
          <ToastViewport />
        </Providers>
      </body>
    </html>
  );
}
