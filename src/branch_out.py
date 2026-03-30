import os
import json
import shutil

# ============================================
# 設定
# ============================================
WARS_ID = os.getenv("WARS_ID", "")

# ============================================
# 補助関数
# ============================================

def get_opponent_style(battle_dir: str) -> str:
    """raw.kif の戦法行から相手の戦型を取得する（最後の要素を採用）"""
    kif_path = os.path.join(battle_dir, "raw.kif")
    if not os.path.exists(kif_path):
        return "その他"

    try:
        with open(kif_path, encoding="utf-8") as f:
            kif_text = f.read()
    except Exception:
        return "その他"

    # ユーザーが先手か後手かを判定
    is_user_sente = False
    for line in kif_text.splitlines():
        if line.startswith("先手："):
            is_user_sente = WARS_ID in line
            break

    # 相手の戦法行を取得
    for line in kif_text.splitlines():
        if is_user_sente and line.startswith("後手の戦法："):
            style = line.split("：", 1)[1]
            style = style.split(",")[-1].strip()
            return style if style else "その他"

        if not is_user_sente and line.startswith("先手の戦法："):
            style = line.split("：", 1)[1]
            style = style.split(",")[-1].strip()
            return style if style else "その他"

    return "その他"


# ============================================
# 戦型別コピー
# ============================================

def copy_to_style_dir(ROOT, log_path, run_dir: str):
    """6.1: 戦型別ディレクトリへ battle_id をコピー"""
    style_base = os.path.join(ROOT, "戦型別")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("=== Step: 対局データの戦型別コピー 開始 ===\n")
    print("=== Step: 対局データの戦型別コピー 開始 ===")

    for battle_id in os.listdir(run_dir):
        battle_path = os.path.join(run_dir, battle_id)
        if not os.path.isdir(battle_path):
            continue

        style = get_opponent_style(battle_path)
        dest_style_dir = os.path.join(style_base, style)
        os.makedirs(dest_style_dir, exist_ok=True)

        dest_path = os.path.join(dest_style_dir, battle_id)
        if os.path.exists(dest_path):
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[SKIP] 既存: {battle_id} -> 戦型別/{style}\n")
            continue

        try:
            shutil.copytree(battle_path, dest_path)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[COPY] {battle_id} -> 戦型別/{style}\n")
            print(f"  [COPY] {battle_id} -> 戦型別/{style}")
        except Exception as e:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[ERROR] コピー失敗 {battle_id}: \n{e}\n")
            print(f"  [ERROR] コピー失敗 {battle_id}: {e}")

    with open(log_path, "a", encoding="utf-8") as f:
        f.write("=== 戦型別コピー 完了 ===\n")
    print("=== 戦型別コピー 完了 ===")


# ============================================
# themes コピー（3段階）
# ============================================

def try_copy(src, dest, battle_id, log_path, label: str) -> bool:
    """
    共通コピー処理
    label: ログ用のラベル（日本語テーマ名 / dir_name / その他）
    """
    # 親ディレクトリを必要になったタイミングで作成
    parent = os.path.dirname(dest)
    os.makedirs(parent, exist_ok=True)

    if os.path.exists(dest):
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[SKIP] {label}: 既に存在します: {battle_id} -> {dest}\n")
        print(f"  [SKIP] {label}: 既に存在します: {battle_id}")
        return True  # スキップも成功扱い

    try:
        shutil.copytree(src, dest)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[COPY] {label}: {battle_id} -> {dest}\n")
        print(f"  [COPY] {label}: {battle_id}")
        return True
    except Exception as e:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[ERROR] {label}: コピー失敗 {battle_id}: {dest}\n{e}\n")
        print(f"  [ERROR] {label}: コピー失敗 {battle_id}")
        return False


def copy_to_theme_dir(ROOT, log_path, run_dir: str):
    """6.2: Sorting.json の内容に従って themes/ へ battle_id をコピー（3段階）"""
    SORTING_JSON_PATH = os.path.join(ROOT, "reports", "Sorting.json")
    THEMES_BASE_DIR = os.path.join(ROOT, "themes")

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"=== Step: 対局データのテーマ別コピー 開始 ===\n")
        f.write(f"ソースディレクトリ: {run_dir}\n")
    print(f"=== Step: 対局データのテーマ別コピー 開始 ===")
    print(f"ソースディレクトリ: {run_dir}")

    if not os.path.exists(SORTING_JSON_PATH):
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[ERROR] Sorting.json が見つかりません: {SORTING_JSON_PATH}\n")
        return

    try:
        with open(SORTING_JSON_PATH, "r", encoding="utf-8") as f:
            sorting_data = json.load(f)
    except Exception as e:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"[ERROR] JSONの読み込みに失敗しました: \n{e}\n")
        return

    themes = sorting_data.get("themes", {})
    if not themes:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("[INFO] 移動対象のテーマ設定が空です。\n")
        return

    for theme_name, info in themes.items():
        dir_name = info.get("dir_name")
        games = info.get("games", [])

        if not dir_name:
            continue

        for game_id in games:
            src_game_path = os.path.join(run_dir, game_id)
            if not os.path.exists(src_game_path):
                continue

            # ① 日本語テーマ名
            dest1 = os.path.join(THEMES_BASE_DIR, theme_name, game_id)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[TRY] 日本語テーマ名: {theme_name} / {game_id}\n")
            print(f"  [TRY] 日本語テーマ名: {theme_name} / {game_id}")
            if try_copy(src_game_path, dest1, game_id, log_path, "日本語テーマ名"):
                continue

            # ② dir_name
            dest2 = os.path.join(THEMES_BASE_DIR, dir_name, game_id)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[TRY] dir_name: {dir_name} / {game_id}\n")
            print(f"  [TRY] dir_name: {dir_name} / {game_id}")
            if try_copy(src_game_path, dest2, game_id, log_path, "dir_name"):
                continue

            # ③ その他
            dest3 = os.path.join(THEMES_BASE_DIR, "その他", game_id)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[TRY] その他: {game_id}\n")
            print(f"  [TRY] その他: {game_id}")
            try_copy(src_game_path, dest3, game_id, log_path, "その他")

    with open(log_path, "a", encoding="utf-8") as f:
        f.write("=== テーマ別コピー 完了 ===\n")
    print("=== テーマ別コピー 完了 ===")


# ============================================================
# 実行部分
# ============================================================

def run(ROOT, log_path):
    base_dir = os.path.join(ROOT, "temp")
    for trg_folder in os.listdir(base_dir):
        trg_path = os.path.join(base_dir, trg_folder)
        if not (os.path.isdir(trg_path) and trg_folder.startswith("trg_")):
            continue
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"=== branch_out: {trg_folder} ===\n")
        print(f"=== branch_out: {trg_folder} ===")

        # 6.1 戦型別へコピー
        copy_to_style_dir(ROOT, log_path, trg_path)

        # 6.2 themes/ へコピー（3段階）
        copy_to_theme_dir(ROOT, log_path, trg_path)


if __name__ == "__main__":
    # ROOT = r"C:\Users\Michiaki\Auto-Shogi-Report"
    # log_path = r"C:\Users\Michiaki\Auto-Shogi-Report\log_.txt"
    run(ROOT, log_path)
