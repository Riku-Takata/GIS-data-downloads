# **国土数値情報ポリゴン自動検索・取得システム（Webアプリ版）基本設計書**

本システムは、ユーザーが自然言語で入力した要求からGemini APIを用いて適切な国土数値情報を特定・提案し、Webインターフェース上で承認されたデータをバックエンド経由で自動取得（スクレイピング・ダウンロード）してGoogle Driveに保存・提供するWebアプリケーションです。

## **1\. システム全体構成**

Plaintext  
\[ユーザー (Webブラウザ)\]  
   │  
   │ 1\. 検索プロンプト入力 (例: 「富山県の土砂災害データ」)  
   ▼  
\[フロントエンド UI (React / Streamlit / HTML+JS)\]  
   │  
   │ 2\. APIリクエスト (POST /api/search)  
   ▼  
\[バックエンド API サーバー (Python: FastAPI / Flask)\]  
   │  
   │ 3\. 意図解釈・メタデータ照合  
   ▼  
\[Gemini API (Structured Outputs)\]  
   │  
   │ 4\. 抽出パラメータ (data\_code, pref\_code, year等) を返却  
   ▼  
\[フロントエンド UI\]  
   │  
   │ 5\. 候補データの提示 & ユーザーによる「ダウンロード実行」ボタン押下  
   ▼  
\[バックエンド API サーバー\]  
   │  
   │ 6\. スクレイピング & ZIPダウンロード実行  
   ▼  
\[国土数値情報サイト (nlftp.mlit.go.jp)\]  
   │  
   │ 7\. ファイル保存・メタデータ更新  
   ▼  
\[Google Drive & GAS (Google Apps Script) / Drive API\]  
   │  
   │ 8\. ダウンロード完了通知 / Google Drive共有リンク返却  
   ▼  
\[フロントエンド UI (ユーザー)\]

## **2\. アーキテクチャと使用技術一覧**

| レイヤー / 項目 | 選定技術・サービス | 役割・選定理由 |
| :---- | :---- | :---- |
| **ソースコード管理** | GitHub (Riku-Takata/GIS-data-downloads) | コードのバージョン管理、Issue/PR管理、CI/CD連携 |
| **フロントエンド** | HTML5/CSS3/JavaScript (または Streamlit) | ユーザーの検索入力、提案結果の確認、ダウンロード進捗・結果表示 |
| **バックエンド** | Python (FastAPI / requests / BeautifulSoup) | REST APIエンドポイント提供、Webスクレイピング、非同期ダウンロード制御 |
| **生成AI / 意図解析** | Gemini API (gemini-1.5-flash / gemini-1.5-pro) | ユーザーの曖昧なプロンプトから国土数値情報の種別・対象地域コードを高精度に抽出 |
| **クラウドストレージ** | Google Drive (Google Drive API / サービスアカウント) | 取得したZIPファイルやGeoJSONの保管先、ユーザーへの共有リンク生成 |
| **自動化・連携** | GAS (Google Apps Script) | Google Drive上のファイル整理、スプレッドシート連携（ログ・ダウンロード履歴管理） |

## **3\. ディレクトリ構成（GitHubリポジトリ構造）**

Plaintext  
GIS-data-downloads/  
├── .github/  
│   └── workflows/              \# GitHub Actions (CI/CD)  
├── backend/  
│   ├── app/  
│   │   ├── \_\_init\_\_.py  
│   │   ├── main.py             \# FastAPI エントリーポイント  
│   │   ├── config.py           \# 環境変数 (GEMINI\_API\_KEY, GOOGLE\_CREDS等)  
│   │   ├── services/  
│   │   │   ├── gemini\_service.py   \# Gemini API 連携・プロンプト制御  
│   │   │   ├── scraper\_service.py  \# 国土数値情報スクレイピング & DL  
│   │   │   └── drive\_service.py    \# Google Drive API 連携  
│   │   ├── models/  
│   │   │   └── schemas.py          \# Pydantic スキーマ定義  
│   │   └── data/  
│   │       ├── metadata.json       \# 国土数値情報定義マスター  
│   │       └── pref\_master.json    \# 都道府県コード対応表  
│   ├── scripts/  
│   │   └── update\_metadata.py  \# 国土数値情報サイトから最新metadata.jsonを自動生成  
│   ├── requirements.txt  
│   └── Dockerfile  
├── frontend/  
│   ├── index.html              \# Web UI インターフェース  
│   ├── app.js                  \# API通信・UIロジック  
│   └── style.css  
├── gas/  
│   └── Code.gs                 \# Drive内ファイル管理・履歴記録用 Apps Script  
├── .env.example  
├── .gitignore  
└── README.md

## **4\. APIエンドポイント定義**

### **POST /api/search**

ユーザーの自然言語入力を受け取り、Geminiを用いて対象の国土数値情報メタデータを抽出・提案します。

* **Request Body:**  
  JSON  
  {  
    "query": "富山県の土砂災害警戒区域のShapefileがほしい"  
  }

* **Response Body (Success):**  
  JSON  
  {  
    "status": "success",  
    "proposal": {  
      "data\_code": "A33",  
      "data\_name": "土砂災害警戒区域データ",  
      "pref\_code": "16",  
      "pref\_name": "富山県",  
      "year": "latest",  
      "format": "Shapefile",  
      "summary": "富山県の土砂災害防止法に基づく警戒区域ポリゴンデータ（最新版）",  
      "confidence": 0.98  
    }  
  }

### **POST /api/download**

ユーザーが提案内容を承認（ボタンクリック）した際に呼び出し、実際のスクレイピング・ダウンロードおよびDrive保存を実行します。

* **Request Body:**  
  JSON  
  {  
    "data\_code": "A33",  
    "pref\_code": "16",  
    "year": "latest"  
  }

* **Response Body (Success):**  
  JSON  
  {  
    "status": "completed",  
    "file\_name": "A33-22\_16\_GML.zip",  
    "file\_size\_mb": 14.2,  
    "drive\_file\_id": "1abcXYZ...",  
    "drive\_web\_view\_link": "https://drive.google.com/file/d/1abcXYZ/view?usp=sharing",  
    "direct\_download\_url": "https://nlftp.mlit.go.jp/ksj/gml/data/A33/A33-22/A33-22\_16\_GML.zip"  
  }

## **5\. 各モジュール設計詳細**

### **① Gemini 意図解析モジュール (gemini\_service.py)**

* metadata.json（識別コード、名称、キーワード一覧）と都道府県マスターをプロンプトのコンテキストとして与えます。  
* Geminiの response\_schema（Structured Outputs）を使用し、data\_code, pref\_code, year を厳密なJSON型で抽出します。

### **② スクレイパー & ダウンローダー (scraper\_service.py)**

* 対象データ種別の詳細ページ（\[https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-\](https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-){data\_code}.html）を BeautifulSoup でパース。  
* 指定された都道府県コード（pref\_code）に対応する行から最新の .zip リンクを抽出してダウンロード。

### **③ Google Drive & GAS連携モジュール (drive\_service.py / Code.gs)**

* Pythonバックエンドから Google Drive API（サービスアカウント）経由で指定のルートフォルダへZIPをアップロード。  
* GAS側で新規ファイル作成トリガーを設定し、Googleスプレッドシートへのダウンロード履歴自動追記やフォルダ自動整理を実行。

## **6\. 実装フェーズ・ロードマップ**

> 1. **Phase 1: マスター作成バッチ**  
   * 国土数値情報サイトの全データ一覧から metadata.json を生成するスクリプトの実装。  
> 2. **Phase 2: バックエンドコア実装**  
   * スクレイピングダウンロード関数（scraper\_service.py）  
   * Geminiパラメータ抽出関数（gemini\_service.py）  
   * Google Drive API アップロード関数（drive\_service.py）  
> 3. **Phase 3: Web API & フロントエンド実装**  
   * FastAPIによるエンドポイント作成  
   * 検索・提案・ダウンロード完了を表示するUI画面の作成  
> 4. **Phase 4: GitHubリポジトリ連携 & GAS整備**  
   * リポジトリへのプッシュ、GASスプレッドシート連携スクリプトの配置