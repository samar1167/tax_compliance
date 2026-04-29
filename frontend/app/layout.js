import "./globals.css";

export const metadata = {
  title: "Tax Compliance MVP",
  description: "Indian personal tax filing obligation and ITR selection engine",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
