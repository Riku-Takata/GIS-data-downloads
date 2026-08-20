"use client";

import { CheckCircle2, FolderSync, ExternalLink, Download, ArrowRight, RotateCcw } from "lucide-react";

export interface CompletedDownloadItem {
  id: string;
  data_code: string;
  pref_code: string;
  region_name: string;
  data_name?: string;
  file_name: string;
  file_size_mb: number | null;
  format: string;
  drive_web_view_link: string | null;
  direct_download_url: string;
  date_folder?: string;
}

interface CompletedViewProps {
  completedItems: CompletedDownloadItem[];
  onResetToTop: () => void;
}

export default function CompletedView({
  completedItems,
  onResetToTop,
}: CompletedViewProps) {
  const dateFolder = completedItems[0]?.date_folder || "今日の日付";

  return (
    <div className="max-w-2xl mx-auto space-y-6 animate-fadeIn my-6">
      {/* Success Banner Card */}
      <div className="bg-white rounded-3xl p-6 sm:p-8 shadow-sm border border-emerald-200 text-center space-y-4">
        <div className="w-16 h-16 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto shadow-inner">
          <CheckCircle2 className="w-10 h-10" />
        </div>

        <div className="space-y-1">
          <span className="px-3 py-1 rounded-full text-xs font-extrabold bg-emerald-50 text-emerald-700 border border-emerald-200">
            全 {completedItems.length} 件 完了
          </span>
          <h2 className="text-2xl font-extrabold text-slate-900 mt-2">
            ダウンロード & 保存が完了しました！
          </h2>
          <p className="text-sm text-slate-600">
            Google Drive の「<span className="font-bold text-slate-800">{dateFolder}</span>」フォルダへ自動保存されました。
          </p>
        </div>
      </div>

      {/* Downloaded Files List */}
      <div className="bg-white rounded-2xl p-5 sm:p-6 shadow-sm border border-slate-200 space-y-3">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
          保存されたデータファイル一覧
        </h3>

        <div className="divide-y divide-slate-100">
          {completedItems.map((item) => (
            <div
              key={item.id}
              className="py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
            >
              <div className="space-y-1">
                <div className="flex items-center space-x-2">
                  <span className="text-xs font-bold px-2 py-0.5 rounded bg-blue-100 text-blue-800">
                    {item.region_name}
                  </span>
                  <span className="text-xs font-bold text-slate-800">
                    {item.file_name}
                  </span>
                  <span className="text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-600 font-medium">
                    {item.format} ({item.file_size_mb ? `${item.file_size_mb} MB` : "-"})
                  </span>
                </div>
              </div>

              <div className="flex items-center space-x-2">
                {item.drive_web_view_link && (
                  <a
                    href={item.drive_web_view_link}
                    target="_blank"
                    rel="noreferrer"
                    className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg text-xs transition flex items-center space-x-1.5 shadow-sm"
                  >
                    <FolderSync className="w-3.5 h-3.5" />
                    <span>Drive で開く</span>
                    <ExternalLink className="w-3 h-3" />
                  </a>
                )}

                {item.direct_download_url && (
                  <a
                    href={item.direct_download_url}
                    target="_blank"
                    rel="noreferrer"
                    className="px-3 py-1.5 bg-white hover:bg-slate-50 text-slate-700 font-medium rounded-lg text-xs border border-slate-200 transition flex items-center space-x-1"
                    title="公式ZIP直接ダウンロード"
                  >
                    <Download className="w-3.5 h-3.5" />
                    <span>ZIP</span>
                  </a>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Return to Top Button */}
      <div className="text-center pt-2">
        <button
          type="button"
          onClick={onResetToTop}
          className="px-8 py-3.5 bg-slate-900 hover:bg-black text-white font-bold rounded-2xl text-sm transition inline-flex items-center space-x-2 shadow-lg shadow-slate-900/20 transform hover:-translate-y-0.5 active:translate-y-0"
        >
          <RotateCcw className="w-4 h-4" />
          <span>トップページに戻って別のデータを検索する</span>
        </button>
      </div>
    </div>
  );
}
