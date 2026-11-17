import type { Metadata } from "next";
import "./globals.css";
import { SmoothScroll } from "@/components/layout/SmoothScroll";
import { BackgroundScene } from "@/components/canvas/BackgroundScene";

export const metadata: Metadata = {
  title: "AI Employee — Executive Operations & Intelligence",
  description:
    "Enterprise AI Receptionist & Business Analyst Operations Console",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col bg-[#F7F7F5] text-[#1A1A1A] font-sans selection:bg-[#5C8A67]/20 selection:text-[#1A1A1A]">
        <BackgroundScene />
        <SmoothScroll>{children}</SmoothScroll>
      </body>
    </html>
  );
}
