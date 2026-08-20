import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "国土数値情報 自動検索・取得システム",
  description: "自然言語から国土数値情報を検索し、取得したデータをGoogle Driveへ自動保存するWebアプリケーション",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ja">
      <body className="min-h-screen bg-slate-50 text-slate-900 flex flex-col">
        <header className="border-b border-slate-200 bg-white/80 backdrop-blur sticky top-0 z-50">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-9 h-9 rounded-lg bg-blue-600 flex items-center justify-center text-white font-bold shadow-sm">
                GIS
              </div>
              <div>
                <h1 className="text-base sm:text-lg font-bold text-slate-900 tracking-tight">
                  国土数値情報 自動検索・取得
                </h1>
                <p className="text-xs text-slate-500 hidden sm:block">
                  AI自然言語検索 & Google Drive 自動保存
                </p>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <a
                href="https://nlftp.mlit.go.jp/ksj/"
                target="_blank"
                rel="noreferrer"
                className="text-xs sm:text-sm font-medium text-slate-600 hover:text-blue-600 transition"
              >
                国土数値情報サイト ↗
              </a>
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
                <span className="w-1.5 h-1.5 mr-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                API Connected
              </span>
            </div>
          </div>
        </header>

        <main className="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 py-8">
          {children}
        </main>

        <footer className="border-t border-slate-200 bg-white py-6 mt-12 text-center text-xs text-slate-500">
          <div className="max-w-6xl mx-auto px-4">
            <p>© {new Date().getFullYear()} GIS Data Downloads System. All data provided by MLIT National Land Numerical Information.</p>
          </div>
        </footer>
      </body>
    </html>
  );
}
