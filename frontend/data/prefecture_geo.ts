export interface PrefectureGeoInfo {
  code: string;
  name: string;
  shortName: string;
  lat: number;
  lng: number;
  zoom: number;
  adjacentCodes: string[];
}

export interface DatasetItem {
  code: string;
  name: string;
  category: string;
  format: string;
}

export const PREFECTURE_GEO_DATA: Record<string, PrefectureGeoInfo> = {
  "00": { code: "00", name: "全国", shortName: "全国", lat: 36.5, lng: 137.5, zoom: 5, adjacentCodes: [] },
  "01": { code: "01", name: "北海道", shortName: "北海道", lat: 43.0642, lng: 141.3469, zoom: 7, adjacentCodes: ["02"] },
  "02": { code: "02", name: "青森県", shortName: "青森", lat: 40.8244, lng: 140.74, zoom: 8, adjacentCodes: ["01", "03", "05"] },
  "03": { code: "03", name: "岩手県", shortName: "岩手", lat: 39.7036, lng: 141.1527, zoom: 8, adjacentCodes: ["02", "04", "05"] },
  "04": { code: "04", name: "宮城県", shortName: "宮城", lat: 38.2688, lng: 140.8721, zoom: 8, adjacentCodes: ["03", "06", "07"] },
  "05": { code: "05", name: "秋田県", shortName: "秋田", lat: 39.7186, lng: 140.1024, zoom: 8, adjacentCodes: ["02", "03", "06"] },
  "06": { code: "06", name: "山形県", shortName: "山形", lat: 38.2404, lng: 140.3636, zoom: 8, adjacentCodes: ["04", "05", "07", "15"] },
  "07": { code: "07", name: "福島県", shortName: "福島", lat: 37.75, lng: 140.4678, zoom: 8, adjacentCodes: ["04", "06", "08", "09", "10", "15"] },
  "08": { code: "08", name: "茨城県", shortName: "茨城", lat: 36.3418, lng: 140.4468, zoom: 8, adjacentCodes: ["07", "09", "11", "12"] },
  "09": { code: "09", name: "栃木県", shortName: "栃木", lat: 36.5657, lng: 139.8836, zoom: 8, adjacentCodes: ["07", "08", "10", "11"] },
  "10": { code: "10", name: "群馬県", shortName: "群馬", lat: 36.3912, lng: 139.0608, zoom: 8, adjacentCodes: ["07", "09", "11", "15", "20"] },
  "11": { code: "11", name: "埼玉県", shortName: "埼玉", lat: 35.857, lng: 139.6489, zoom: 9, adjacentCodes: ["08", "09", "10", "12", "13", "19", "20"] },
  "12": { code: "12", name: "千葉県", shortName: "千葉", lat: 35.6051, lng: 140.1233, zoom: 8, adjacentCodes: ["08", "11", "13", "14"] },
  "13": { code: "13", name: "東京都", shortName: "東京", lat: 35.6895, lng: 139.6917, zoom: 9, adjacentCodes: ["11", "12", "14", "19"] },
  "14": { code: "14", name: "神奈川県", shortName: "神奈川", lat: 35.4475, lng: 139.6423, zoom: 9, adjacentCodes: ["12", "13", "19", "22"] },
  "15": { code: "15", name: "新潟県", shortName: "新潟", lat: 37.9026, lng: 139.0232, zoom: 8, adjacentCodes: ["06", "07", "10", "16", "20"] },
  "16": { code: "16", name: "富山県", shortName: "富山", lat: 36.6953, lng: 137.2113, zoom: 9, adjacentCodes: ["15", "17", "20", "21"] },
  "17": { code: "17", name: "石川県", shortName: "石川", lat: 36.5947, lng: 136.6256, zoom: 8, adjacentCodes: ["16", "18", "21"] },
  "18": { code: "18", name: "福井県", shortName: "福井", lat: 36.0652, lng: 136.2216, zoom: 8, adjacentCodes: ["17", "21", "25", "26"] },
  "19": { code: "19", name: "山梨県", shortName: "山梨", lat: 35.6639, lng: 138.5684, zoom: 8, adjacentCodes: ["11", "13", "14", "20", "22"] },
  "20": { code: "20", name: "長野県", shortName: "長野", lat: 36.6513, lng: 138.181, zoom: 8, adjacentCodes: ["10", "11", "15", "16", "19", "21", "22", "23"] },
  "21": { code: "21", name: "岐阜県", shortName: "岐阜", lat: 35.3912, lng: 136.7223, zoom: 8, adjacentCodes: ["16", "17", "18", "20", "22", "23", "24", "25"] },
  "22": { code: "22", name: "静岡県", shortName: "静岡", lat: 34.977, lng: 138.3831, zoom: 8, adjacentCodes: ["14", "19", "20", "23"] },
  "23": { code: "23", name: "愛知県", shortName: "愛知", lat: 35.1802, lng: 136.9066, zoom: 9, adjacentCodes: ["20", "21", "22", "24"] },
  "24": { code: "24", name: "三重県", shortName: "三重", lat: 34.7303, lng: 136.5086, zoom: 8, adjacentCodes: ["21", "23", "25", "26", "29", "30"] },
  "25": { code: "25", name: "滋賀県", shortName: "滋賀", lat: 35.0045, lng: 135.8686, zoom: 9, adjacentCodes: ["18", "21", "24", "26"] },
  "26": { code: "26", name: "京都府", shortName: "京都", lat: 35.0211, lng: 135.7556, zoom: 8, adjacentCodes: ["18", "24", "25", "27", "28", "29"] },
  "27": { code: "27", name: "大阪府", shortName: "大阪", lat: 34.6863, lng: 135.52, zoom: 9, adjacentCodes: ["26", "28", "29", "30"] },
  "28": { code: "28", name: "兵庫県", shortName: "兵庫", lat: 34.6913, lng: 135.183, zoom: 8, adjacentCodes: ["26", "27", "31", "33", "36"] },
  "29": { code: "29", name: "奈良県", shortName: "奈良", lat: 34.6853, lng: 135.8327, zoom: 8, adjacentCodes: ["24", "26", "27", "30"] },
  "30": { code: "30", name: "和歌山県", shortName: "和歌山", lat: 34.226, lng: 135.1675, zoom: 8, adjacentCodes: ["24", "27", "29", "36"] },
  "31": { code: "31", name: "鳥取県", shortName: "鳥取", lat: 35.5039, lng: 134.2383, zoom: 8, adjacentCodes: ["28", "32", "33", "34"] },
  "32": { code: "32", name: "島根県", shortName: "島根", lat: 35.4723, lng: 133.0505, zoom: 8, adjacentCodes: ["31", "34", "35"] },
  "33": { code: "33", name: "岡山県", shortName: "岡山", lat: 34.6618, lng: 133.9344, zoom: 8, adjacentCodes: ["28", "31", "34", "37"] },
  "34": { code: "34", name: "広島県", shortName: "広島", lat: 34.3966, lng: 132.4596, zoom: 8, adjacentCodes: ["31", "32", "33", "35", "38"] },
  "35": { code: "35", name: "山口県", shortName: "山口", lat: 34.1859, lng: 131.4714, zoom: 8, adjacentCodes: ["32", "34", "40", "44"] },
  "36": { code: "36", name: "徳島県", shortName: "徳島", lat: 34.0658, lng: 134.5594, zoom: 8, adjacentCodes: ["28", "30", "37", "38", "39"] },
  "37": { code: "37", name: "香川県", shortName: "香川", lat: 34.3401, lng: 134.0434, zoom: 9, adjacentCodes: ["33", "36", "38"] },
  "38": { code: "38", name: "愛媛県", shortName: "愛媛", lat: 33.8417, lng: 132.7661, zoom: 8, adjacentCodes: ["34", "36", "37", "39", "44"] },
  "39": { code: "39", name: "高知県", shortName: "高知", lat: 33.5597, lng: 133.5311, zoom: 8, adjacentCodes: ["36", "38"] },
  "40": { code: "40", name: "福岡県", shortName: "福岡", lat: 33.6068, lng: 130.4183, zoom: 8, adjacentCodes: ["35", "41", "43", "44"] },
  "41": { code: "41", name: "佐賀県", shortName: "佐賀", lat: 33.2494, lng: 130.2988, zoom: 9, adjacentCodes: ["40", "42"] },
  "42": { code: "42", name: "長崎県", shortName: "長崎", lat: 32.7448, lng: 129.8737, zoom: 8, adjacentCodes: ["41", "43"] },
  "43": { code: "43", name: "熊本県", shortName: "熊本", lat: 32.7898, lng: 130.7417, zoom: 8, adjacentCodes: ["40", "42", "44", "45", "46"] },
  "44": { code: "44", name: "大分県", shortName: "大分", lat: 33.2382, lng: 131.6126, zoom: 8, adjacentCodes: ["35", "38", "40", "43", "45"] },
  "45": { code: "45", name: "宮崎県", shortName: "宮崎", lat: 31.9111, lng: 131.4239, zoom: 8, adjacentCodes: ["43", "44", "46"] },
  "46": { code: "46", name: "鹿児島県", shortName: "鹿児島", lat: 31.5602, lng: 130.5581, zoom: 7, adjacentCodes: ["43", "45", "47"] },
  "47": { code: "47", name: "沖縄県", shortName: "沖縄", lat: 26.2124, lng: 127.6809, zoom: 8, adjacentCodes: ["46"] },
};

export const POPULAR_RELATED_DATASETS: DatasetItem[] = [
  { code: "GSI-DEM5A", name: "国土地理院 5m DEM", category: "標高・地形", format: "GeoJSON" },
  { code: "A33", name: "土砂災害警戒区域", category: "災害・防災", format: "GeoJSON" },
  { code: "A31", name: "浸水想定区域", category: "災害・防災", format: "GeoJSON" },
  { code: "G04-a", name: "標高・傾斜度", category: "地形", format: "GeoJSON" },
  { code: "P34", name: "避難施設", category: "防災", format: "GeoJSON" },
  { code: "P31", name: "医療機関", category: "施設", format: "GeoJSON" },
  { code: "P29", name: "学校", category: "施設", format: "GeoJSON" },
  { code: "L01", name: "地価公示", category: "土地・都市", format: "GeoJSON" },
  { code: "A29", name: "用途地域", category: "都市計画", format: "GeoJSON" },
  { code: "N03", name: "行政区域", category: "境界", format: "GML" },
];
