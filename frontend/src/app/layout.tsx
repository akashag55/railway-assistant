import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Railway Assistant",
  description: "Personal Indian Railways journey search and availability assistant"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
