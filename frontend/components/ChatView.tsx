"use client";

import { useState } from "react";
import { Search, Sparkles, ArrowRight, Bot, Compass, ShieldCheck } from "lucide-react";

interface ChatViewProps {
  onSearch: (query: string) => void;
}

const SUGGESTIONS = [
  "富山県の土砂災害警戒区域データ",
  "全国の行政区域 GML 2024",
  "東京都の地価公示データ",
  "石川県の避難施設データ",
  "愛知県の用途地域データ",
  "大阪府の医療機関データ",
];

export default function ChatView({ onSearch }: ChatViewProps) {
  const [inputQuery, setInputQuery] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputQuery.trim()) return;
    onSearch(inputQuery.trim());
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Assistant Intro Message Bubble */}
      <div className="bg-white rounded-3xl p-6 sm:p-8 shadow-sm border border-slate-200 space-y-6">
        <div className="flex items-start space-x-4">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-blue-600 to-indigo-500 text-white flex items-center justify-center flex-shrink-0 shadow-md shadow-blue-500/20">
            <Bot className="w-6 h-6" />
          </div>
          <div className="space-y-2 flex-1">
            <div className="flex items-center space-x-2">
              <h2 className="text-lg font-extrabold text-slate-900">
                GIS データ探索アシスタント
              </h2>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-100">
                国土数値情報 × Google Drive
              </span>
            </div>
            <p className="text-sm text-slate-600 leading-relaxed">
              こんにちは！国土交通省の全133データセットから、あなたが必要なGISデータを自然言語で検索・自動取得します。
              地域やデータの種類（例:「富山県の土砂災害」「東京都の地価公示 GeoJSON」など）をお気軽に入力してください。
            </p>
          </div>
        </div>

        {/* Feature Highlights */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2 border-t border-slate-100 text-xs">
          <div className="flex items-center space-x-2 text-slate-600 bg-slate-50 p-2.5 rounded-xl border border-slate-100">
            <Sparkles className="w-4 h-4 text-amber-500 flex-shrink-0" />
            <span>AIが意図・地域を自動解析</span>
          </div>
          <div className="flex items-center space-x-2 text-slate-600 bg-slate-50 p-2.5 rounded-xl border border-slate-100">
            <Compass className="w-4 h-4 text-blue-500 flex-shrink-0" />
            <span>地図で周辺データも同時選択</span>
          </div>
          <div className="flex items-center space-x-2 text-slate-600 bg-slate-50 p-2.5 rounded-xl border border-slate-100">
            <ShieldCheck className="w-4 h-4 text-emerald-500 flex-shrink-0" />
            <span>Google Drive日付フォルダへ保存</span>
          </div>
        </div>
      </div>

      {/* Input Box Card */}
      <form onSubmit={handleSubmit} className="relative">
        <div className="relative flex items-center shadow-lg rounded-2xl overflow-hidden border-2 border-blue-500/30 focus-within:border-blue-600 bg-white transition">
          <div className="absolute left-4 text-slate-400">
            <Search className="w-5 h-5" />
          </div>
          <input
            type="text"
            value={inputQuery}
            onChange={(e) => setInputQuery(e.target.value)}
            placeholder="どんなデータが欲しいですか？（例: 富山県の土砂災害データ）"
            className="w-full pl-12 pr-32 py-4 text-sm sm:text-base text-slate-900 bg-transparent placeholder-slate-400 focus:outline-none"
            autoFocus
          />
          <button
            type="submit"
            disabled={!inputQuery.trim()}
            className="absolute right-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 text-white font-bold rounded-xl text-sm transition flex items-center space-x-2 shadow-sm"
          >
            <span>送信</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </form>

      {/* Suggestion Chips */}
      <div className="space-y-2">
        <p className="text-xs font-semibold text-slate-400 px-1">
          ワンクリックでお試し:
        </p>
        <div className="flex flex-wrap gap-2">
          {SUGGESTIONS.map((q, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => {
                setInputQuery(q);
                onSearch(q);
              }}
              className="text-xs bg-white hover:bg-blue-50 hover:text-blue-600 text-slate-700 font-medium px-3.5 py-2 rounded-xl border border-slate-200 hover:border-blue-200 transition shadow-sm"
            >
              {q}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
