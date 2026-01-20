# Firecrawl Analysis

FirecrawlでスクレイピングしたJSONデータをSQLiteに保存し、CLI/GUIで検索・分析・エクスポートできるツールです。

## 機能

- **JSONインポート**: Firecrawl APIのレスポンスJSONをSQLiteにインポート
- **全文検索**: FTS5による高速な全文検索（タイトル、説明、Markdown本文）
- **スクリーンショット取得**: デスクトップ・モバイル両方のスクリーンショットをローカル保存
- **複数URL一括取得**: 複数URLを順次スクレイピング
- **エクスポート**: CSV/JSON形式でエクスポート
- **CLI/GUI両対応**: コマンドラインとStreamlit GUIの両方で操作可能

## セットアップ

### 必要条件

- Python 3.10以上
- [Firecrawl API キー](https://firecrawl.dev/)（URL取得機能を使用する場合）

### インストール

```bash
# リポジトリをクローン
git clone https://github.com/tomohisay/firecrawl-analysis.git
cd firecrawl-analysis

# セットアップスクリプトを実行
./setup.sh
```

または手動でセットアップ:

```bash
# 仮想環境を作成
python3 -m venv .venv
source .venv/bin/activate

# 依存パッケージをインストール
pip install -r requirements.txt

# データディレクトリを作成
mkdir -p data/screenshots
```

### 環境変数の設定

URL取得機能を使用する場合は、Firecrawl APIキーを設定してください:

```bash
# .zshrc または .bashrc に追加
export FIRECRAWL_API_KEY="your-api-key-here"
```

## 使い方

### GUI（Streamlit）

```bash
source .venv/bin/activate
streamlit run gui.py
```

ブラウザで http://localhost:8501 にアクセス

#### GUI機能

- **検索・フィルタ**: サイドバーで全文検索、URL絞り込み、モード選択
- **URL取得**: URLを入力してFirecrawl APIで直接スクレイピング（複数URL対応）
- **詳細表示**: Markdown/HTML/Screenshot/Links/Metadataをタブで切り替え
- **エクスポート**: CSV/JSONダウンロードボタン

### CLI

```bash
source .venv/bin/activate

# ヘルプ表示
python cli.py --help
```

#### インポート

```bash
# 単一ファイル
python cli.py import path/to/file.json

# ディレクトリ一括（サブディレクトリ含む）
python cli.py import ~/FirecrawlAPI/ -r

# 重複も再インポート
python cli.py import ~/FirecrawlAPI/ -f
```

#### 一覧・検索

```bash
# 一覧表示
python cli.py list
python cli.py list --limit 50 --mode scrape

# 全文検索
python cli.py search "キーワード"

# URL絞り込み
python cli.py search --url "example.com"
```

#### 詳細表示

```bash
# 基本情報
python cli.py show 1

# Markdownも表示
python cli.py show 1 --markdown

# リンク一覧
python cli.py show 1 --links

# メタデータ
python cli.py show 1 --metadata
```

#### エクスポート

```bash
# CSV
python cli.py export --format csv -o output.csv

# JSON
python cli.py export --format json -o output.json

# フィルタ付き
python cli.py export --format csv -o output.csv --url "example.com" --limit 100
```

#### 統計

```bash
python cli.py stats
```

#### 削除

```bash
python cli.py delete 1
python cli.py delete 1 -f  # 確認なし
```

## ディレクトリ構成

```
firecrawl-analysis/
├── .venv/                      # Python仮想環境
├── requirements.txt            # 依存パッケージ
├── setup.sh                    # セットアップスクリプト
├── cli.py                      # CLIエントリーポイント
├── gui.py                      # Streamlit GUI
├── firecrawl_db/               # メインパッケージ
│   ├── __init__.py
│   ├── models.py               # データモデル
│   ├── database.py             # SQLite操作
│   ├── importer.py             # JSONインポート
│   ├── exporter.py             # CSV/JSONエクスポート
│   ├── query.py                # 検索・フィルタ
│   └── scraper.py              # Firecrawl API クライアント
└── data/
    ├── firecrawl.db            # SQLiteデータベース
    └── screenshots/            # スクリーンショット保存先
```

## データベーススキーマ

### scrapes テーブル

| カラム | 型 | 説明 |
|--------|------|------|
| id | INTEGER | 主キー |
| source_url | TEXT | スクレイピング元URL |
| mode | TEXT | モード（scrape/crawl/map） |
| scraped_at | TIMESTAMP | スクレイピング日時 |
| markdown | TEXT | Markdownコンテンツ |
| html | TEXT | HTMLコンテンツ |
| screenshot_desktop_url | TEXT | デスクトップスクリーンショットURL |
| screenshot_mobile_url | TEXT | モバイルスクリーンショットURL |
| screenshot_desktop_path | TEXT | デスクトップスクリーンショットローカルパス |
| screenshot_mobile_path | TEXT | モバイルスクリーンショットローカルパス |
| title | TEXT | ページタイトル |
| description | TEXT | ページ説明 |
| language | TEXT | 言語 |
| status_code | INTEGER | HTTPステータスコード |

### links テーブル

| カラム | 型 | 説明 |
|--------|------|------|
| id | INTEGER | 主キー |
| scrape_id | INTEGER | scrapes.id への外部キー |
| url | TEXT | リンクURL |
| position | INTEGER | 出現順序 |

### metadata テーブル

| カラム | 型 | 説明 |
|--------|------|------|
| id | INTEGER | 主キー |
| scrape_id | INTEGER | scrapes.id への外部キー |
| key | TEXT | メタデータキー |
| value | TEXT | メタデータ値 |

## ライセンス

MIT License

## 関連リンク

- [Firecrawl](https://firecrawl.dev/) - Webスクレイピング API
- [Streamlit](https://streamlit.io/) - Python GUIフレームワーク
