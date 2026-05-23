import type { Metadata, Viewport } from "next";
import { Ubuntu_Mono } from "next/font/google";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import Aurora from "@/components/Aurora";
import MotionProvider from "@/components/MotionProvider";
import Nav from "@/components/Nav";
import { siteUrl } from "@/lib/site-url";
import "./globals.css";

const ubuntuMono = Ubuntu_Mono({
  subsets: ["latin"],
  weight: ["400", "700"],
  variable: "--font-ubuntu-mono",
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
  themeColor: "#05080c",
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
      className={`${GeistSans.variable} ${GeistMono.variable} ${ubuntuMono.variable}`}
    >
      <body>
        <Aurora />
        <Nav />
        <MotionProvider>{children}</MotionProvider>
      </body>
    </html>
  );
}
