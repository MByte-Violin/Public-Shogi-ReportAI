import os
import re
import glob
import requests
import datetime
import shutil
from typing import List, Dict, Any

WARS_ID = os.getenv("WARS_ID", "")
BASE_URL = "https://www.shogi-extend.com"

# 未解析のballe_idが5個以上あったらダウンロードはしない。
def has_many_missing_reports(root_path: str) -> bool:
    temp_path = os.path.join(root_path, "temp")
    if not os.path.isdir(temp_path):
        return False  # tempディレクトリが存在しない場合はFalse

    missing_count = 0

    for entry in os.listdir(temp_path):
        trg_path = os.path.join(temp_path, entry)
        if os.path.isdir(trg_path) and entry.startswith("trg_"):
            for battle_id in os.listdir(trg_path):
                battle_path = os.path.join(trg_path, battle_id)
                if os.path.isdir(battle_path):
                    report_path = os.path.join(battle_path, "local_report.json")
                    if not os.path.isfile(report_path):
                        missing_count += 1
                        if missing_count >= 5:
                            return True  # 5つ見つけた時点でTrueを返す

    return False  # 5つ未満ならFalse



def fetch_battles_raw(ROOT, log_path, wars_id: str, count: int = 100) -> List[Dict[str, Any]]:
    url = f"{BASE_URL}/w.json?query={wars_id}&per={count}"
    resp = requests.get(url)
    resp.raise_for_status()

    data = resp.json()
    records = data.get("records", [])

    battles = []
    for rec in records:
        show_path = rec.get("show_path")
        if not show_path:
            continue

        battle_id = show_path.split("/")[-1]
        battles.append({
            "show_path": show_path,
            "battle_id": battle_id,
        })

    return battles


def fetch_kif(ROOT, log_path, show_path: str) -> str:
    kif_url = f"{BASE_URL}{show_path}.kif"
    resp = requests.get(kif_url)
    resp.raise_for_status()
    return resp.text


def create_run_directory(ROOT, log_path) -> str:
    base_dir = os.path.join(ROOT, "temp")
    now = datetime.datetime.now()
    dirname = f"trg_{now.strftime('%Y%m%d_%H%M')}"
    full_path = os.path.join(base_dir, dirname)

    os.makedirs(full_path, exist_ok=True)
    return full_path


def save_raw_kif(run_dir: str, battle_id: str, kif_text: str):
    battle_dir = os.path.join(run_dir, battle_id)
    os.makedirs(battle_dir, exist_ok=True)

    kif_path = os.path.join(battle_dir, "raw.kif")
    with open(kif_path, "w", encoding="utf-8") as f:
        f.write(kif_text)

    print(f"Saved: {kif_path}")


def is_user_lost(kif_text: str, wars_id: str = WARS_ID) -> bool:
    """raw.kif からユーザーが負けたか判定する"""
    is_sente = False
    is_gote = False
    for line in kif_text.splitlines():
        if f"先手：{wars_id}" in line or f"先手: {wars_id}" in line:
            is_sente = True
        if f"後手：{wars_id}" in line or f"後手: {wars_id}" in line:
            is_gote = True
    sente_won = "先手の勝ち" in kif_text or "先手勝ち" in kif_text
    gote_won = "後手の勝ち" in kif_text or "後手勝ち" in kif_text
    if is_sente:
        return gote_won   # 先手がユーザー → 後手が勝ったら負け
    elif is_gote:
        return sente_won  # 後手がユーザー → 先手が勝ったら負け
    return False  # 判定不能の場合は負けではないとみなす


# ---------------------------------------------------------
# 1.2 重複除去
# ---------------------------------------------------------
def cleanup_duplicate_kif(ROOT, log_path, run_dir: str):
    temp_root = os.path.join(ROOT, "temp")
    thema_root = os.path.join(ROOT, "戦型別")  # themes → 戦型別 に変更
    back_up_root = os.path.join(ROOT, "backup")

    with open(log_path, "a", encoding="utf-8") as f:
        f.write("=== 重複KIFチェック開始 ===\n")
    print("=== 重複KIFチェック開始 ===")

    # 1. now_kif_list
    now_kif_list = [
        d for d in os.listdir(run_dir)
        if os.path.isdir(os.path.join(run_dir, d))
    ]

    # 2. existing_kif_list（今回以外のtrgフォルダ）
    existing_kif_list = []
    for trg in os.listdir(temp_root):
        trg_path = os.path.join(temp_root, trg)
        if not os.path.isdir(trg_path):
            continue
        if trg_path == run_dir:
            continue  # 今回のtrgは除外

        for d in os.listdir(trg_path):
            if os.path.isdir(os.path.join(trg_path, d)):
                existing_kif_list.append(d)

    # 3. thema_kif_list（戦型別/ 配下を再帰的に走査）
    # 新仕様: 戦型別/相手の戦型/dir_name/battle_id という3階層構造
    thema_kif_list = []
    if os.path.exists(thema_root):
        for root_dir, dirs, files in os.walk(thema_root):
            for d in dirs:
                # battle_id は末尾が YYYYMMDD_HHMMSS 形式
                if re.match(r'.+-\d{8}_\d{6}$', d):
                    thema_kif_list.append(d)

    # 3'. back_up_kif_list
    back_up_kif_list = []
    if os.path.exists(back_up_root):
        for back_up in os.listdir(back_up_root):
            back_up_kif_list.append(back_up)

    # 4. 既存KIFセットを構築
    existing_kif_set = set(existing_kif_list)
    existing_kif_set.update(thema_kif_list)
    existing_kif_set.update(back_up_kif_list)

    # 5. delete_kif_list
    delete_kif_list = [d for d in now_kif_list if d in existing_kif_set]

    # 6. 削除実行
    for d in delete_kif_list:
        target = os.path.join(run_dir, d)
        if os.path.exists(target):
            shutil.rmtree(target)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[削除] 重複のため削除: {target}\n")
            print(f"[削除] 重複のため削除: {target}")

    with open(log_path, "a", encoding="utf-8") as f:
        f.write("=== 重複KIFチェック完了 ===\n")
    print("=== 重複KIFチェック完了 ===")


# ---------------------------------------------------------
# 1.3 古いデータ除外
# ---------------------------------------------------------
def exclude_by_date(ROOT, log_path, run_dir: str):
    """最新 trend_report より古い対局を処理（負け→削除、勝ち→backup移動）"""
    reports_dir = os.path.join(ROOT, "reports")
    backup_root = os.path.join(ROOT, "backup")

    with open(log_path, "a", encoding="utf-8") as f:
        f.write("=== 古いデータ除外開始 ===\n")
    print("=== 古いデータ除外開始 ===")

    # 最新 trend_report の日付を取得
    trend_files = glob.glob(os.path.join(reports_dir, "trend_report*.md"))
    if not trend_files:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("[SKIP] trend_report が存在しないため、古いデータ除外をスキップ\n")
        print("[SKIP] trend_report が存在しないためスキップ")
        return

    latest_date = None
    for tf in trend_files:
        m = re.search(r'trend_report(\d{8})\.md', os.path.basename(tf))
        if m:
            d = datetime.datetime.strptime(m.group(1), "%Y%m%d")
            if latest_date is None or d > latest_date:
                latest_date = d

    if latest_date is None:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("[SKIP] trend_report の日付が取得できないためスキップ\n")
        print("[SKIP] trend_report の日付が取得できないためスキップ")
        return

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"最新 trend_report の日付: {latest_date.strftime('%Y%m%d')}\n")
    print(f"最新 trend_report の日付: {latest_date.strftime('%Y%m%d')}")

    for battle_id in list(os.listdir(run_dir)):
        battle_path = os.path.join(run_dir, battle_id)
        if not os.path.isdir(battle_path):
            continue

        # battle_id 末尾から日付を取得（例: 先手ユーザー-後手ユーザー-YYYYMMDD_hhmmss）
        m = re.search(r'(\d{8})_\d{6}$', battle_id)
        if not m:
            continue

        battle_date = datetime.datetime.strptime(m.group(1), "%Y%m%d")
        if battle_date >= latest_date:
            continue  # 最新 trend_report 以降のデータはそのまま

        # 古いデータの処理
        kif_path = os.path.join(battle_path, "raw.kif")
        lost = True  # デフォルトは負けとみなす
        if os.path.exists(kif_path):
            with open(kif_path, "r", encoding="utf-8") as f:
                kif_text = f.read()
            lost = is_user_lost(kif_text)

        if lost:
            # 負け → 削除
            shutil.rmtree(battle_path)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[除外/削除] 古い負け対局: {battle_id}\n")
            print(f"[除外/削除] 古い負け対局: {battle_id}")
        else:
            # 勝ち → backup へ移動
            os.makedirs(backup_root, exist_ok=True)
            dest = os.path.join(backup_root, battle_id)
            if not os.path.exists(dest):
                shutil.move(battle_path, dest)
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"[除外/backup] 古い勝ち対局を移動: {battle_id}\n")
                print(f"[除外/backup] 古い勝ち対局を移動: {battle_id}")
            else:
                shutil.rmtree(battle_path)
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"[除外/削除] backup に既存のため削除: {battle_id}\n")
                print(f"[除外/削除] backup に既存のため削除: {battle_id}")

    with open(log_path, "a", encoding="utf-8") as f:
        f.write("=== 古いデータ除外完了 ===\n")
    print("=== 古いデータ除外完了 ===")


# ---------------------------------------------------------
# 1.4 最新10局絞り込み
# ---------------------------------------------------------
def limit_to_latest_10(ROOT, log_path, run_dir: str):
    """local_report.json が存在しない対局を処理:
    - 勝ち対局 → backup へ移動
    - 負け対局 → 最新10局のみ残す（それより古いものは削除）
    """
    backup_root = os.path.join(ROOT, "backup")

    with open(log_path, "a", encoding="utf-8") as f:
        f.write("=== 最新10局絞り込み開始 ===\n")
    print("=== 最新10局絞り込み開始 ===")

    # local_report.json が存在しない battle_id を収集
    unanalyzed = []
    for battle_id in os.listdir(run_dir):
        battle_path = os.path.join(run_dir, battle_id)
        if not os.path.isdir(battle_path):
            continue
        if os.path.exists(os.path.join(battle_path, "local_report.json")):
            continue  # 既に解析済みはスキップ
        unanalyzed.append(battle_id)

    # 日付降順でソート（battle_id末尾のYYYYMMDD_hhmmssを基準）
    def get_battle_datetime(bid):
        m = re.search(r'(\d{8}_\d{6})$', bid)
        if m:
            try:
                return datetime.datetime.strptime(m.group(1), "%Y%m%d_%H%M%S")
            except ValueError:
                pass
        return datetime.datetime.min

    unanalyzed.sort(key=get_battle_datetime, reverse=True)

    # 勝ち対局を backup へ移動、負け対局リストを構築
    lost_games = []
    for battle_id in unanalyzed:
        battle_path = os.path.join(run_dir, battle_id)
        kif_path = os.path.join(battle_path, "raw.kif")
        lost = False  # デフォルトは勝ちとみなす(例外棋譜を解析させないため)
        if os.path.exists(kif_path):
            with open(kif_path, "r", encoding="utf-8") as f:
                kif_text = f.read()
            lost = is_user_lost(kif_text)

        if not lost:
            # 勝ち → backup へ移動
            os.makedirs(backup_root, exist_ok=True)
            dest = os.path.join(backup_root, battle_id)
            if not os.path.exists(dest):
                shutil.move(battle_path, dest)
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"[backup] 勝ち対局を移動: {battle_id}\n")
                print(f"[backup] 勝ち対局を移動: {battle_id}")
            else:
                shutil.rmtree(battle_path)
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(f"[削除] backup に既存のため削除: {battle_id}\n")
                print(f"[削除] backup に既存のため削除: {battle_id}")
        else:
            lost_games.append(battle_id)

    # 負け対局: 最新10局以外を削除
    #to_delete = lost_games[40:]
    to_delete = lost_games[10:]
    for battle_id in to_delete:
        target = os.path.join(run_dir, battle_id)
        if os.path.exists(target):
            shutil.rmtree(target)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[削除] 11局目以降のため削除: {battle_id}\n")
                #f.write(f"[削除] 41局目以降のため削除: {battle_id}\n")
            print(f"[削除] 11局目以降のため削除: {battle_id}")

    remaining = len(lost_games) - len(to_delete)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"=== 最新10局絞り込み完了: 残り未解析(負け) {remaining} 局 ===\n")
        #f.write(f"=== 最新40局絞り込み完了: 残り未解析(負け) {remaining} 局 ===\n")
    print(f"=== 最新10局絞り込み完了: 残り未解析(負け) {remaining} 局 ===")


# ---------------------------------------------------------
# run() に組み込み
# ---------------------------------------------------------
def run(ROOT, log_path):
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"=== Step1: 棋譜ダウンロード ===\n")
    print("=== Step1: 棋譜ダウンロード ===")

    run_dir =""
    flag = has_many_missing_reports(ROOT)
    if flag:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"=== 未解析が多いため、ダウンロードを中止 ===\n")
        print("=== 未解析が多いため、ダウンロードを中止 ===")

    else:
        run_dir = create_run_directory(ROOT, log_path)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"保存先ディレクトリ: {run_dir}\n")
        print(f"保存先ディレクトリ: {run_dir}")

        battles = fetch_battles_raw(ROOT, log_path, wars_id=WARS_ID, count=100)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"取得した対局数: {len(battles)}\n")
        print(f"取得した対局数: {len(battles)}")

        for b in battles:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"Fetching KIF for {b['battle_id']} ...\n")
            print(f"Fetching KIF for {b['battle_id']} ...")
            kif_text = fetch_kif(ROOT, log_path, b["show_path"])
            save_raw_kif(run_dir, b["battle_id"], kif_text)

        cleanup_duplicate_kif(ROOT, log_path, run_dir)
        exclude_by_date(ROOT, log_path, run_dir)
        limit_to_latest_10(ROOT, log_path, run_dir)

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"=== Step1 完了 ===\n")
    print("=== Step1 完了 ===")

    return run_dir


if __name__ == "__main__":
    run_dir = run(ROOT, log_path)
