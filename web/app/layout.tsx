import type { Metadata } from "next";
import { Bodoni_Moda, Fragment_Mono, Inter } from "next/font/google";
import Wordmark from "@/components/Wordmark";
import "./globals.css";

const display = Bodoni_Moda({ subsets: ["latin"], variable: "--font-bodoni" });

const mono = Fragment_Mono({
  subsets: ["latin"],
  variable: "--font-fragment",
  weight: "400",
});

const sans = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "Kiplore",
  description: "Bedtime stories that answer back.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${display.variable} ${mono.variable} ${sans.variable}`}
    >
      <body className="min-h-dvh antialiased">
        <Wordmark />
        {children}
      </body>
    </html>
  );
}
