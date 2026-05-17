import type { Metadata, Viewport } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import { Playfair_Display } from "next/font/google";
import Aurora from "@/components/Aurora";
import MotionProvider from "@/components/MotionProvider";
import { siteUrl } from "@/lib/site-url";
import "./globals.css";

const playfair = Playfair_Display({
  subsets: ["latin"],
  variable: "--font-playfair",
  display: "swap",
});

const SITE_URL = siteUrl();
const TITLE = "Sentiment — Read the market before it moves";
const DESCRIPTION =
  "AI-powered news sentiment for any stock ticker. Every headline read, scored, and distilled into one clear signal.";

export const metadata: Metadata = {
  metadataBase: SITE_URL,
  title: TITLE,
  description: DESCRIPTION,
  applicationName: "Sentiment",
  authors: [{ name: "Stock Sentiment" }],
  alternates: { canonical: "/" },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true, "max-image-preview": "large" },
  },
  openGraph: {
    title: TITLE,
    description: DESCRIPTION,
    type: "website",
    url: SITE_URL.toString(),
    siteName: "Sentiment",
    locale: "en_US",
  },
  twitter: {
    card: "summary_large_image",
    title: TITLE,
    description: DESCRIPTION,
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
        <MotionProvider>{children}</MotionProvider>
      </body>
    </html>
  );
}
