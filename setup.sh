#!/bin/bash
#
# Firecrawl Analysis セットアップスクリプト
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "======================================"
echo "Firecrawl Analysis Setup"
echo "======================================"
echo ""

# Python バージョンチェック
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "Error: Python が見つかりません"
    echo "Python 3.10以上をインストールしてください"
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Python version: $PYTHON_VERSION"

# バージョン比較
MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$MAJOR" -lt 3 ] || ([ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 10 ]); then
    echo "Error: Python 3.10以上が必要です（現在: $PYTHON_VERSION）"
    exit 1
fi

# 仮想環境の作成
echo ""
echo "1. 仮想環境を作成..."
if [ -d ".venv" ]; then
    echo "   .venv は既に存在します（スキップ）"
else
    $PYTHON_CMD -m venv .venv
    echo "   .venv を作成しました"
fi

# 仮想環境を有効化
echo ""
echo "2. 仮想環境を有効化..."
source .venv/bin/activate

# 依存パッケージのインストール
echo ""
echo "3. 依存パッケージをインストール..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "   インストール完了"

# データディレクトリの作成
echo ""
echo "4. データディレクトリを作成..."
mkdir -p data/screenshots
echo "   data/ を作成しました"
echo "   data/screenshots/ を作成しました"

# 環境変数チェック
echo ""
echo "======================================"
echo "セットアップ完了!"
echo "======================================"
echo ""

if [ -z "$FIRECRAWL_API_KEY" ]; then
    echo "注意: FIRECRAWL_API_KEY が設定されていません"
    echo ""
    echo "URL取得機能を使用する場合は、以下を .zshrc または .bashrc に追加してください:"
    echo ""
    echo '  export FIRECRAWL_API_KEY="your-api-key-here"'
    echo ""
    echo "APIキーは https://firecrawl.dev/ で取得できます"
    echo ""
fi

echo "使い方:"
echo ""
echo "  # CLI"
echo "  source .venv/bin/activate"
echo "  python cli.py --help"
echo ""
echo "  # GUI (Streamlit)"
echo "  source .venv/bin/activate"
echo "  streamlit run gui.py"
echo ""
