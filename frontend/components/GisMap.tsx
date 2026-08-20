"use client";

import { useEffect, useState, useCallback } from "react";
import { MapContainer, TileLayer, Marker, Popup, useMap, useMapEvents, Circle, Rectangle } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { PREFECTURE_GEO_DATA, PrefectureGeoInfo } from "../data/prefecture_geo";
import { BoundingBoxGridItem, generateSurroundingBoundingBoxes, getMeshesInViewport, latLngToJisMesh3 } from "../data/mesh_grid";
import { Plus, Check, MapPin, Layers, BoxSelect, Maximize2, Grid, Move } from "lucide-react";

// Controller to smoothly fly to center and zoom
function MapViewController({ center, zoom }: { center: [number, number]; zoom: number }) {
  const map = useMap();
  useEffect(() => {
    map.flyTo(center, zoom, { duration: 1.2 });
  }, [center, zoom, map]);
  return null;
}

// Dynamic mesh tracker: updates visible 3次メッシュ (1km) when user moves/zooms map
function ViewportMeshTracker({
  isElevationOrMesh,
  prefCode,
  prefName,
  primaryMeshCode,
  onMeshesUpdate,
}: {
  isElevationOrMesh: boolean;
  prefCode: string;
  prefName: string;
  primaryMeshCode?: string;
  onMeshesUpdate: (meshes: BoundingBoxGridItem[]) => void;
}) {
  const map = useMap();

  const updateVisibleMeshes = useCallback(() => {
    if (!isElevationOrMesh) return;
    const bounds = map.getBounds();
    const zoom = map.getZoom();

    // Only render 1km grid when zoomed in enough (zoom >= 11) to avoid performance lag
    if (zoom < 11) {
      onMeshesUpdate([]);
      return;
    }

    const meshes = getMeshesInViewport(
      bounds.getSouth(),
      bounds.getWest(),
      bounds.getNorth(),
      bounds.getEast(),
      prefCode,
      prefName,
      primaryMeshCode,
      64 // max visible meshes per viewport
    );
    onMeshesUpdate(meshes);
  }, [map, isElevationOrMesh, prefCode, prefName, primaryMeshCode, onMeshesUpdate]);

  useMapEvents({
    moveend: () => updateVisibleMeshes(),
    zoomend: () => updateVisibleMeshes(),
  });

  useEffect(() => {
    updateVisibleMeshes();
  }, [updateVisibleMeshes]);

  return null;
}

// Custom Leaflet DivIcon creator using HTML & Tailwind
function createCustomPin(
  text: string,
  isPrimary: boolean,
  isSelected: boolean,
  colorScheme: "primary" | "neighbor" | "bbox"
) {
  let bgClass = "bg-blue-600 border-white text-white shadow-blue-500/40";
  if (isSelected) {
    bgClass = "bg-emerald-600 border-white text-white shadow-emerald-500/50";
  } else if (colorScheme === "neighbor") {
    bgClass = "bg-slate-800 border-white text-white shadow-slate-900/40";
  } else if (colorScheme === "bbox") {
    bgClass = isSelected
      ? "bg-emerald-600 border-white text-white shadow-emerald-500/50"
      : isPrimary
      ? "bg-indigo-600 border-white text-white shadow-indigo-500/40"
      : "bg-slate-800/90 border-slate-300 text-slate-100 shadow-sm";
  }

  const html = `
    <div class="relative flex items-center justify-center cursor-pointer group">
      ${isPrimary && colorScheme !== "bbox" ? '<div class="absolute -inset-2 bg-blue-500/30 rounded-full animate-ping pointer-events-none"></div>' : ''}
      <div class="flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-bold shadow-md border ${bgClass} transition-transform transform group-hover:scale-110">
        <span>${isSelected ? '✓ ' : ''}${text}</span>
      </div>
    </div>
  `;

  return L.divIcon({
    html: html,
    className: "custom-leaflet-pin",
    iconSize: [110, 24],
    iconAnchor: [55, 12],
    popupAnchor: [0, -12],
  });
}

export interface GisMapProps {
  primaryPrefCode: string;
  dataCode: string;
  dataName: string;
  targetLat?: number | null;
  targetLng?: number | null;
  locationName?: string | null;
  selectedPrefCodes: string[];
  selectedBboxIds?: string[];
  onTogglePrefecture: (prefCode: string) => void;
  onToggleBbox?: (box: BoundingBoxGridItem) => void;
}

export default function GisMap({
  primaryPrefCode,
  dataCode,
  dataName,
  targetLat,
  targetLng,
  locationName,
  selectedPrefCodes,
  selectedBboxIds = [],
  onTogglePrefecture,
  onToggleBbox,
}: GisMapProps) {
  const isElevationOrMesh = dataCode.toUpperCase().startsWith("GSI-") || dataCode.toUpperCase().startsWith("G04");
  const primaryGeo = PREFECTURE_GEO_DATA[primaryPrefCode] || PREFECTURE_GEO_DATA["00"];
  const adjacentCodes = primaryGeo.adjacentCodes || [];

  // Determine exact center (specific geocoded coordinates > prefecture center)
  const centerLat = (typeof targetLat === "number" && targetLat > 0) ? targetLat : primaryGeo.lat;
  const centerLng = (typeof targetLng === "number" && targetLng > 0) ? targetLng : primaryGeo.lng;
  const center: [number, number] = [centerLat, centerLng];

  // Primary 3rd mesh at requested center
  const primaryMeshInfo = latLngToJisMesh3(centerLat, centerLng);
  const primaryMeshCode = primaryMeshInfo.meshCode8;

  // Zoom level: Zoom 14 for 1km 3次メッシュ view, Zoom 8 for prefecture overview
  const zoom = isElevationOrMesh ? 14 : (primaryGeo.zoom || 8);

  // Initial fallback 3x3 meshes around center
  const initialMeshes = isElevationOrMesh
    ? generateSurroundingBoundingBoxes(primaryPrefCode, primaryGeo.name, centerLat, centerLng, locationName || undefined)
    : [];

  const [visibleMeshes, setVisibleMeshes] = useState<BoundingBoxGridItem[]>(initialMeshes);

  // Update visible meshes callback from ViewportMeshTracker
  const handleMeshesUpdate = useCallback((meshes: BoundingBoxGridItem[]) => {
    if (meshes.length > 0) {
      setVisibleMeshes(meshes);
    }
  }, []);

  return (
    <div className="relative w-full h-[420px] sm:h-[480px] rounded-2xl overflow-hidden border border-slate-200 shadow-inner">
      <MapContainer
        center={center}
        zoom={zoom}
        scrollWheelZoom={true}
        className="w-full h-full z-10"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <MapViewController center={center} zoom={zoom} />

        <ViewportMeshTracker
          isElevationOrMesh={isElevationOrMesh}
          prefCode={primaryPrefCode}
          prefName={primaryGeo.name}
          primaryMeshCode={primaryMeshCode}
          onMeshesUpdate={handleMeshesUpdate}
        />

        {/* 1. Dynamic 3rd-Order Mesh Grid Mode (国土地理院 3次メッシュ / 約1km×1km) */}
        {isElevationOrMesh &&
          visibleMeshes.map((box) => {
            const isPrimary = box.code === primaryMeshCode || box.isPrimary;
            const isSelected: boolean = Boolean(
              selectedBboxIds.includes(box.id) || (isPrimary && selectedBboxIds.length === 0)
            );

            return (
              <div key={box.id}>
                <Rectangle
                  bounds={box.bounds}
                  pathOptions={{
                    color: isSelected ? "#059669" : isPrimary ? "#4f46e5" : "#64748b",
                    weight: isSelected ? 3.5 : isPrimary ? 3 : 1.5,
                    dashArray: isPrimary || isSelected ? undefined : "4 4",
                    fillColor: isSelected ? "#10b981" : isPrimary ? "#6366f1" : "#94a3b8",
                    fillOpacity: isSelected ? 0.35 : isPrimary ? 0.25 : 0.08,
                  }}
                  eventHandlers={{
                    click: () => onToggleBbox && onToggleBbox(box),
                  }}
                />

                <Marker
                  position={box.center}
                  icon={createCustomPin(
                    box.formattedCode,
                    Boolean(isPrimary),
                    isSelected,
                    "bbox"
                  )}
                  eventHandlers={{
                    click: () => onToggleBbox && onToggleBbox(box),
                  }}
                >
                  <Popup>
                    <div className="text-xs p-1 space-y-1.5 min-w-[200px]">
                      <div className="flex items-center justify-between border-b pb-1">
                        <span className="font-bold text-slate-900">{box.formattedCode}</span>
                        <span className="px-1.5 py-0.5 rounded bg-indigo-100 text-indigo-800 text-[10px] font-bold">
                          3次メッシュ (約1km四方)
                        </span>
                      </div>
                      <p className="text-slate-600 font-medium">
                        {isPrimary ? (locationName ? `${locationName} 付近` : "提案の中心区画") : box.name}
                      </p>
                      <div className="space-y-0.5 text-[11px] text-slate-500 bg-slate-50 p-1.5 rounded">
                        <p>• 標高解像度: <strong>5m間隔 (航空レーザ)</strong></p>
                        <p>• 区画内標高点数: <strong>40,000 点</strong> (200×200)</p>
                        <p>• データサイズ: <strong>約 {box.approxSizeMb} MB</strong></p>
                      </div>
                      {onToggleBbox && (
                        <button
                          type="button"
                          onClick={() => onToggleBbox(box)}
                          className={`mt-1 w-full px-2.5 py-1 rounded text-xs font-bold text-white transition shadow-sm ${
                            isSelected ? "bg-rose-600 hover:bg-rose-700" : "bg-emerald-600 hover:bg-emerald-700"
                          }`}
                        >
                          {isSelected ? "選択を解除" : "+ この1kmメッシュを追加"}
                        </button>
                      )}
                    </div>
                  </Popup>
                </Marker>
              </div>
            );
          })}

        {/* 2. Standard Prefecture Mode (for Polygon/Line MLIT datasets) */}
        {!isElevationOrMesh && (
          <>
            {primaryPrefCode !== "00" && (
              <Circle
                center={center}
                radius={28000}
                pathOptions={{
                  color: "#2563eb",
                  fillColor: "#3b82f6",
                  fillOpacity: 0.15,
                  weight: 2,
                  dashArray: "4 4",
                }}
              />
            )}

            <Marker
              position={center}
              icon={createCustomPin(
                locationName || primaryGeo.shortName,
                true,
                selectedPrefCodes.includes(primaryPrefCode),
                "primary"
              )}
            >
              <Popup>
                <div className="text-xs p-1">
                  <p className="font-bold text-slate-900">{locationName || primaryGeo.name}</p>
                  <p className="text-blue-600 font-medium mt-0.5">{dataName} ({dataCode})</p>
                  <p className="text-slate-500 mt-1">選択中のメイン地域</p>
                </div>
              </Popup>
            </Marker>

            {adjacentCodes.map((code) => {
              const geo = PREFECTURE_GEO_DATA[code];
              if (!geo) return null;
              const isSelected = selectedPrefCodes.includes(code);

              return (
                <Marker
                  key={code}
                  position={[geo.lat, geo.lng]}
                  icon={createCustomPin(geo.shortName, false, isSelected, "neighbor")}
                  eventHandlers={{
                    click: () => onTogglePrefecture(code),
                  }}
                >
                  <Popup>
                    <div className="text-xs p-1 space-y-1">
                      <p className="font-bold text-slate-900">{geo.name}（周辺・隣接地域）</p>
                      <p className="text-slate-600">この地域の「{dataName}」も取得対象に追加できます。</p>
                      <button
                        type="button"
                        onClick={() => onTogglePrefecture(code)}
                        className={`mt-1.5 w-full px-2.5 py-1 rounded text-xs font-bold text-white transition ${
                          isSelected ? "bg-rose-600 hover:bg-rose-700" : "bg-emerald-600 hover:bg-emerald-700"
                        }`}
                      >
                        {isSelected ? "選択を解除" : "+ 追加ダウンロードする"}
                      </button>
                    </div>
                  </Popup>
                </Marker>
              );
            })}
          </>
        )}
      </MapContainer>

      {/* Overlay legend badge with interactive drag helper */}
      <div className="absolute top-3 left-3 z-[400] bg-white/95 backdrop-blur px-3 py-2 rounded-xl shadow-md border border-slate-200 text-xs space-y-1 max-w-[320px]">
        <div className="flex items-center space-x-2 font-bold text-slate-800">
          {isElevationOrMesh ? (
            <Grid className="w-3.5 h-3.5 text-indigo-600" />
          ) : (
            <Layers className="w-3.5 h-3.5 text-blue-600" />
          )}
          <span>
            {isElevationOrMesh ? "国土地理院 3次メッシュ動的選択 (約1km四方)" : "周辺エリア選択マップ"}
          </span>
        </div>
        <p className="text-[11px] text-slate-500 leading-tight">
          {isElevationOrMesh
            ? "🗺️ 地図をドラッグ・移動すると、移動先の1kmメッシュが動的に表示されます。クリックで自由に選択できます。"
            : "ピンをクリックすると周辺地域のデータも一括追加できます"}
        </p>
        <div className="flex items-center space-x-3 text-[11px] pt-0.5">
          <span className="flex items-center space-x-1 text-indigo-700 font-medium">
            <span className="w-2 h-2 rounded-sm bg-indigo-600"></span>
            <span>主提案</span>
          </span>
          <span className="flex items-center space-x-1 text-emerald-700 font-medium">
            <span className="w-2 h-2 rounded-sm bg-emerald-600"></span>
            <span>選択中</span>
          </span>
          <span className="flex items-center space-x-1 text-slate-600 font-medium">
            <span className="w-2 h-2 rounded-sm border border-slate-400 border-dashed bg-slate-100"></span>
            <span>表示メッシュ</span>
          </span>
        </div>
      </div>
    </div>
  );
}
