/**
 * JIS X 0410 標準地域メッシュ（3次メッシュ / 約1km×1km / 8桁コード）計算 & 動的グリッド生成
 * 国土地理院（基盤地図情報 DEM5A/DEM5B）の正式な配信単位に完全準拠。
 */

export interface BoundingBoxGridItem {
  id: string;
  code: string; // 8桁JISメッシュコード (例: 55370147)
  formattedCode: string; // 例: 5537-01-47
  name: string; // 代表地名またはメッシュコード
  pref_code: string;
  pref_name: string;
  meshLevel: "3次メッシュ (約1km四方)";
  resolution: "5mメッシュ (航空レーザ測量)";
  pointCount: number; // 40,000 点 (200x200)
  bounds: [[number, number], [number, number]]; // [[minLat, minLng], [maxLat, maxLng]]
  center: [number, number];
  isPrimary?: boolean;
  approxSizeMb: number;
}

/**
 * 緯度・経度から JIS 3次地域メッシュコード（8桁）および境界矩形を正確に計算
 */
export function latLngToJisMesh3(lat: number, lng: number): {
  meshCode8: string;
  formattedCode: string;
  bounds: [[number, number], [number, number]];
  center: [number, number];
} {
  const p = Math.floor(lat * 1.5);
  const u = Math.floor(lng - 100);

  const remLat1 = lat * 1.5 - p;
  const remLng1 = lng - 100 - u;

  const q = Math.floor(remLat1 * 8);
  const v = Math.floor(remLng1 * 8);

  const remLat2 = remLat1 * 8 - q;
  const remLng2 = remLng1 * 8 - v;

  const r = Math.floor(remLat2 * 10);
  const w = Math.floor(remLng2 * 10);

  const mesh1 = `${String(p).padStart(2, "0")}${String(u).padStart(2, "0")}`;
  const mesh2 = `${q}${v}`;
  const mesh3 = `${r}${w}`;
  const meshCode8 = `${mesh1}${mesh2}${mesh3}`;
  const formattedCode = `${mesh1}-${mesh2}-${mesh3}`;

  // 3次メッシュの境界緯度経度（緯度30秒 = 1/120度、経度45秒 = 1/80度）
  const minLat = p / 1.5 + (q * 5) / 60 + (r * 30) / 3600;
  const maxLat = minLat + 30 / 3600;
  const minLng = u + 100 + (v * 7.5) / 60 + (w * 45) / 3600;
  const maxLng = minLng + 45 / 3600;

  return {
    meshCode8,
    formattedCode,
    bounds: [
      [minLat, minLng],
      [maxLat, maxLng],
    ],
    center: [(minLat + maxLat) / 2, (minLng + maxLng) / 2],
  };
}

// Direction label offsets for initial 3x3 3rd-order mesh grid
const MESH3_GRID_OFFSETS = [
  { dx: 0, dy: 0, label: "中心区画 (中心1km)", isPrimary: true },
  { dx: 0, dy: 1, label: "北隣区画 (北1km)" },
  { dx: 1, dy: 1, label: "北東区画 (北東1.4km)" },
  { dx: 1, dy: 0, label: "東隣区画 (東1km)" },
  { dx: 1, dy: -1, label: "南東区画 (南東1.4km)" },
  { dx: 0, dy: -1, label: "南隣区画 (南1km)" },
  { dx: -1, dy: -1, label: "南西区画 (南西1.4km)" },
  { dx: -1, dy: 0, label: "西隣区画 (西1km)" },
  { dx: -1, dy: 1, label: "北西区画 (北西1.4km)" },
];

/**
 * 初期の中心点周辺の 3次メッシュ（3×3）を生成
 */
export function generateSurroundingBoundingBoxes(
  prefCode: string,
  prefName: string,
  centerLat: number,
  centerLng: number,
  locationName?: string
): BoundingBoxGridItem[] {
  const baseMesh = latLngToJisMesh3(centerLat, centerLng);
  const dLat = 30 / 3600;
  const dLng = 45 / 3600;

  const locLabel = locationName || prefName;

  return MESH3_GRID_OFFSETS.map((offset) => {
    const targetLat = baseMesh.center[0] + offset.dy * dLat;
    const targetLng = baseMesh.center[1] + offset.dx * dLng;

    const meshInfo = latLngToJisMesh3(targetLat, targetLng);
    const isPrimary = offset.dx === 0 && offset.dy === 0;

    return {
      id: `mesh3_${meshInfo.meshCode8}`,
      code: meshInfo.meshCode8,
      formattedCode: meshInfo.formattedCode,
      name: isPrimary ? `${locLabel} (${meshInfo.formattedCode})` : `${offset.label} (${meshInfo.formattedCode})`,
      pref_code: prefCode,
      pref_name: prefName,
      meshLevel: "3次メッシュ (約1km四方)",
      resolution: "5mメッシュ (航空レーザ測量)",
      pointCount: 40000,
      bounds: meshInfo.bounds,
      center: meshInfo.center,
      isPrimary,
      approxSizeMb: 0.35,
    };
  });
}

/**
 * 地図の現在表示領域（ビューポート）内にある 3次メッシュ（1km四方）を動的に網羅計算
 * 地図を日本全国どこへスクロール・移動しても、リアルタイムにメッシュを描画する。
 */
export function getMeshesInViewport(
  minLat: number,
  minLng: number,
  maxLat: number,
  maxLng: number,
  prefCode: string = "00",
  prefName: string = "全国",
  primaryCode?: string,
  maxCount: number = 49
): BoundingBoxGridItem[] {
  const dLat = 30 / 3600; // 0.008333 deg (~1km)
  const dLng = 45 / 3600; // 0.012500 deg (~1.1km)

  // Align start to 3rd mesh grid step
  const startMesh = latLngToJisMesh3(minLat, minLng);
  const endMesh = latLngToJisMesh3(maxLat, maxLng);

  const meshes: BoundingBoxGridItem[] = [];
  const seen = new Set<string>();

  for (let lat = startMesh.center[0]; lat <= endMesh.center[0] + dLat * 0.5; lat += dLat) {
    for (let lng = startMesh.center[1]; lng <= endMesh.center[1] + dLng * 0.5; lng += dLng) {
      if (meshes.length >= maxCount) break;

      const info = latLngToJisMesh3(lat, lng);
      if (seen.has(info.meshCode8)) continue;
      seen.add(info.meshCode8);

      const isPrimary = info.meshCode8 === primaryCode;

      meshes.push({
        id: `mesh3_${info.meshCode8}`,
        code: info.meshCode8,
        formattedCode: info.formattedCode,
        name: `メッシュ ${info.formattedCode}`,
        pref_code: prefCode,
        pref_name: prefName,
        meshLevel: "3次メッシュ (約1km四方)",
        resolution: "5mメッシュ (航空レーザ測量)",
        pointCount: 40000,
        bounds: info.bounds,
        center: info.center,
        isPrimary,
        approxSizeMb: 0.35,
      });
    }
  }

  return meshes;
}
