import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Nav } from "@/components/nav";
import { Providers } from "@/components/providers";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "TalentLens — AI Talent Intelligence",
  description: "AI that hires like your best manager — because it remembers everything",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={`${inter.className} bg-[#F8F9FA]`}>
        <Providers>
          <Nav />
          <main className="pt-14 min-h-screen">
            <div className="max-w-[1400px] mx-auto px-6 py-8">{children}</div>
          </main>
        </Providers>
      </body>
    </html>
  );
}
