import type { Metadata } from "next";
import "./globals.css";
import { ApiStatusBanner } from "@/components/ApiStatusBanner";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "Commander",
  description: "Run your AI software company.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="font-sans antialiased">
        <Providers>
          <ApiStatusBanner />
          {children}
        </Providers>
      </body>
    </html>
  );
}
