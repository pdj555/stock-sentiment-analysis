import type { Metadata, Viewport } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import { Playfair_Display } from "next/font/google";
import Aurora from "@/components/Aurora";
import "./globals.css";

const playfair = Playfair_Display({
  subsets: ["latin"],
  variable: "--font-playfair",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Sentiment — Read the market before it moves",
  description:
    "AI-powered news sentiment for any stock ticker. Every headline read, scored, and distilled into one clear signal.",
  applicationName: "Sentiment",
  authors: [{ name: "Stock Sentiment" }],
  openGraph: {
    title: "Sentiment — Read the market before it moves",
    description:
      "AI-powered news sentiment for any stock ticker. Every headline read, scored, and distilled into one clear signal.",
    type: "website",
  },
};

export const viewport: Viewport = {
  themeColor: "#0d0c0a",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${GeistSans.variable} ${GeistMono.variable} ${playfair.variable}`}
    >
      <body>
        <Aurora />
        {children}
      </body>
    </html>
  );
}
