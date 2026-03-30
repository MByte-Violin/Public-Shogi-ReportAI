import os
import json
import glob
import re
from datetime import datetime
from google import genai
from dotenv import load_dotenv

# ============================================
# 設定
# ============================================
#load_dotenv()
API_KEY = os.getenv("API_KEY_FREE")

# reports_dir = os.path.join(ROOT,"reports")
# sorting_json_path = os.path.join(reports_dir, "Sorting.json")
MODEL_ID = "gemini-2.5-flash"

# ============================================
# 補助関数
# ============================================

def get_latest_trend_report(ROOT, log_path):
    """最新のトレンドレポート(trend_reportYYYYMMDD.md)を取得する"""
    reports_dir = os.path.join(ROOT,"reports")
    files = glob.glob(os.path.join(reports_dir, "trend_report*.md"))
    if not files:
        print("トレンドレポートが見つかりません。")
        return None
    
    # ファイル名の日付部分でソートして最新を取得
    latest_file = max(files, key=os.path.getmtime)
    try:
        with open(latest_file, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"-レポート読み込みエラー: \n{e}\n")
        print(f"レポート読み込みエラー: {e}")
        return None

def load_current_sorting(ROOT, log_path):
    """既存のSorting.jsonを読み込む"""
    reports_dir = os.path.join(ROOT,"reports")
    sorting_json_path = os.path.join(reports_dir, "Sorting.json")
    if os.path.exists(sorting_json_path):
        try:
            with open(sorting_json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"Sorting.json読み込みエラー: \n{e}\n")
            print(f"Sorting.json読み込みエラー: {e}")
    return {"themes": {}}

def call_gemini_json_converter(ROOT, log_path, prompt: str) -> str:
    """Geminiに対してプロンプトを送信する"""
    client = genai.Client(api_key=API_KEY)
    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                response_mime_type="application/json" # JSON出力モード
            )
        )
        if response and response.text:
            return response.text.strip()
    except Exception as e:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"APIリクエストエラー: \n{e}\n")
        print(f"APIリクエストエラー: {e}")
    return ""

# ============================================
# メイン処理
# ============================================

def run(ROOT, log_path):
    reports_dir = os.path.join(ROOT,"reports")
    sorting_json_path = os.path.join(reports_dir, "Sorting.json")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"=== Step: 対局名振り分けデータのJSON変換・統合 開始 ===\n")
    print("=== Step: 対局名振り分けデータのJSON変換・統合 開始 ===")

    # 1. データの準備
    markdown_report = get_latest_trend_report(ROOT, log_path)
    if not markdown_report:
        return

    current_sorting = load_current_sorting(ROOT, log_path)

    # 2. プロンプトの組み立て
    # json.dumpsで既存データを文字列化して埋め込む
    prompt = f"""
# 対局名振り分けデータのjson変換プロンプト
- あなたはデータ整理アシスタントです。
- これからあなたに、以下の情報をお渡しします。
  - 現存の振り返りテーマごとによって振り分けた対局名ディレクトリのディレクトリ構造を記載した@Sorting.json
    - 元々データが無くて渡せない場合もあります。
  - 新しく振り返りテーマと対局名ディレクトリを記載したMarkdownレポート
- あなたの役割は、Markdownレポートの「4. 振り返りテーマによる対局データの振り分け」セクションを読み取り、既存の@Sorting.jsonに**新しく振り返りテーマごとに対局名ディレクトリを振り分けたデータを追加した@Sorting.jsonのみを出力すること**です。

【重要】
- **もし既存の@Sorting.jsonと酷似している振り返りテーマがあった場合は、既存の振り返りテーマへ統合すること。**

既存のSorting.json:
{json.dumps(current_sorting, ensure_ascii=False, indent=4)}

Markdownレポート:
{markdown_report}

出力形式:
{{
    "themes": {{
        "テーマ名": {{
            "dir_name": "ディレクトリ名",
            "games": ["対局名1", "対局名2"]
        }}
    }}
}}
"""

    # 3. Gemini実行
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"GeminiにJSON変換リクエストを送信中...\n")
    print("GeminiにJSON変換リクエストを送信中...")
    json_response = call_gemini_json_converter(ROOT, log_path, prompt)

    # 4. 保存判定
    if json_response:
        try:
            # 有効なJSONか検証
            updated_data = json.loads(json_response)
            
            with open(sorting_json_path, "w", encoding="utf-8") as f:
                json.dump(updated_data, f, ensure_ascii=False, indent=4)
            
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[SUCCESS] Sorting.jsonを更新しました: {sorting_json_path}\n")
            print(f"[SUCCESS] Sorting.jsonを更新しました: {sorting_json_path}")
        except json.JSONDecodeError as e:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[ERROR] Geminiの応答が正しいJSON形式ではありません: \n{e}\n")
            print(f"[ERROR] Geminiの応答が正しいJSON形式ではありません: {e}")
    else:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[CANCEL] レスポンスが空のため、Sorting.jsonの更新をスキップしました。\n")
        print("[CANCEL] レスポンスが空のため、Sorting.jsonの更新をスキップしました。")

if __name__ == "__main__":
    run(ROOT, log_path)