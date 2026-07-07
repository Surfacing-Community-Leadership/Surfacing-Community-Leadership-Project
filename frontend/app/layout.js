import "@/styles/globals.css";

export const metadata = {
  title: "Surfacing Community Leadership",
  description: "Turn everyday acts of helping and hosting into real relationships.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
