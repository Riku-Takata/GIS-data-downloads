"use client";

import { Loader2, CheckCircle2, FolderSync, Database } from "lucide-react";
import { SelectedDownloadItem } from "./ResultMapView";

interface DownloadingViewProps {
  items: SelectedDownloadItem[];
  currentIndex: number;
  currentMessage: string;
}

export default function DownloadingView({
  items,
  currentIndex,
  currentMessage,
}: DownloadingViewProps) {
  const percent = Math.min(100, Math.round(((currentIndex + 0.5) / items.length) * 100));

  return (
    <div className="max-w-xl mx-auto my-8 bg-white rounded-3xl p-6 sm:p-10 shadow-sm border border-slate-200 space-y-6 text-center animate-fadeIn">
      <div className="relative w-16 h-16 mx-auto flex items-center justify-center">
        <div className="absolute inset-0 rounded-full bg-emerald-500/20 animate-ping"></div>
        <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-emerald-600 to-teal-600 text-white flex items-center justify-center shadow-lg shadow-emerald-500/30">
          <Loader2 className="w-7 h-7 animate-spin" />
        </div>
      </div>

      <div className="space-y-2">
        <h3 className="text-xl sm:text-2xl font-extrabold text-slate-900">
          データをダウンロード中です...
        </h3>
        <p className="text-sm text-slate-500">
          国土数値情報サイトからZIPを取得し、Google Driveへ自動保存しています。
        </p>
      </div>

      {/* Progress Bar */}
      <div className="space-y-1.5 max-w-md mx-auto">
        <div className="flex justify-between text-xs font-bold text-slate-600">
          <span>進捗状況 ({Math.min(currentIndex + 1, items.length)} / {items.length} 件)</span>
          <span>{percent}%</span>
        </div>
        <div className="w-full h-2.5 bg-slate-100 rounded-full overflow-hidden">
          <div
            className="h-full bg-emerald-600 transition-all duration-500 rounded-full"
            style={{ width: `${percent}%` }}
          ></div>
        </div>
        <p className="text-xs text-emerald-600 font-medium pt-1">
          {currentMessage || "処理中..."}
        </p>
      </div>

      {/* Item by Item Status List */}
      <div className="bg-slate-50 rounded-2xl p-4 border border-slate-100 max-w-md mx-auto text-xs text-left space-y-2 divide-y divide-slate-200/60">
        {items.map((item, idx) => {
          const isDone = idx < currentIndex;
          const isCurrent = idx === currentIndex;
          const isWaiting = idx > currentIndex;

          return (
            <div key={item.id} className="pt-2 first:pt-0 flex items-center justify-between">
              <div className="space-y-0.5">
                <p className="font-bold text-slate-800">
                  {item.pref_name} - {item.data_name}
                </p>
                <p className="text-[11px] text-slate-400">
                  {item.data_code} ({item.format})
                </p>
              </div>

              <div>
                {isDone && (
                  <span className="inline-flex items-center space-x-1 text-emerald-600 font-bold">
                    <CheckCircle2 className="w-4 h-4" />
                    <span>完了</span>
                  </span>
                )}
                {isCurrent && (
                  <span className="inline-flex items-center space-x-1 text-blue-600 font-bold">
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>取得中</span>
                  </span>
                )}
                {isWaiting && (
                  <span className="text-slate-400 font-medium">待機中</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
