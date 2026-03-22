import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AiWriter",
  description: "AI 自动写小说系统",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN">
      <body>
        {children}
      </body>
    </html>
  );
}
