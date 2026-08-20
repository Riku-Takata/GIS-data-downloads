# GIS-data-downloads

自然言語から国土数値情報を検索し、取得したデータをGoogle Driveへ保存するWebアプリケーションのバックエンドです。

現在は最初の実装として、国土交通省の国土数値情報一覧から検索用メタデータを生成し、Google Drive上の `metadata.json` を作成または更新するバッチを提供します。

## 実装済みの範囲

- 国土数値情報の公式一覧ページからデータコード、名称、分類、キーワード、詳細URLを抽出
- UTF-8の `backend/app/data/metadata.json` を原子的に更新
- JIS X 0401準拠の全国および47都道府県マスター（`backend/app/data/pref_master.json`）の生成・管理
- 自然言語プロンプトからの意図解析・国土数値情報データ提案（Gemini API Structured Outputs & 高度なキーワード照合フォールバック）
- 国土数値情報のスクレイピング・ZIPダウンロード（GeoJSON優先・自動フォールバック対応）
- Google Driveの指定フォルダ（日付別サブフォルダ含む）への自動アップロード・更新
- サービスアカウント、ユーザーOAuth、Application Default Credentials、Google Workspaceのドメイン全体の委任に対応

## セットアップ

Python 3.11以降を使用します。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
cp .env.example .env
```

`.env` の以下の値を環境に合わせて設定してください。

- `GOOGLE_APPLICATION_CREDENTIALS`: サービスアカウントまたはユーザーOAuth認証JSONの絶対パス
- `GOOGLE_DRIVE_FOLDER_ID`: `metadata.json` を保存するフォルダID
- `GOOGLE_DRIVE_SHARED_DRIVE_ID`: 保存先が共有ドライブの場合のドライブID（任意）
- `GOOGLE_DRIVE_IMPERSONATE_USER`: ドメイン全体の委任で代理するユーザー（任意）

認証JSONや `.env` はGit管理対象外です。

### 認証方式の選択

- 共有ドライブ: サービスアカウントを共有ドライブのメンバーに追加します。
- Google Workspaceのユーザー領域: ドメイン全体の委任と `GOOGLE_DRIVE_IMPERSONATE_USER` を使用できます。
- 個人のマイドライブ: ユーザーOAuth認証を使用します。サービスアカウントには保存容量がないため、共有されたマイドライブのフォルダへ新規ファイルを所有することはできません。

個人のマイドライブを使用する場合は、Google Cloud Consoleで「デスクトップアプリ」のOAuthクライアントを作成し、ダウンロードしたクライアントJSONを指定して一度だけ認可します。この認可では、設定済みの既存フォルダへアクセスするためGoogle Drive全体のスコープを要求します。バッチ処理は `GOOGLE_DRIVE_FOLDER_ID` で指定したフォルダ内の `metadata.json` だけを検索・作成・更新します。

```bash
python backend/scripts/authorize_drive.py \
  --client-secrets /absolute/path/to/client_secret.json \
  --output credentials/authorized-user.json
```

認可後、`.env` を次のように変更します。

```dotenv
GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/project/credentials/authorized-user.json
GOOGLE_DRIVE_FOLDER_ID=YOUR_FOLDER_ID
```

## 実行方法

ローカルのメタデータだけを更新します。

```bash
python backend/scripts/update_metadata.py
```

ローカル更新後、Google Driveにも保存します。

```bash
python backend/scripts/update_metadata.py --upload-drive
```

保存先やファイル名はコマンドラインでも上書きできます。

```bash
python backend/scripts/update_metadata.py \
  --upload-drive \
  --drive-folder-id "YOUR_FOLDER_ID" \
  --drive-file-name "metadata.json"
```

同じフォルダに同名ファイルがある場合は内容を更新するため、定期実行してもファイルが重複しません。

### 都道府県マスターの生成

都道府県マスター（全国 + 47都道府県）をローカルに生成します。

```bash
python backend/scripts/generate_pref_master.py
```

Google Driveにも保存する場合：

```bash
python backend/scripts/generate_pref_master.py --upload-drive
```

### 自然言語による国土数値情報データの検索・提案

自然言語のプロンプトから適切なデータ種別・都道府県・年度・フォーマットを解析・提案します。

```bash
python backend/scripts/search_data.py "富山県の土砂災害データ"
python backend/scripts/search_data.py "全国の行政区域 GML 2024"
```

### 国土数値情報データのダウンロード

データコードと都道府県コード等を指定してダウンロードします。
- **フォーマット優先度**: デフォルトで **GeoJSON** を優先的にダウンロードし、提供されていないデータセットの場合は Shapefile / GML などへ自動フォールバックします（`--format` で明示指定も可能）。
- **保存先**: ローカルおよび Google Drive 上で実行日（`YYYY-MM-DD`）のサブフォルダ内に自動整理されて保存されます。

```bash
# 富山県 (16) の土砂災害警戒区域データ (A33) をダウンロード（GeoJSON優先、今日の日付フォルダ内）
python backend/scripts/download_data.py --data-code A33 --pref-code 16 --upload-drive
```

特定のフォーマットや過去年度を指定する場合：

```bash
# 2024年度のShapefile形式を指定してダウンロード
python backend/scripts/download_data.py --data-code A33 --pref-code 16 --year 2024 --format Shapefile --upload-drive
```

### Web アプリケーション運用構成

本システムは、用途に合わせて2種類のバックエンド構成を選択できます。

```
【構成 A: 完全無料・サーバーレス運用（推奨）】
Next.js (Vercel)  --->  GAS Web App (doPost)  --->  Gemini API & Google Drive

【構成 B: Python サーバー運用】
Next.js (Vercel / Local)  --->  FastAPI (Uvicorn / Cloud Run)  --->  Gemini API & Google Drive
```

---

#### 構成 A: GAS をバックエンドにする場合（完全サーバーレス & 無料）

1. **Google Apps Script プロジェクトの作成**:
   - [Google Apps Script](https://script.google.com/) を開き、新しいプロジェクトを作成します。
   - [`gas/Code.gs`](./gas/Code.gs) の内容をコードエディタにコピー＆ペーストします。
   - 「プロジェクトの設定」（歯車アイコン）>「スクリプト プロパティ」に以下を追加します：
     - `GEMINI_API_KEY`: Gemini APIキー（任意。設定するとAI高精度解析が有効になります）
     - `GEMINI_MODEL`: `gemini-2.5-flash`（デフォルト）
     - `GOOGLE_DRIVE_FOLDER_ID`: GISデータを保存したい Google Drive フォルダのID
2. **Web アプリとしてデプロイ**:
   - 画面右上の「デプロイ」>「新しいデプロイ」をクリック。
   - 種類の選択で「ウェブアプリ」を選択。
     - **次のユーザーとして実行**: `自分 (YOUR_EMAIL@gmail.com)`
     - **アクセスできるユーザー**: `全員 (Anyone)`
   - デプロイを実行し、発行された **ウェブアプリの URL**（`https://script.google.com/macros/s/.../exec`）をコピーします。
3. **フロントエンド（Next.js）への設定**:
   - `frontend/.env.local` または Vercel の環境変数に設定します：
     ```bash
     NEXT_PUBLIC_GAS_API_URL=https://script.google.com/macros/s/YOUR_DEPLOYMENT_ID/exec
     ```

---

#### 構成 B: FastAPI サーバーをバックエンドにする場合

1. **バックエンド API サーバーの起動**:
   ```bash
   source .venv/bin/activate
   uvicorn backend.app.main:app --reload --port 8000
   ```
   - Swagger UI (API仕様書): [http://localhost:8000/docs](http://localhost:8000/docs)

2. **フロントエンド（Next.js）の起動**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   - Web UI: [http://localhost:3000](http://localhost:3000)

---

#### Vercel へのデプロイ

フロントエンド（Next.js）は Vercel にそのままデプロイ可能です。
- **Root Directory**: `frontend`
- **Framework Preset**: `Next.js`
- **Environment Variables**:
  - GAS 運用の場合は `NEXT_PUBLIC_GAS_API_URL`
  - FastAPI 運用の場合は `NEXT_PUBLIC_API_BASE_URL`

## テスト

```bash
source .venv/bin/activate
pytest
```

フロントエンドのビルド確認：

```bash
cd frontend
npm run build
```

詳細なシステム構成は [GIS-data-downloads_設計書.md](./GIS-data-downloads_設計書.md) を参照してください。
