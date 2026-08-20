"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import {
  Sparkles,
  MapPin,
  FileCode2,
  Calendar,
  Layers,
  FolderSync,
  Plus,
  Check,
  X,
  ArrowLeft,
  Info,
  BoxSelect,
  Sliders,
} from "lucide-react";
import { PREFECTURE_GEO_DATA, POPULAR_RELATED_DATASETS, DatasetItem } from "../data/prefecture_geo";
import { BoundingBoxGridItem, generateSurroundingBoundingBoxes } from "../data/mesh_grid";

// Dynamically import Leaflet GisMap to avoid SSR 'window is not defined' error
const DynamicGisMap = dynamic(() => import("./GisMap"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-[420px] bg-slate-100 rounded-2xl flex items-center justify-center text-slate-400 text-sm">
      地図データを読み込み中...
    </div>
  ),
});

export interface SelectedDownloadItem {
  id: string;
  data_code: string;
  data_name: string;
  pref_code: string;
  pref_name: string;
  provider_id?: string;
  provider_name?: string;
  year: string;
  format: string;
  isPrimary?: boolean;
  bbox_name?: string;
  approx_size_mb?: number;
}

export interface ProposalData {
  data_code: string;
  data_name: string;
  pref_code: string;
  pref_name: string;
  provider_id?: string;
  provider_name?: string;
  year: string;
  format: string;
  summary: string;
  confidence: number;
  location_name?: string | null;
  target_lat?: number | null;
  target_lng?: number | null;
}

interface ResultMapViewProps {
  proposal: ProposalData;
  onStartDownload: (items: SelectedDownloadItem[]) => void;
  onBackToChat: () => void;
}

export default function ResultMapView({
  proposal,
  onStartDownload,
  onBackToChat,
}: ResultMapViewProps) {
  const isGsi = (proposal.provider_id === "gsi") || proposal.data_code.startsWith("GSI-");
  const isElevationOrMesh = isGsi || proposal.data_code.startsWith("G04");
  const providerLabel = isGsi ? "国土地理院（基盤地図情報）" : "国土交通省（国土数値情報）";

  const primaryGeo = PREFECTURE_GEO_DATA[proposal.pref_code] || PREFECTURE_GEO_DATA["00"];
  const adjacentCodes = primaryGeo.adjacentCodes || [];

  const centerLat = (typeof proposal.target_lat === "number" && proposal.target_lat > 0)
    ? proposal.target_lat
    : primaryGeo.lat;
  const centerLng = (typeof proposal.target_lng === "number" && proposal.target_lng > 0)
    ? proposal.target_lng
    : primaryGeo.lng;

  // Generate 3x3 surrounding bounding boxes around target center for DEM / Mesh
  const boundingBoxes = isElevationOrMesh
    ? generateSurroundingBoundingBoxes(
        proposal.pref_code,
        proposal.pref_name,
        centerLat,
        centerLng,
        proposal.location_name || undefined
      )
    : [];

  const primaryBox = boundingBoxes.length > 0 ? boundingBoxes[0] : null;

  // Primary item
  const initialItem: SelectedDownloadItem = {
    id: isElevationOrMesh && primaryBox ? primaryBox.id : `${proposal.data_code}_${proposal.pref_code}`,
    data_code: proposal.data_code,
    data_name: isElevationOrMesh && primaryBox ? `${proposal.data_name} [${primaryBox.name}]` : proposal.data_name,
    pref_code: proposal.pref_code,
    pref_name: proposal.pref_name,
    provider_id: proposal.provider_id,
    provider_name: proposal.provider_name,
    year: proposal.year || "latest",
    format: proposal.format || "GeoJSON",
    isPrimary: true,
    bbox_name: primaryBox ? primaryBox.name : undefined,
    approx_size_mb: primaryBox ? primaryBox.approxSizeMb : undefined,
  };

  const [selectedItems, setSelectedItems] = useState<SelectedDownloadItem[]>([initialItem]);
  const [selectedPrefCodes, setSelectedPrefCodes] = useState<string[]>([proposal.pref_code]);
  const [selectedBboxIds, setSelectedBboxIds] = useState<string[]>(
    isElevationOrMesh && primaryBox ? [primaryBox.id] : []
  );

  // Toggle Bounding Box (for 5m DEM / Mesh)
  const toggleBoundingBox = (box: BoundingBoxGridItem) => {
    const exists = selectedItems.some((x) => x.id === box.id);

    if (exists) {
      if (selectedItems.length === 1) return; // keep at least 1
      setSelectedItems(selectedItems.filter((x) => x.id !== box.id));
      setSelectedBboxIds(selectedBboxIds.filter((id) => id !== box.id));
    } else {
      const newItem: SelectedDownloadItem = {
        id: box.id,
        data_code: proposal.data_code,
        data_name: `${proposal.data_name} [${box.name}]`,
        pref_code: proposal.pref_code,
        pref_name: proposal.pref_name,
        provider_id: proposal.provider_id,
        provider_name: proposal.provider_name,
        year: proposal.year || "latest",
        format: proposal.format || "GeoJSON",
        bbox_name: box.name,
        approx_size_mb: box.approxSizeMb,
      };
      setSelectedItems([...selectedItems, newItem]);
      setSelectedBboxIds([...selectedBboxIds, box.id]);
    }
  };

  // Toggle adjacent prefecture for the SAME dataset (Polygon mode)
  const toggleAdjacentPrefecture = (prefCode: string) => {
    const geo = PREFECTURE_GEO_DATA[prefCode];
    if (!geo) return;

    const itemId = `${proposal.data_code}_${prefCode}`;
    const exists = selectedItems.some((x) => x.id === itemId);

    if (exists) {
      setSelectedItems(selectedItems.filter((x) => x.id !== itemId));
      setSelectedPrefCodes(selectedPrefCodes.filter((c) => c !== prefCode));
    } else {
      const newItem: SelectedDownloadItem = {
        id: itemId,
        data_code: proposal.data_code,
        data_name: proposal.data_name,
        pref_code: prefCode,
        pref_name: geo.name,
        provider_id: proposal.provider_id,
        provider_name: proposal.provider_name,
        year: proposal.year || "latest",
        format: proposal.format || "GeoJSON",
      };
      setSelectedItems([...selectedItems, newItem]);
      setSelectedPrefCodes([...selectedPrefCodes, prefCode]);
    }
  };

  // Toggle related dataset in the SAME prefecture
  const toggleRelatedDataset = (ds: DatasetItem) => {
    const itemId = `${ds.code}_${proposal.pref_code}`;
    const exists = selectedItems.some((x) => x.id === itemId);

    if (exists) {
      setSelectedItems(selectedItems.filter((x) => x.id !== itemId));
    } else {
      const isDsGsi = ds.code.startsWith("GSI-");
      const newItem: SelectedDownloadItem = {
        id: itemId,
        data_code: ds.code,
        data_name: ds.name,
        pref_code: proposal.pref_code,
        pref_name: proposal.pref_name,
        provider_id: isDsGsi ? "gsi" : "mlit",
        provider_name: isDsGsi ? "国土地理院（基盤地図情報）" : "国土交通省（国土数値情報）",
        year: "latest",
        format: ds.format,
      };
      setSelectedItems([...selectedItems, newItem]);
    }
  };

  const removeItem = (id: string) => {
    const remaining = selectedItems.filter((x) => x.id !== id);
    setSelectedItems(remaining);
    // Update pref codes & bbox ids
    const prefCodes = remaining.map((x) => x.pref_code);
    setSelectedPrefCodes(Array.from(new Set(prefCodes)));
    setSelectedBboxIds(remaining.map((x) => x.id));
  };

  const handleDownloadClick = () => {
    if (selectedItems.length === 0) return;
    onStartDownload(selectedItems);
  };

  return (
    <div className="space-y-6 animate-fadeIn">
      {/* Top Bar with Back Button & Summary */}
      <div className="flex items-center justify-between pb-2 border-b border-slate-200">
        <button
          type="button"
          onClick={onBackToChat}
          className="inline-flex items-center space-x-1.5 text-xs font-semibold text-slate-600 hover:text-blue-600 transition px-3 py-1.5 rounded-lg hover:bg-slate-100"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>新しい条件で検索し直す</span>
        </button>
        <span className="text-xs text-slate-500 font-medium">
          検索結果 & {isElevationOrMesh ? "メッシュ・矩形範囲選択" : "周辺エリア選択"}
        </span>
      </div>

      {/* 2-Column Grid Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Text Proposal & Selected Queue (5 cols) */}
        <div className="lg:col-span-5 space-y-5">
          {/* Main Proposal Card */}
          <div className="bg-white rounded-2xl p-5 sm:p-6 shadow-sm border border-slate-200 space-y-4">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`px-2.5 py-0.5 rounded-md text-xs font-extrabold ${
                    isGsi
                      ? "bg-indigo-100 text-indigo-800"
                      : "bg-blue-100 text-blue-800"
                  }`}
                >
                  {proposal.data_code}
                </span>
                <span
                  className={`px-2.5 py-0.5 rounded-full text-xs font-bold border ${
                    isGsi
                      ? "bg-indigo-50 text-indigo-700 border-indigo-200"
                      : "bg-blue-50 text-blue-700 border-blue-200"
                  }`}
                >
                  {providerLabel}
                </span>
                <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800">
                  確信度: {Math.round(proposal.confidence * 100)}%
                </span>
              </div>
              <h3 className="text-xl font-extrabold text-slate-900 mt-2">
                {proposal.data_name}
              </h3>
              <p className="text-xs text-slate-600 mt-1 leading-relaxed">
                {proposal.summary}
              </p>
            </div>

            {/* Bounding box optimization notice for DEM */}
            {isElevationOrMesh && (
              <div className="p-3.5 bg-indigo-50/80 rounded-xl border border-indigo-100 text-xs space-y-1.5">
                <div className="flex items-center space-x-1.5 font-bold text-indigo-950">
                  <BoxSelect className="w-3.5 h-3.5 text-indigo-600" />
                  <span>国土地理院 3次メッシュ配信単位（約1km×1km区画）</span>
                </div>
                <p className="text-indigo-800 leading-relaxed text-[11px]">
                  5mメッシュ（DEM5A）は<strong>「5mピッチ（解像度）」</strong>のデータであり、国土地理院の公式配信単位は<strong>「3次メッシュ（約1km四方）」</strong>です。1区画の中に<strong>40,000点</strong>の標高値が含まれます（1区画 約0.35MB）。地図上の周囲枠をクリックして複数メッシュを選択できます。
                </p>
              </div>
            )}

            <div className="grid grid-cols-3 gap-2 text-xs bg-slate-50 p-3 rounded-xl border border-slate-100">
              <div>
                <p className="text-slate-400">地域</p>
                <p className="font-bold text-slate-800 mt-0.5">{proposal.pref_name}</p>
              </div>
              <div>
                <p className="text-slate-400">形式</p>
                <p className="font-bold text-blue-700 mt-0.5">{proposal.format}</p>
              </div>
              <div>
                <p className="text-slate-400">配信単位</p>
                <p className="font-bold text-indigo-700 mt-0.5">
                  {isElevationOrMesh ? "3次メッシュ (約1km)" : "都道府県単位"}
                </p>
              </div>
            </div>
          </div>

          {/* Selected Download Queue */}
          <div className="bg-white rounded-2xl p-5 sm:p-6 shadow-sm border border-slate-200 space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-bold text-slate-900 flex items-center space-x-1.5">
                <Layers className="w-4 h-4 text-blue-600" />
                <span>ダウンロード対象リスト</span>
              </h4>
              <span className="px-2 py-0.5 rounded-full text-xs font-extrabold bg-blue-50 text-blue-700 border border-blue-100">
                計 {selectedItems.length} 件
              </span>
            </div>

            {selectedItems.length === 0 ? (
              <p className="text-xs text-rose-500 py-3 text-center">
                ダウンロード対象が選択されていません。マップから追加してください。
              </p>
            ) : (
              <div className="divide-y divide-slate-100 max-h-56 overflow-y-auto pr-1">
                {selectedItems.map((item) => (
                  <div
                    key={item.id}
                    className="py-2.5 flex items-center justify-between text-xs group"
                  >
                    <div className="space-y-0.5">
                      <div className="flex items-center space-x-1.5">
                        <span className="font-bold text-slate-800">{item.pref_name}</span>
                        <span className="text-slate-600 font-medium">{item.data_name}</span>
                        {item.isPrimary && (
                          <span className="px-1.5 py-0.2 rounded bg-indigo-100 text-indigo-700 text-[10px] font-bold">
                            主区画
                          </span>
                        )}
                      </div>
                      <span className="text-slate-400 text-[11px]">
                        形式: {item.format} • {item.approx_size_mb ? `推定サイズ: 約 ${item.approx_size_mb} MB` : `年度: ${item.year}`}
                      </span>
                    </div>

                    <button
                      type="button"
                      onClick={() => removeItem(item.id)}
                      className="text-slate-300 hover:text-rose-500 p-1 transition"
                      title="リストから削除"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Action Download Button */}
            <button
              type="button"
              onClick={handleDownloadClick}
              disabled={selectedItems.length === 0}
              className="w-full py-3.5 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 disabled:from-slate-300 disabled:to-slate-300 text-white font-bold rounded-xl text-sm transition flex items-center justify-center space-x-2 shadow-md hover:shadow-lg transform active:scale-98"
            >
              <FolderSync className="w-4 h-4" />
              <span>選択したデータをダウンロード（{selectedItems.length}件）</span>
            </button>
          </div>

          {/* Related Datasets in the same region */}
          {proposal.pref_code !== "00" && (
            <div className="bg-slate-50 rounded-2xl p-4 border border-slate-200 space-y-2.5">
              <p className="text-xs font-bold text-slate-700 flex items-center space-x-1">
                <Info className="w-3.5 h-3.5 text-blue-500" />
                <span>{proposal.pref_name} の他の関連データも併せて選択:</span>
              </p>
              <div className="flex flex-wrap gap-1.5">
                {POPULAR_RELATED_DATASETS.filter((d) => d.code !== proposal.data_code).map((ds) => {
                  const isSelected = selectedItems.some((x) => x.data_code === ds.code);
                  return (
                    <button
                      key={ds.code}
                      type="button"
                      onClick={() => toggleRelatedDataset(ds)}
                      className={`text-xs px-2.5 py-1 rounded-lg border font-medium transition flex items-center space-x-1 ${
                        isSelected
                          ? "bg-emerald-600 text-white border-emerald-600 shadow-sm"
                          : "bg-white text-slate-700 border-slate-200 hover:border-blue-400 hover:bg-blue-50"
                      }`}
                    >
                      <span>{isSelected ? "✓" : "+"}</span>
                      <span>{ds.name}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Right Column: Interactive Map & Surroundings Strip (7 cols) */}
        <div className="lg:col-span-7 space-y-4">
          <DynamicGisMap
            primaryPrefCode={proposal.pref_code}
            dataCode={proposal.data_code}
            dataName={proposal.data_name}
            targetLat={proposal.target_lat}
            targetLng={proposal.target_lng}
            locationName={proposal.location_name}
            selectedPrefCodes={selectedPrefCodes}
            selectedBboxIds={selectedBboxIds}
            onTogglePrefecture={toggleAdjacentPrefecture}
            onToggleBbox={toggleBoundingBox}
          />

          {/* 1. Bounding Boxes Quick Selector Strip for DEM */}
          {isElevationOrMesh && boundingBoxes.length > 0 && (
            <div className="bg-white rounded-2xl p-4 shadow-sm border border-slate-200 space-y-2.5">
              <p className="text-xs font-bold text-slate-700 flex items-center space-x-1.5">
                <BoxSelect className="w-3.5 h-3.5 text-indigo-600" />
                <span>国土地理院 3次メッシュ区画（約1km四方 / 8桁コード）を選択:</span>
              </p>
              <div className="flex flex-wrap gap-2">
                {boundingBoxes.map((box) => {
                  const isSelected = selectedBboxIds.includes(box.id);
                  return (
                    <button
                      key={box.id}
                      type="button"
                      onClick={() => toggleBoundingBox(box)}
                      className={`text-xs px-3 py-1.5 rounded-xl border font-bold transition flex items-center space-x-1.5 shadow-sm ${
                        isSelected
                          ? "bg-emerald-600 text-white border-emerald-600 shadow-emerald-500/20"
                          : "bg-slate-50 text-slate-700 border-slate-200 hover:bg-indigo-50 hover:text-indigo-700 hover:border-indigo-300"
                      }`}
                    >
                      {isSelected ? <Check className="w-3.5 h-3.5" /> : <Plus className="w-3.5 h-3.5" />}
                      <span>{box.name}</span>
                      <span className="text-[10px] opacity-75 font-normal">({box.approxSizeMb}MB)</span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* 2. Adjacent Prefectures Quick Toggle Strip (for Polygon mode) */}
          {!isElevationOrMesh && adjacentCodes.length > 0 && (
            <div className="bg-white rounded-2xl p-4 shadow-sm border border-slate-200 space-y-2">
              <p className="text-xs font-bold text-slate-700 flex items-center space-x-1.5">
                <MapPin className="w-3.5 h-3.5 text-slate-500" />
                <span>周辺・隣接地域の「{proposal.data_name}」もワンクリック追加:</span>
              </p>
              <div className="flex flex-wrap gap-2">
                {adjacentCodes.map((code) => {
                  const geo = PREFECTURE_GEO_DATA[code];
                  if (!geo) return null;
                  const isSelected = selectedPrefCodes.includes(code);

                  return (
                    <button
                      key={code}
                      type="button"
                      onClick={() => toggleAdjacentPrefecture(code)}
                      className={`text-xs px-3 py-1.5 rounded-xl border font-bold transition flex items-center space-x-1.5 shadow-sm ${
                        isSelected
                          ? "bg-emerald-600 text-white border-emerald-600 shadow-emerald-500/20"
                          : "bg-slate-50 text-slate-700 border-slate-200 hover:bg-blue-50 hover:text-blue-700 hover:border-blue-300"
                      }`}
                    >
                      {isSelected ? <Check className="w-3.5 h-3.5" /> : <Plus className="w-3.5 h-3.5" />}
                      <span>{geo.name}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
