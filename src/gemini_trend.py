import os
import glob
import re
import json
import time
from datetime import datetime
from google.genai import types
from google import genai
from dotenv import load_dotenv

# ============================================
# 設定
# ============================================
load_dotenv()

WARS_ID = os.getenv("WARS_ID", "")
THINKING_MODELS = {"gemini-3.1-pro-preview", "gemini-3.1-flash-preview"}

# ============================================
# 実行条件チェック
# ============================================

def should_run_trend(ROOT) -> bool:
    """実行条件: 今月の trend_report が未作成 AND local_summarys.json が40件以上"""
    reports_dir = os.path.join(ROOT, "reports")
    today = datetime.now()
    current_ym = today.strftime("%Y%m")

    # 今月の trend_report があるか
    files = glob.glob(os.path.join(reports_dir, "trend_report*.md"))
    for f in files:
        match = re.search(r'trend_report(\d{8})\.md', os.path.basename(f))
        if match and match.group(1).startswith(current_ym):
            return False  # 今月分は既にある

    # local_summarys.json の件数が40以上か
    json_path = os.path.join(ROOT, "temp", "local_summarys.json")
    if not os.path.exists(json_path):
        return False
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        count = len(data.get("各対局の振り返り", {}))
        return count >= 40
    except Exception:
        return False

# ============================================
# 補助関数
# ============================================

def get_latest_report(ROOT, log_path):
    reports_dir = os.path.join(ROOT,"reports")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"reportsディレクトリ内の最新のmdファイルを取得します\n")
    print("reportsディレクトリ内の最新のmdファイルを取得します")
    files = glob.glob(os.path.join(reports_dir, "*.md"))
    if not files:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"前回レポートの読み込み失敗\n")
        print(f"前回レポートの読み込み失敗")
        return ""
    
    # ファイル名から日付部分(YYYYMMDD)を抽出してソート
    # 例: trend_report20260117.md や reports_20260117.md
    def extract_date(filepath):
        match = re.search(r'(\d{8})', os.path.basename(filepath))
        return match.group(1) if match else "00000000"

    latest_file = max(files, key=extract_date)
    
    try:
        with open(latest_file, "r", encoding="utf-8") as f:
            return f.read()
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"前回レポートの読み込み成功:{latest_file}\n")
        print(f"前回レポートの読み込み成功:{latest_file}")
    except Exception as e:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"前回レポートの読み込み失敗: \n{e}\n")
        print(f"前回レポートの読み込み失敗: {e}")
        return ""

def call_gemini_trend(ROOT, log_path, prompt: str) -> str:
    """Gemini APIを呼び出して傾向分析レポートを返す（GEMINI_MODELSを順にトライ、API_KEY01〜05をローテーション）"""
    gemini_models_str = os.getenv("GEMINI_MODELS", "gemini-3.1-pro-preview,gemini-3.1-flash-preview,gemini-2.5-pro,gemini-2.5-flash")
    model_list = [m.strip() for m in gemini_models_str.split(",") if m.strip()]

    api_keys = [
        os.getenv("API_KEY01"),
        os.getenv("API_KEY02"),
        os.getenv("API_KEY03"),
        os.getenv("API_KEY04"),
        os.getenv("API_KEY05"),
    ]

    last_error = None
    for model_idx, model in enumerate(model_list):
        use_thinking = model in THINKING_MODELS
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"MODEL={model}\n")
        print(f"MODEL={model}")

        for i, api_key in enumerate(api_keys, start=1):
            key_num = f"{i:02d}"
            if not api_key:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"[WARN] API_KEY{key_num} が未設定のためスキップ\n")
                print(f"[WARN] API_KEY{key_num} が未設定のためスキップ")
                continue
            try:
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"[*] Gemini呼び出し (KEY{key_num}): {model}\n")
                print(f"[*] Gemini呼び出し (KEY{key_num}): {model}")
                client = genai.Client(api_key=api_key)
                if use_thinking:
                    config = types.GenerateContentConfig(
                        thinking_config=types.ThinkingConfig(
                            include_thoughts=True,
                            thinking_level="high"
                        )
                    )
                else:
                    config = types.GenerateContentConfig()
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config
                )
                if response and response.text:
                    return response.text.strip()
            except Exception as e:
                last_error = e
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"[WARN] KEY{key_num}/{model} 失敗: {e}\n")
                print(f"[WARN] KEY{key_num}/{model} 失敗: {e}")
                if i < len(api_keys):
                    time.sleep(10)

        # 全キー失敗 → 次のモデルへ
        if model_idx < len(model_list) - 1:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[WARN] モデル {model} 全キー失敗。次のモデルへ移行します\n")
            print(f"[WARN] モデル {model} 全キー失敗。次のモデルへ移行します")
            time.sleep(10)

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[ERROR] 全モデル・全APIキーで失敗: {last_error}\n")
    print(f"[ERROR] 全モデル・全APIキーで失敗: {last_error}")
    return ""

# ============================================
# メイン処理
# ============================================

def run(ROOT, log_path):
    reports_dir = os.path.join(ROOT,"reports")
    os.makedirs(os.path.join(ROOT,'reports') ,exist_ok=True)
    made_report = False
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"=== Geminiトレンド分析 開始: ===\n")
    print(f"=== Geminiトレンド分析 開始: ===")
    
    # 1. データの準備
    today_str = datetime.now().strftime("%Y%m%d")
    #json_path = r"C:\SHOGI\temp\local_summarys.json"
    json_path = os.path.join(ROOT,"temp","local_summarys.json")

    if not os.path.exists(json_path):
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[ERROR] JSONファイルが見つかりません: {json_path}\n")
        print(f"[ERROR] JSONファイルが見つかりません: {json_path}")
        return made_report

    with open(json_path, "r", encoding="utf-8") as f:
        local_summarys_json = f.read()

    # 4.1 追加アップデート: local_summarys.json を最新40局に絞り込み
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("=== [4.1追加] local_summarys.json を最新40局に絞り込み ===\n")
    print("=== [4.1追加] local_summarys.json を最新40局に絞り込み ===")
    try:
        local_summarys_data = json.loads(local_summarys_json)
        games = local_summarys_data.get("各対局の振り返り", {})
        if len(games) > 40:
            def _get_battle_dt(bid):
                m = re.search(r'(\d{8}_\d{6})$', bid)
                if m:
                    try:
                        return datetime.strptime(m.group(1), "%Y%m%d_%H%M%S")
                    except ValueError:
                        pass
                return datetime.min
            sorted_ids = sorted(games.keys(), key=_get_battle_dt, reverse=True)
            ids_to_delete = sorted_ids[40:]
            for bid in ids_to_delete:
                del games[bid]
            local_summarys_data["各対局の振り返り"] = games
            local_summarys_json = json.dumps(local_summarys_data, ensure_ascii=False, indent=4)
            with open(json_path, "w", encoding="utf-8") as f:
                f.write(local_summarys_json)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[4.1追加] {len(ids_to_delete)} 件を削除して {len(games)} 件に絞り込み\n")
            print(f"[4.1追加] {len(ids_to_delete)} 件を削除して {len(games)} 件に絞り込み")
        else:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[4.1追加] 件数は {len(games)} 件のため削除不要\n")
            print(f"[4.1追加] 件数は {len(games)} 件のため削除不要")
    except Exception:
        import traceback as _tb
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[WARN] 40局絞り込み処理でエラー:\n{_tb.format_exc()}\n")

    # 前回のレポートを取得
    previous_report = get_latest_report(ROOT, log_path)

    # 2. プロンプトの組み立て
    prompt = f"""
あなたは将棋のプロ棋士育成コーチAIです。
あなたに、私(={WARS_ID})が将棋で負けた各対局における(1)対局棋譜データ、(2)将棋プロ棋士AIの解説をまとめたjson形式のデータ「以降、これを各対局分析レポートと呼びます」をお渡しします。

あなたの役割は、下記の2つです。
1. 各対局分析レポートデータから、**私が棋力向上するためのコーチングレポートを作成してください**。
  - フォーマットは末尾に示すMarkdown形式のテンプレートに従って、下記3点をまとめてください。
    - 私の弱点傾向
    - 改善点
    - 勉強計画
      - **勉強時間は1日1時間を目安とすること**
        - 対局すること自体もこの勉強時間に含めて計画すること
      - 意識すべきこととともに、具体的に示すこと
      - 書籍の購入を除いて、なるべく無料でできる方法を提案すること
  - **【重要】**
    - 使用する用語は専門用語を避け、アマチュア初段程度向けに分かりやすい言葉で丁寧に説明すること
    - 「自分の弱点傾向 → 改善点 → 克服に向けた勉強計画」の流れを意識してまとめること
    - **「勝つこと」よりも「棋力向上するために必要な勉強法」に重きを置くこと**
      - (悪い例)：相手の持ち時間が1分以内になったら、自玉の守りを徹底や王手を繰り返し、相手の時間切れを狙う
        - 棋力向上につながる内容ではないため最悪な例。まとめにくい場合は、時間切れが敗因と思われる対局の情報重要度を下げても問題ありません。
      - (良い例)：「速く」「正確に」指せるようになることを意識する
        - **「私が今までの負けた対局から何を学び、今後強くなるためにどうすればいいか」を記載した内容のため良い例**
    - テンプレートの内容は絶対に崩さないこと
      - ただし各項目は、月末目標を除き、複数回答が可能です。
      - **月末目標はなるべく1個、多くても絶対2個まで**

2. 下記の記載方法に従い、**後で振り返りやすいように、敗因ごとに対局データをグループ分けしてください**。
  - ※対局データとは、お渡しするjsonデータにおいて「{WARS_ID}-Opponent-YYYYMMDD_hhmmss」のように、「(先手ユーザー名)-(後手ユーザー名)-(対局日付"YYYYMMDD_yymmss")」というフォーマットで記載されており、ディレクトリ名にもなっている対局の識別IDのことです。
  - 敗因ごとにグループ分けした対局データの記載方法
    - **振り分けテーマ1(日本語で記載)**
      - **ディレクトリ名**
        - **テーマに該当する対局データ1**
        - **テーマに該当する対局データ2**
        - ...
    - **振り分けテーマ2(日本語で記載)**
      - ...
    (例)
    - 玉の囲いが未完成の状態で攻めを続けた
      - Kept_Attacking_with_Unprepared_casle
        - xxxxx-{WARS_ID}-YYYYMMDD_hhmmss(**テーマに該当する対局データ1**）)
        - {WARS_ID}-xxxxx-YYYYMMDD_hhmmssなど・・・ほかの対局データについても同様
    - ・・・ほかの振り返りテーマについても同様
  - **【重要】**
    - ディレクトリ名は、1つの振り分けテーマに対して必ず1つだけ記載すること
    - ディレクトリ名は、必ず「Windowsのディレクトリ名に適した」英数字と「_」のみの組み合わせにし、文字数はなるべく50文字以内で記載すること
    - 対局データは必ず最適な振り分けテーマに1つだけ割り振り、絶対に同じ対局名ディレクトリを複数のテーマ配下に記載しないこと
    - 1テーマにつき、振り分けたディレクトリ名が2つ以上5つ以下となるように、振り分けテーマを考えること

【入力データ】
各対局分析レポートデータ
{local_summarys_json}

【出力フォーマット（Markdown）】
# コーチングレポート
## 1. 自分の弱点傾向
- **自分が頻繁に負ける相手の戦型**
- **対局レビューで頻繁に見受けられる敗因**

## 2. 改善点
- **今後の対局で意識すべき改善点**
- **覚えておくと良い定跡**
  - 基本的な定跡から、上記1.の項目で記載した相手の戦型に対するマニアックな将棋の知識を1つ記載

## 3. 勉強計画
- **月末目標**
- **目標に対して、現在の実力から見た達成度合い(0~100%で記載)**
- **勉強法**
  - **その勉強法で効果を高めるために意識すべきこと**
  - **その勉強法を通して、弱点が克服される理想的なステップ(3~5ステップ程度で記載)**

## 4. 敗因ごとの対局データのグループ分け
- **振り分けテーマ**
  - **ディレクトリ名の例**
  - **各テーマに該当する対局データ**

## 5. 振り返りの優先度が高い対局
  - **自分の弱点傾向が明確に表れている対局データを3局以内で選択し、箇条書きで記載**
    - それぞれの対局データを選んだ根拠を記載
"""

    # 3. Gemini実行
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"Geminiにリクエスト送信中...\n")
    print("Geminiにリクエスト送信中...")
    report_content = call_gemini_trend(ROOT, log_path, prompt)

    # 4. 保存判定
    if report_content:        
        try:
            output_path = os.path.join(reports_dir, f"trend_report{today_str}.md")
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(report_content)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[SUCCESS] レポートを保存しました: {output_path}\n")
            print(f"[SUCCESS] レポートを保存しました: {output_path}")
            made_report = True
        except Exception as e:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[ERROR] ファイル書き込み失敗: {e}\n")
            print(f"[ERROR] ファイル書き込み失敗: {e}")
    else:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[CANCEL] レスポンスが空のため、レポート作成をスキップしました。\n")
        print("[CANCEL] レスポンスが空のため、レポート作成をスキップしました。")

    return made_report

if __name__ == "__main__":
    # デバッグ用設定
    #run_dir = r"C:\SHOGI\temp\trg_20260118_0621"
    made_report = run(ROOT, log_path)
