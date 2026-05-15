import type { Metadata, Viewport } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import Aurora from "@/components/Aurora";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sentiment — read the market before it moves",
  description:
    "Type a ticker. We read every recent headline, score the sentiment with AI, and distill it into one clear signal.",
  applicationName: "Sentiment",
  authors: [{ name: "Stock Sentiment" }],
  openGraph: {
    title: "Sentiment — read the market before it moves",
    description:
      "AI-read news sentiment for any ticker. Every headline, scored. One signal, distilled.",
    type: "website",
  },
};

export const viewport: Viewport = {
  themeColor: "#060708",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body>
        <Aurora />
        {children}
      </body>
    </html>
  );
}
