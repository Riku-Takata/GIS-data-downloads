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


### GSMaP時間雨量のFTPダウンロード

GSMaPの認証情報を `.env` に設定します。パスワードをコマンドライン引数へ直接書かないでください。

```dotenv
GSMAP_FTP_HOST=YOUR_FTP_HOST
GSMAP_FTP_PORT=21
GSMAP_FTP_USER=YOUR_USER
GSMAP_FTP_PASSWORD=YOUR_PASSWORD
GSMAP_FTP_TLS=false
GSMAP_FTP_TIMEOUT=60
GSMAP_FTP_RETRIES=8
GSMAP_FTP_RETRY_DELAY=5
GSMAP_FTP_RETRY_MAX_DELAY=120
GSMAP_OUTPUT_DIR=downloads/gsmap
GSMAP_JAPAN_BOUNDARY=downloads/n03-source/N03-20260101_GML.zip
GSMAP_JAPAN_CSV_DIR=downloads/gsmap-japan-csv
GSMAP_CSV_WORKERS=2
```

最初に対象件数と既知の合計サイズだけを確認します。

```powershell
python backend/scripts/download_gsmap.py standard/v8 --start 2014-01-01 --end today --dry-run
```

確認後、実際にダウンロードします。31日を超える範囲では誤操作防止のため `--yes` が必要です。

```powershell
python backend/scripts/download_gsmap.py standard/v8 --start 2014-01-01 --end today --yes
```

雨量計補正済みの時間雨量を取得する場合：

```powershell
python backend/scripts/download_gsmap.py standard/v8 --dataset hourly-gauge --start 2014-01-01 --end today --yes
```

日本国土に重なる元の0.1度格子だけを、ダウンロードと並行して日別CSVへ変換する場合：

```powershell
python backend/scripts/download_gsmap.py standard/v8 --start 2014-01-01 --end today --yes --japan-csv
```

- 初回だけ全国N03ポリゴンとGSMaP格子を面積交差判定し、`_mask/gsmap_japan_grid_mask.csv` に保存します。取得済みN03-2026では5,062格子です。
- FTPで1日分を取得した時点で変換をキューへ投入し、次の日のダウンロードとバックグラウンド変換を並行実行します。
- 出力は `standard/v8/hourly/YYYY/MM/YYYYMMDD.csv.gz`。列は `timestamp_utc,grid_id,latitude,longitude,rain_rate_mm_h` です。
- 既定は大規模保存向けのgzip圧縮CSVです。非圧縮CSVが必要なら `--csv-compression none` を指定します。
- 日別メタデータに変換元ファイル一覧を記録し、再実行では同じ日をスキップします。時間ファイルが追加された日だけCSV全体を原子的に再生成します。
- JAXA定義の負値 `-4`, `-8`, `-99` は欠損・未観測コードとしてそのまま保持します。

取得処理の安全策：

- FTPサーバーには一覧・サイズ・更新日時・取得の読み取り系コマンドだけを送信します。
- ファイルはローカルの `.part` に保存し、サイズ確認とSHA-256計算後に確定名へ変更します。
- 接続拒否・切断・タイムアウト時は指数バックオフでFTPへ再接続し、既定で最大8回再試行します。
- 同じサイズの取得済みファイルはスキップし、中断した `.part` は自動再試行または次回実行で再開します。
- 保存先は `standard/v8/hourly/YYYY/MM/DD/` 相当の階層で整理され、結果を `manifest.jsonl` に記録します。

2014年から現在までの時間雨量は最大約11万ファイル、概算160GB超になる可能性があります。最初は `--limit 24` を併用して1日分程度で接続確認することを推奨します。
### 日本国内GSMaP MySQLデータベース

Docker上のMySQL 8.4へ、完成済みの日別CSVだけを再開可能・重複防止付きで投入できます。雨量テーブルにはUTCとJST（UTC+9）、数値ID、日時・格子検索用インデックスがあります。

```powershell
# 対象確認
python backend/scripts/import_gsmap_csv_to_mysql.py --start 2014-01-01 --end today --dry-run

# 完成済み全日を投入（再実行時は投入済みファイルをスキップ）
python backend/scripts/import_gsmap_csv_to_mysql.py --start 2014-01-01 --end today
```

起動、管理者ファイアウォール設定、別PCからのAdminer/CLI接続は [`infrastructure/mysql/README.md`](./infrastructure/mysql/README.md) を参照してください。
日本国土ポリゴンは、格子抽出に使用したN03都道府県レイヤーをSRID 4326・空間インデックス・元属性・出典ハッシュ付きでDBへ保存します。DBのみからGeoJSONを再生成できます。

```powershell
python backend/scripts/import_japan_boundaries_to_mysql.py
python backend/scripts/export_japan_boundaries_from_mysql.py downloads/japan-land.geojson
```

全量投入後は、CSV署名・投入履歴・実テーブル行数・バイナリ時間数・境界件数を検証してから、大容量の元データだけを削除できます。

```powershell
python backend/scripts/verify_and_cleanup_gsmap_sources.py --start 2014-01-01 --end today --yes
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
   uvicorn --app-dir backend app.main:app --reload --port 8000
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
