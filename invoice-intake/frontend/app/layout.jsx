import "./globals.css";

export const metadata = {
  title: "SAKANA AI — Invoice automation",
  description: "Automating the boring office work. 請求書処理を、もっと簡単に。",
};

export default function RootLayout({ children }) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  );
}