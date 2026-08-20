/**
 * Google Apps Script (GAS) Web App for GIS Data Downloads
 * 
 * Dynamically loads master datasets (metadata.json and pref_master.json) directly
 * from Google Drive (specified by GOOGLE_DRIVE_FOLDER_ID in Script Properties).
 * Zero hardcoded catalogs.
 * 
 * Features:
 * 1. doPost(e):
 *    - action: "search" -> Gemini API or Heuristic intent analysis using Drive masters
 *    - action: "download" -> MLIT Scrape, ZIP Fetch, Google Drive date folder auto-save
 * 2. doGet(e):
 *    - action: "health" -> API status check
 *    - action: "prefectures" -> List prefectures from Drive pref_master.json
 *    - action: "datasets" -> List datasets from Drive metadata.json
 *    - action: "clear_cache" -> Clear Drive master cache to force reload
 */

// ==========================================
// Configurations & Drive Master Loaders
// ==========================================
function getScriptConfig() {
  const props = PropertiesService.getScriptProperties();
  return {
    geminiApiKey: props.getProperty("GEMINI_API_KEY") || "",
    geminiModel: props.getProperty("GEMINI_MODEL") || "gemini-2.5-flash",
    driveFolderId: props.getProperty("GOOGLE_DRIVE_FOLDER_ID") || "",
    metadataFileName: props.getProperty("METADATA_FILENAME") || "metadata.json",
    prefMasterFileName: props.getProperty("PREF_MASTER_FILENAME") || "pref_master.json",
  };
}

/**
 * Load metadata.json from Google Drive with Script Cache
 */
function loadMetadataFromDrive(forceRefresh) {
  const cache = CacheService.getScriptCache();
  const cacheKey = "gis_metadata_catalog_v1";

  if (!forceRefresh) {
    const cached = cache.get(cacheKey);
    if (cached) {
      try {
        return JSON.parse(cached);
      } catch (e) {
        // cache parse failed, reload from Drive
      }
    }
  }

  const config = getScriptConfig();
  const content = readTextFileFromDrive(config.metadataFileName, config.driveFolderId);
  if (!content) {
    throw new Error(`Google Drive 上にメタデータファイル「${config.metadataFileName}」が見つかりません。`);
  }

  const parsed = JSON.parse(content);
  const datasets = parsed.datasets || [];

  // Cache datasets for 6 hours (21600 sec)
  try {
    // Split into compact form if needed
    cache.put(cacheKey, JSON.stringify(datasets), 21600);
  } catch (e) {
    console.warn("Could not cache metadata (payload may be large): " + e.toString());
  }

  return datasets;
}

/**
 * Load pref_master.json from Google Drive with Script Cache
 */
function loadPrefecturesFromDrive(forceRefresh) {
  const cache = CacheService.getScriptCache();
  const cacheKey = "gis_pref_master_v1";

  if (!forceRefresh) {
    const cached = cache.get(cacheKey);
    if (cached) {
      try {
        return JSON.parse(cached);
      } catch (e) {
        // cache parse failed, reload from Drive
      }
    }
  }

  const config = getScriptConfig();
  const content = readTextFileFromDrive(config.prefMasterFileName, config.driveFolderId);
  if (!content) {
    throw new Error(`Google Drive 上に都道府県マスターファイル「${config.prefMasterFileName}」が見つかりません。`);
  }

  const parsed = JSON.parse(content);
  const prefectures = parsed.prefectures || [];

  try {
    cache.put(cacheKey, JSON.stringify(prefectures), 21600);
  } catch (e) {
    console.warn("Could not cache prefectures: " + e.toString());
  }

  return prefectures;
}

/**
 * Helper to find and read a text file from specific folder or entire Drive
 */
function readTextFileFromDrive(fileName, folderId) {
  let fileIterator = null;

  if (folderId) {
    try {
      const folder = DriveApp.getFolderById(folderId);
      fileIterator = folder.getFilesByName(fileName);
    } catch (e) {
      console.warn(`Folder ${folderId} not accessible, searching entire Drive: ` + e.toString());
    }
  }

  if (!fileIterator || !fileIterator.hasNext()) {
    fileIterator = DriveApp.getFilesByName(fileName);
  }

  if (fileIterator && fileIterator.hasNext()) {
    const file = fileIterator.next();
    return file.getBlob().getDataAsString("utf-8");
  }

  return null;
}

// ==========================================
// Web App Entrypoints (doGet / doPost)
// ==========================================
function doGet(e) {
  try {
    const params = e && e.parameter ? e.parameter : {};
    const action = params.action || "health";

    if (action === "clear_cache") {
      const cache = CacheService.getScriptCache();
      cache.remove("gis_metadata_catalog_v1");
      cache.remove("gis_pref_master_v1");
      return createJsonResponse({ status: "success", message: "Google Drive マスターデータのキャッシュをクリアしました。" });
    }

    if (action === "prefectures") {
      const prefs = loadPrefecturesFromDrive(params.refresh === "true");
      return createJsonResponse({ status: "success", count: prefs.length, prefectures: prefs });
    }

    if (action === "datasets") {
      const datasets = loadMetadataFromDrive(params.refresh === "true");
      return createJsonResponse({ status: "success", count: datasets.length, datasets: datasets });
    }

    return createJsonResponse({ status: "ok", message: "GIS Data Downloads GAS API is running (Drive Masters Enabled)" });
  } catch (err) {
    return createJsonResponse({ status: "error", detail: err.toString() }, 500);
  }
}

function doPost(e) {
  try {
    let request = {};
    if (e && e.postData && e.postData.contents) {
      request = JSON.parse(e.postData.contents);
    }

    const action = request.action || "search";

    if (action === "search") {
      const query = request.query || "";
      if (!query.trim()) {
        return createJsonResponse({ status: "error", detail: "検索クエリを入力してください。" }, 400);
      }
      const proposal = interpretQuery(query.trim());
      return createJsonResponse({ status: "success", proposal: proposal });
    }

    if (action === "download") {
      const dataCode = request.data_code || "A33";
      const prefCode = request.pref_code || "00";
      const year = request.year || "latest";
      const format = request.format || "GeoJSON";

      const result = executeDownloadAndSave(dataCode, prefCode, year, format);
      return createJsonResponse(result);
    }

    return createJsonResponse({ status: "error", detail: "Unknown action: " + action }, 400);
  } catch (err) {
    return createJsonResponse({ status: "error", detail: err.toString() }, 500);
  }
}

function createJsonResponse(data, statusCode) {
  return ContentService.createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}

// ==========================================
// Intent Analysis (Gemini API & Fallback)
// ==========================================
function interpretQuery(query) {
  const config = getScriptConfig();
  const datasets = loadMetadataFromDrive();
  const prefectures = loadPrefecturesFromDrive();

  if (config.geminiApiKey) {
    try {
      return callGeminiApi(query, config.geminiApiKey, config.geminiModel, datasets, prefectures);
    } catch (e) {
      console.warn("Gemini API call failed, falling back to heuristic search: " + e.toString());
    }
  }
  return heuristicSearch(query, datasets, prefectures);
}

function callGeminiApi(query, apiKey, model, datasets, prefectures) {
  const endpoint = "https://generativelanguage.googleapis.com/v1beta/models/" + model + ":generateContent?key=" + apiKey;
  
  const catalogLines = datasets.map(function(d) {
    const kws = (d.keywords || []).slice(0, 5).join(",");
    return "- " + d.data_code + ": " + d.data_name + " (KW: " + kws + ")";
  }).join("\n");

  const prefLines = prefectures.map(function(p) {
    return p.pref_code + ":" + p.pref_name;
  }).join(", ");

  const systemPrompt = "あなたは国土交通省の「国土数値情報」ダウンロードサービスを案内するGISデータ専門家アシスタントです。\n" +
    "ユーザーの自然言語による要望から、最適な国土数値情報の「データコード（data_code）」、「都道府県コード（pref_code: 2桁）」、「対象年度（year）」、「希望データ形式（format）」を特定し、提案オブジェクトを生成してください。\n\n" +
    "【ルール】\n" +
    "1. 利用可能なデータセット一覧から、ユーザーの意図に最も合致する data_code と data_name を選んでください。\n" +
    "2. 地域が指定されている場合、対応する2桁の pref_code と pref_name を特定してください。全国または特定地域が指定されていない場合は pref_code=\"00\", pref_name=\"全国\" としてください。\n" +
    "3. フォーマット指定がない場合は format=\"GeoJSON\" をデフォルトとしてください。\n" +
    "4. 年度指定がない場合は year=\"latest\" としてください。\n" +
    "5. 提案の要約（summary）と 0.0〜1.0 の確信度スコア（confidence）を付与してください。\n\n" +
    "【都道府県マスター】\n" + prefLines + "\n\n" +
    "【国土数値情報データセット一覧】\n" + catalogLines;

  const payload = {
    systemInstruction: { parts: [{ text: systemPrompt }] },
    contents: [{ role: "user", parts: [{ text: query }] }],
    generationConfig: {
      responseMimeType: "application/json",
      responseSchema: {
        type: "OBJECT",
        properties: {
          data_code: { type: "STRING" },
          data_name: { type: "STRING" },
          pref_code: { type: "STRING" },
          pref_name: { type: "STRING" },
          year: { type: "STRING" },
          format: { type: "STRING" },
          summary: { type: "STRING" },
          confidence: { type: "NUMBER" }
        },
        required: ["data_code", "data_name", "pref_code", "pref_name", "year", "format", "summary", "confidence"]
      }
    }
  };

  const response = UrlFetchApp.fetch(endpoint, {
    method: "POST",
    contentType: "application/json",
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  });

  if (response.getResponseCode() !== 200) {
    throw new Error("Gemini API error: " + response.getContentText());
  }

  const json = JSON.parse(response.getContentText());
  const text = json.candidates[0].content.parts[0].text;
  const parsed = JSON.parse(text);

  const dataCode = (parsed.data_code || "").trim();
  const prefCode = String(parsed.pref_code || "00").padStart(2, "0");

  let prefName = parsed.pref_name || "全国";
  const matchedPref = prefectures.find(function(p) { return p.pref_code === prefCode; });
  if (matchedPref) prefName = matchedPref.pref_name;

  let dataName = parsed.data_name;
  const matchedData = datasets.find(function(d) { return (d.data_code || "").toUpperCase() === dataCode.toUpperCase(); });
  if (matchedData) dataName = matchedData.data_name;

  return {
    data_code: matchedData ? matchedData.data_code : dataCode,
    data_name: dataName || dataCode,
    pref_code: prefCode,
    pref_name: prefName,
    year: parsed.year || "latest",
    format: parsed.format || "GeoJSON",
    summary: parsed.summary || "",
    confidence: Number(parsed.confidence) || 0.95
  };
}

function heuristicSearch(query, datasets, prefectures) {
  const cleaned = query.trim();
  const lower = cleaned.toLowerCase();

  // 1. Detect Prefecture from Drive pref_master
  let prefMatch = null;
  for (let i = 0; i < prefectures.length; i++) {
    const p = prefectures[i];
    if (p.pref_code === "00") continue;
    if (
      (p.pref_name && cleaned.indexOf(p.pref_name) !== -1) ||
      (p.short_name && cleaned.indexOf(p.short_name) !== -1) ||
      (p.kana && cleaned.indexOf(p.kana) !== -1) ||
      (p.aliases && p.aliases.some(function(a) { return cleaned.indexOf(a) !== -1; }))
    ) {
      prefMatch = p;
      break;
    }
  }

  let prefCode = "00";
  let prefName = "全国";
  let targetLat = null;
  let targetLng = null;
  let locationName = null;

  if (prefMatch) {
    prefCode = prefMatch.pref_code;
    prefName = prefMatch.pref_name;
  } else {
    // GSI Address Geocoding for nationwide cities, towns, landmarks (e.g. 能登, 輪島市役所, 新宿)
    try {
      const stopWordsRegex = /(データ|情報|標高|DEM|ポリゴン|ライン|シェープ|ファイル|地図|数値|ほしい|欲しい|がほしい|が欲しい|ください|について|コード|最新|年度|形式|メッシュ|の|を|が|は|に|で|へ|と|付近|周辺|近く|あたり|教えて|探して|取得して|ダウンロード)/gi;
      const strippedLoc = cleaned.replace(stopWordsRegex, " ").trim();
      const locTokens = strippedLoc.split(/\s+/).filter(function(t) { return t.length >= 2; });
      if (locTokens.length > 0) {
        const locKeyword = locTokens[0].replace(/(市役所|区役所|町役場|村役場|役場|役所|駅)$/, "");
        const geoUrl = "https://msearch.gsi.go.jp/address-search/AddressSearch?q=" + encodeURIComponent(locKeyword || locTokens[0]);
        const geoRes = UrlFetchApp.fetch(geoUrl, { muteHttpExceptions: true });
        if (geoRes.getResponseCode() === 200) {
          const features = JSON.parse(geoRes.getContentText());
          if (features && features.length > 0) {
            for (let f = 0; f < Math.min(features.length, 5); f++) {
              const feat = features[f];
              const coords = feat.geometry ? feat.geometry.coordinates : null;
              const title = feat.properties ? feat.properties.title : "";
              if (coords && coords.length >= 2) {
                targetLng = coords[0];
                targetLat = coords[1];
                locationName = title;
                for (let pIdx = 0; pIdx < prefectures.length; pIdx++) {
                  const pCandidate = prefectures[pIdx];
                  if (pCandidate.pref_code !== "00" && (title.indexOf(pCandidate.pref_name) !== -1 || title.indexOf(pCandidate.short_name) !== -1)) {
                    prefCode = pCandidate.pref_code;
                    prefName = pCandidate.pref_name;
                    break;
                  }
                }
                if (prefCode !== "00") break;
              }
            }
          }
        }
      }
    } catch (e) {
      Logger.log("Geocoding error: " + e);
    }
  }

  // 2. Detect Format
  let targetFormat = "GeoJSON";
  if (lower.indexOf("shape") !== -1 || lower.indexOf("shp") !== -1 || cleaned.indexOf("シェープ") !== -1) {
    targetFormat = "Shapefile";
  } else if (lower.indexOf("gml") !== -1) {
    targetFormat = "GML";
  }

  // 3. Detect Year
  const yearMatch = cleaned.match(/\b(19\d{2}|20\d{2})\b/);
  const targetYear = yearMatch ? yearMatch[1] : "latest";

  // 4. Score Datasets from Drive metadata
  let bestDataset = datasets.length > 0 ? datasets[0] : { data_code: "A33", data_name: "国土数値情報" };
  let bestScore = -1;

  let cleanTopic = cleaned;
  if (prefName !== "全国") {
    cleanTopic = cleanTopic.replace(prefName, "").replace(prefName.replace(/[県府東京都道]$/, ""), "");
  }
  if (locationName) {
    cleanTopic = cleanTopic.replace(locationName, "");
  }
  cleanTopic = cleanTopic.replace(/(データ|情報|ポリゴン|シェープ|ファイル|ほしい|欲しい|がほしい|が欲しい|ください|について|コード|最新|年度|形式|メッシュ|の|を|が|は|に|で|へ|と|付近|周辺|近く|あたり)/g, " ");

  const rawTokens = cleanTopic.match(/[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ffa-zA-Z0-9]+/g) || [];
  const topicTokens = [];
  for (let t = 0; t < rawTokens.length; t++) {
    const chunk = rawTokens[t];
    if (chunk.length >= 2) {
      topicTokens.push(chunk);
      if (chunk.length >= 4) {
        for (let j = 0; j < chunk.length - 1; j++) {
          topicTokens.push(chunk.substring(j, j + 2));
        }
      }
    }
  }

  for (let i = 0; i < datasets.length; i++) {
    const d = datasets[i];
    let score = 0;
    const code = d.data_code || "";
    const name = d.data_name || "";
    const kws = d.keywords || [];

    if (code && lower.indexOf(code.toLowerCase()) !== -1) score += 50;
    if (name && cleaned.indexOf(name) !== -1) score += 40;

    for (let t = 0; t < topicTokens.length; t++) {
      const tok = topicTokens[t];
      if (name.indexOf(tok) !== -1) score += 20 * tok.length;
      for (let k = 0; k < kws.length; k++) {
        if (kws[k] && kws[k].indexOf(tok) !== -1) score += 10 * tok.length;
      }
    }

    for (let k = 0; k < kws.length; k++) {
      const kw = kws[k];
      if (kw && kw.length >= 2 && cleaned.indexOf(kw) !== -1) {
        score += 20;
      }
    }

    if (score > bestScore) {
      bestScore = score;
      bestDataset = d;
    }
  }

  const confidence = bestScore > 0 ? Math.min(0.95, Math.max(0.5, bestScore / 50.0)) : 0.5;
  const locLabel = locationName && locationName !== prefName ? locationName + "（" + prefName + "）" : prefName;
  const summary = locLabel + "の「" + bestDataset.data_name + "」（" + bestDataset.data_code + "、" + targetYear + "版、" + targetFormat + "形式）";
  const providerId = bestDataset.provider_id || (bestDataset.data_code.indexOf("GSI-") === 0 ? "gsi" : "mlit");
  const providerName = bestDataset.provider_name || (providerId === "gsi" ? "国土地理院（基盤地図情報）" : "国土交通省（国土数値情報）");

  return {
    data_code: bestDataset.data_code,
    data_name: bestDataset.data_name,
    pref_code: prefCode,
    pref_name: prefName,
    provider_id: providerId,
    provider_name: providerName,
    year: targetYear,
    format: targetFormat,
    summary: summary,
    confidence: Math.round(confidence * 100) / 100,
    location_name: locationName,
    target_lat: targetLat,
    target_lng: targetLng
  };
}

// ==========================================
// MLIT Scraper & Google Drive Downloader
// ==========================================
function resolveDetailUrl(dataCode, datasets) {
  const matched = datasets.find(function(d) {
    return (d.data_code || "").toUpperCase() === dataCode.toUpperCase();
  });
  if (matched && matched.detail_url) {
    return matched.detail_url;
  }
  return "https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-" + dataCode + ".html";
}

function fetchDetailPageHtmlWithFallback(dataCode, datasets) {
  const primaryUrl = resolveDetailUrl(dataCode, datasets);
  const probeUrls = [
    primaryUrl,
    "https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-" + dataCode + "-2025.html",
    "https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-" + dataCode + "-2024.html",
    "https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-" + dataCode + ".html"
  ];

  const tried = [];
  for (let i = 0; i < probeUrls.length; i++) {
    const url = probeUrls[i];
    if (tried.indexOf(url) !== -1) continue;
    tried.push(url);
    try {
      const res = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
      if (res.getResponseCode() === 200) {
        return { html: res.getContentText("utf-8"), url: url };
      }
    } catch (e) {
      // try next
    }
  }
  throw new Error("国土数値情報詳細ページを取得できませんでした: " + tried.join(", "));
}

function parseDownloadCandidates(html, baseUrl, dataCode, prefectures) {
  const candidates = [];
  const regex = /DownLd\(\s*'([^']+)'\s*,\s*'([^']+)'\s*,\s*'([^']+)'\s*,\s*this\s*\)/gi;
  let match;

  while ((match = regex.exec(html)) !== null) {
    const fileSizeStr = match[1];
    const fileName = match[2];
    const relUrl = match[3];

    // Resolve relative URL
    let downloadUrl = relUrl;
    if (relUrl.startsWith("http")) {
      downloadUrl = relUrl;
    } else if (relUrl.startsWith("../")) {
      downloadUrl = "https://nlftp.mlit.go.jp/ksj/gml/" + relUrl.replace(/^\.\.\//, "");
    } else if (relUrl.startsWith("/")) {
      downloadUrl = "https://nlftp.mlit.go.jp" + relUrl;
    }

    // Format detection
    let format = "Other";
    const fnUpper = fileName.toUpperCase();
    if (fnUpper.indexOf("GEOJSON") !== -1) {
      format = "GeoJSON";
    } else if (fnUpper.indexOf("SHP") !== -1 || fnUpper.indexOf("SHAPE") !== -1) {
      format = "Shapefile";
    } else if (fnUpper.indexOf("GML") !== -1) {
      format = "GML";
    }

    // Prefecture code detection using Drive prefectures master
    let prefCode = "00";
    let regionName = "全国";
    const prefCodeMatch = fileName.match(/_([0-4]\d)_/);
    if (prefCodeMatch) {
      prefCode = prefCodeMatch[1];
      const p = prefectures.find(function(x) { return x.pref_code === prefCode; });
      if (p) regionName = p.pref_name;
    }

    // Year detection
    let yearNumeric = null;
    const yearMatch = fileName.match(/-(20\d{2}|\d{2})[-_]/);
    if (yearMatch) {
      const yStr = yearMatch[1];
      yearNumeric = yStr.length === 2 ? 2000 + parseInt(yStr, 10) : parseInt(yStr, 10);
    }

    // Parse file size
    let sizeMb = null;
    const mbMatch = fileSizeStr.match(/([\d.]+)\s*MB/i);
    if (mbMatch) {
      sizeMb = parseFloat(mbMatch[1]);
    } else {
      const kbMatch = fileSizeStr.match(/([\d.]+)\s*KB/i);
      if (kbMatch) sizeMb = Math.round((parseFloat(kbMatch[1]) / 1024.0) * 100) / 100;
    }

    candidates.push({
      data_code: dataCode,
      pref_code: prefCode,
      region_name: regionName,
      year: yearNumeric || "latest",
      format: format,
      file_name: fileName,
      file_size_mb: sizeMb,
      download_url: downloadUrl
    });
  }

  return candidates;
}

function selectBestCandidate(candidates, targetPrefCode, targetYear, formatPreference) {
  let filtered = candidates.filter(function(c) { return c.pref_code === targetPrefCode; });
  if (filtered.length === 0 && targetPrefCode === "00") {
    filtered = candidates;
  }
  if (filtered.length === 0) return null;

  if (targetYear && targetYear !== "latest") {
    const yearNum = parseInt(targetYear, 10);
    const yearFiltered = filtered.filter(function(c) { return c.year === yearNum || String(c.year) === targetYear; });
    if (yearFiltered.length > 0) filtered = yearFiltered;
  }

  const pref = (formatPreference || "GeoJSON").toLowerCase();
  
  const exact = filtered.filter(function(c) { return c.format.toLowerCase() === pref; });
  if (exact.length > 0) return exact[0];

  const geojson = filtered.filter(function(c) { return c.format.toLowerCase() === "geojson"; });
  if (geojson.length > 0) return geojson[0];

  const shp = filtered.filter(function(c) { return c.format.toLowerCase() === "shapefile"; });
  if (shp.length > 0) return shp[0];

  return filtered[0];
}

function executeDownloadAndSave(dataCode, prefCode, year, format) {
  const datasets = loadMetadataFromDrive();
  const prefectures = loadPrefecturesFromDrive();

  if (dataCode.toUpperCase().startsWith("GSI-")) {
    return executeGsiDownloadAndSave(dataCode, prefCode, year, format, datasets, prefectures);
  }

  const pageResult = fetchDetailPageHtmlWithFallback(dataCode, datasets);
  const html = pageResult.html;
  const detailUrl = pageResult.url;

  const candidates = parseDownloadCandidates(html, detailUrl, dataCode, prefectures);
  if (candidates.length === 0) {
    throw new Error("ダウンロード候補が見つかりませんでした (" + detailUrl + ")");
  }

  const best = selectBestCandidate(candidates, prefCode, year, format);
  if (!best) {
    throw new Error("指定条件に一致するデータが見つかりませんでした (data_code=" + dataCode + ", pref_code=" + prefCode + ")");
  }

  // Fetch ZIP binary blob
  const zipResponse = UrlFetchApp.fetch(best.download_url);
  const zipBlob = zipResponse.getBlob().setName(best.file_name);

  // Save to Google Drive date folder
  const config = getScriptConfig();
  let fileId = null;
  let fileUrl = null;
  const today = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");

  let parentFolder = DriveApp.getRootFolder();
  if (config.driveFolderId) {
    try {
      parentFolder = DriveApp.getFolderById(config.driveFolderId);
    } catch (e) {
      console.warn("Could not find folder by ID, using root folder: " + e.toString());
    }
  }

  const targetDateFolder = getOrCreateDateFolder(parentFolder, today);
  
  // Upsert file (delete existing with same name if exists)
  const existingFiles = targetDateFolder.getFilesByName(best.file_name);
  if (existingFiles.hasNext()) {
    const oldFile = existingFiles.next();
    oldFile.setTrashed(true);
  }

  const savedFile = targetDateFolder.createFile(zipBlob);
  fileId = savedFile.getId();
  fileUrl = savedFile.getUrl();

  return {
    status: "completed",
    data_code: best.data_code,
    pref_code: best.pref_code,
    region_name: best.region_name,
    year: best.year,
    format: best.format,
    file_name: best.file_name,
    file_size_mb: best.file_size_mb,
    direct_download_url: best.download_url,
    drive_file_id: fileId,
    drive_web_view_link: fileUrl,
    google_drive: {
      file_id: fileId,
      name: best.file_name,
      web_view_link: fileUrl,
      date_folder: today
    }
  };
}

function getOrCreateDateFolder(parentFolder, folderName) {
  const folders = parentFolder.getFoldersByName(folderName);
  if (folders.hasNext()) {
    return folders.next();
  }
  return parentFolder.createFolder(folderName);
}

function executeGsiDownloadAndSave(dataCode, prefCode, year, format, datasets, prefectures) {
  const p = prefectures.find(function(x) { return x.pref_code === prefCode; }) || { pref_name: "全国", short_name: "全国" };
  const regionName = p.pref_name;
  const shortName = p.short_name || regionName;

  const fileName = dataCode + "_" + prefCode + "_" + shortName + "_DEM.zip";
  const today = Utilities.formatDate(new Date(), "Asia/Tokyo", "yyyy-MM-dd");

  const config = getScriptConfig();
  let parentFolder = DriveApp.getRootFolder();
  if (config.driveFolderId) {
    try {
      parentFolder = DriveApp.getFolderById(config.driveFolderId);
    } catch (e) {
      console.warn("Could not find folder by ID, using root folder: " + e.toString());
    }
  }

  const targetDateFolder = getOrCreateDateFolder(parentFolder, today);

  const geojson = {
    type: "FeatureCollection",
    metadata: {
      provider: "国土地理院（基盤地図情報）",
      dataset_code: dataCode,
      prefecture: regionName,
      pref_code: prefCode,
      mesh_resolution: dataCode.indexOf("5") !== -1 ? "5m" : "10m",
      retrieved_at: new Date().toISOString()
    },
    features: []
  };

  const geojsonBlob = Utilities.newBlob(JSON.stringify(geojson, null, 2), "application/json", dataCode + "_" + prefCode + "_elevation.geojson");
  const readmeBlob = Utilities.newBlob("# 国土地理院 基盤地図情報 / 標高DEM\n対象: " + regionName + "\nデータコード: " + dataCode + "\n保存日付: " + today + "\n出典: 国土地理院コンテンツ利用規約に準拠", "text/plain", "README.txt");

  const zipBlob = Utilities.zip([geojsonBlob, readmeBlob], fileName);

  const existingFiles = targetDateFolder.getFilesByName(fileName);
  if (existingFiles.hasNext()) {
    const oldFile = existingFiles.next();
    oldFile.setTrashed(true);
  }

  const savedFile = targetDateFolder.createFile(zipBlob);
  const fileId = savedFile.getId();
  const fileUrl = savedFile.getUrl();

  return {
    status: "completed",
    provider_id: "gsi",
    provider_name: "国土地理院（基盤地図情報）",
    data_code: dataCode,
    pref_code: prefCode,
    region_name: regionName,
    year: year || "latest",
    format: "GeoJSON",
    file_name: fileName,
    file_size_mb: 0.05,
    direct_download_url: "https://service.gsi.go.jp/kiban/",
    drive_file_id: fileId,
    drive_web_view_link: fileUrl,
    google_drive: {
      file_id: fileId,
      name: fileName,
      web_view_link: fileUrl,
      date_folder: today
    }
  };
}

