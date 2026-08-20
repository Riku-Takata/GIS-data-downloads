"use client";

import { useState } from "react";
import ChatView from "../components/ChatView";
import SearchingView from "../components/SearchingView";
import ResultMapView, { ProposalData, SelectedDownloadItem } from "../components/ResultMapView";
import DownloadingView from "../components/DownloadingView";
import CompletedView, { CompletedDownloadItem } from "../components/CompletedView";
import { AlertCircle } from "lucide-react";

type ViewStep = "chat" | "searching" | "result_map" | "downloading" | "completed";

const GAS_API_URL = process.env.NEXT_PUBLIC_GAS_API_URL;
const FASTAPI_URL = process.env.NEXT_PUBLIC_API_BASE_URL;

async function callBackendApi(action: "search" | "download", payload: Record<string, any>) {
  // If GAS Web App URL is configured, route all requests directly to GAS
  if (GAS_API_URL && GAS_API_URL.startsWith("http")) {
    const res = await fetch(GAS_API_URL, {
      method: "POST",
      headers: { "Content-Type": "text/plain;charset=utf-8" },
      body: JSON.stringify({ action, ...payload }),
    });

    if (!res.ok) {
      const errText = await res.text().catch(() => "");
      throw new Error(`GAS 通信エラー (${res.status}): ${errText}`);
    }

    const data = await res.json();
    if (data.status === "error") {
      throw new Error(data.detail || "GAS 処理中にエラーが発生しました。");
    }
    return data;
  }

  // Otherwise, route to FastAPI server
  const endpoint =
    FASTAPI_URL && FASTAPI_URL.startsWith("http")
      ? `${FASTAPI_URL.replace(/\/$/, "")}/api/${action}`
      : `/backend-api/${action}`;

  const res = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `バックエンド通信エラー (${res.status})`);
  }

  return res.json();
}

export default function Home() {
  const [viewStep, setViewStep] = useState<ViewStep>("chat");
  const [currentQuery, setCurrentQuery] = useState("");
  const [proposal, setProposal] = useState<ProposalData | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Multi-download queue state
  const [downloadQueue, setDownloadQueue] = useState<SelectedDownloadItem[]>([]);
  const [downloadIndex, setDownloadIndex] = useState(0);
  const [downloadMessage, setDownloadMessage] = useState("");
  const [completedItems, setCompletedItems] = useState<CompletedDownloadItem[]>([]);

  // 1. Trigger Search
  const handleSearch = async (query: string) => {
    setCurrentQuery(query);
    setErrorMessage(null);
    setViewStep("searching");

    try {
      const data = await callBackendApi("search", { query });
      if (data.status === "success" && data.proposal) {
        setProposal(data.proposal);
        setViewStep("result_map");
      } else {
        throw new Error("検索結果の特定に失敗しました。");
      }
    } catch (err: any) {
      setErrorMessage(err.message || "検索処理中にエラーが発生しました。");
      setViewStep("chat");
    }
  };

  // 2. Start Sequential Downloads for all selected items
  const handleStartDownload = async (items: SelectedDownloadItem[]) => {
    if (items.length === 0) return;

    setDownloadQueue(items);
    setDownloadIndex(0);
    setCompletedItems([]);
    setErrorMessage(null);
    setViewStep("downloading");

    const finished: CompletedDownloadItem[] = [];

    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      setDownloadIndex(i);
      setDownloadMessage(`「${item.pref_name} - ${item.data_name}」を取得中 (${i + 1}/${items.length})...`);

      try {
        const result = await callBackendApi("download", {
          data_code: item.data_code,
          pref_code: item.pref_code,
          year: item.year,
          format: item.format,
        });

        finished.push({
          id: `${item.id}_${Date.now()}`,
          data_code: item.data_code,
          pref_code: item.pref_code,
          region_name: item.pref_name,
          data_name: item.data_name,
          file_name: result.file_name,
          file_size_mb: result.file_size_mb,
          format: result.format || item.format,
          drive_web_view_link: result.drive_web_view_link,
          direct_download_url: result.direct_download_url,
          date_folder: result.google_drive?.date_folder,
        });
      } catch (err: any) {
        console.error(`Download failed for ${item.pref_name}`, err);
        // Continue downloading other items if one fails
      }
    }

    setCompletedItems(finished);
    setViewStep("completed");
  };

  // 3. Reset back to initial chat
  const handleResetToTop = () => {
    setViewStep("chat");
    setCurrentQuery("");
    setProposal(null);
    setDownloadQueue([]);
    setCompletedItems([]);
    setErrorMessage(null);
  };

  return (
    <div className="py-4">
      {/* Global Error Banner */}
      {errorMessage && (
        <div className="max-w-2xl mx-auto mb-6 p-4 rounded-2xl bg-rose-50 border border-rose-200 text-rose-700 text-sm flex items-start space-x-3 animate-fadeIn">
          <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5 text-rose-500" />
          <div className="space-y-0.5">
            <p className="font-bold">エラーが発生しました</p>
            <p className="text-xs">{errorMessage}</p>
          </div>
        </div>
      )}

      {/* Step 1: Initial Chat View */}
      {viewStep === "chat" && <ChatView onSearch={handleSearch} />}

      {/* Step 2: Searching Progress View */}
      {viewStep === "searching" && <SearchingView query={currentQuery} />}

      {/* Step 3: Result & Interactive Map View */}
      {viewStep === "result_map" && proposal && (
        <ResultMapView
          proposal={proposal}
          onStartDownload={handleStartDownload}
          onBackToChat={handleResetToTop}
        />
      )}

      {/* Step 4: Downloading Progress View */}
      {viewStep === "downloading" && (
        <DownloadingView
          items={downloadQueue}
          currentIndex={downloadIndex}
          currentMessage={downloadMessage}
        />
      )}

      {/* Step 5: Completed View */}
      {viewStep === "completed" && (
        <CompletedView
          completedItems={completedItems}
          onResetToTop={handleResetToTop}
        />
      )}
    </div>
  );
}
