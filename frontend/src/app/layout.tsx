import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MediShield - Document Intake",
  description: "AI-powered document intake system for health insurance claims",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
