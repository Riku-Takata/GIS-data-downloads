"use client";

import { Loader2, Sparkles, Database, Map } from "lucide-react";

interface SearchingViewProps {
  query: string;
}

export default function SearchingView({ query }: SearchingViewProps) {
  return (
    <div className="max-w-xl mx-auto my-12 bg-white rounded-3xl p-8 sm:p-12 shadow-sm border border-slate-200 text-center space-y-6 animate-fadeIn">
      {/* Animated Glowing Spinner */}
      <div className="relative w-20 h-20 mx-auto flex items-center justify-center">
        <div className="absolute inset-0 rounded-full bg-blue-500/20 animate-ping"></div>
        <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-blue-600 to-indigo-600 text-white flex items-center justify-center shadow-lg shadow-blue-500/30">
          <Loader2 className="w-8 h-8 animate-spin" />
        </div>
      </div>

      <div className="space-y-2">
        <div className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-bold bg-blue-50 text-blue-700">
          <Sparkles className="w-3.5 h-3.5 text-blue-500" />
          <span>AI 解析中</span>
        </div>
        <h3 className="text-xl sm:text-2xl font-extrabold text-slate-900">
          検索中です...
        </h3>
        <p className="text-sm text-slate-500 max-w-sm mx-auto">
          「<span className="font-semibold text-slate-800">{query}</span>」の意図を解析し、国土数値情報マスターと対象地域を特定しています。
        </p>
      </div>

      {/* Progress Steps */}
      <div className="bg-slate-50 rounded-2xl p-4 border border-slate-100 max-w-sm mx-auto text-xs text-left space-y-2.5">
        <div className="flex items-center space-x-2 text-slate-700 font-medium">
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></div>
          <span>1. 自然言語プロンプトの意図解析</span>
        </div>
        <div className="flex items-center space-x-2 text-slate-700 font-medium">
          <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse"></div>
          <span>2. Google Drive メタデータとのコード照合</span>
        </div>
        <div className="flex items-center space-x-2 text-slate-700 font-medium">
          <div className="w-2 h-2 rounded-full bg-indigo-500 animate-pulse"></div>
          <span>3. 地図座標 & 周辺エリアの特定</span>
        </div>
      </div>
    </div>
  );
}
