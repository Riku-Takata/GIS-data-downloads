# GIS-data-downloads

自然言語から国土数値情報を検索し、取得したデータをGoogle Driveへ保存するWebアプリケーションのバックエンドです。

現在は最初の実装として、国土交通省の国土数値情報一覧から検索用メタデータを生成し、Google Drive上の `metadata.json` を作成または更新するバッチを提供します。

## 実装済みの範囲

- 国土数値情報の公式一覧ページからデータコード、名称、分類、キーワード、詳細URLを抽出
- UTF-8の `backend/app/data/metadata.json` を原子的に更新
- Google Driveの指定フォルダに `metadata.json` を新規作成、または既存ファイルを更新
- サービスアカウント、Application Default Credentials、Google Workspaceのドメイン全体の委任に対応

## セットアップ

Python 3.11以降を使用します。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
cp .env.example .env
```

`.env` の以下の値を環境に合わせて設定してください。

- `GOOGLE_APPLICATION_CREDENTIALS`: サービスアカウントJSONの絶対パス
- `GOOGLE_DRIVE_FOLDER_ID`: `metadata.json` を保存するフォルダID
- `GOOGLE_DRIVE_SHARED_DRIVE_ID`: 保存先が共有ドライブの場合のドライブID（任意）
- `GOOGLE_DRIVE_IMPERSONATE_USER`: ドメイン全体の委任で代理するユーザー（任意）

認証JSONや `.env` はGit管理対象外です。

サービスアカウントで保存する場合は、対象の共有ドライブにサービスアカウントをメンバーとして追加してください。Google Workspaceのユーザー領域へ保存する場合は、ドメイン全体の委任と `GOOGLE_DRIVE_IMPERSONATE_USER` を使用できます。

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

## テスト

```bash
python -m pip install -r requirements-dev.txt
pytest
```

詳細なシステム構成は [GIS-data-downloads_設計書.md](./GIS-data-downloads_設計書.md) を参照してください。
