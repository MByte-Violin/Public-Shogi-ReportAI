import os
import shutil

def trg_dir(ROOT, log_path, run_dir):
    backup_dir = os.path.join(ROOT, "backup")
    os.makedirs(backup_dir ,exist_ok=True)

    if not os.path.exists(run_dir):
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"指定されたディレクトリが存在しません: {run_dir}\n")
        return

    os.makedirs(backup_dir, exist_ok=True)

    # run_dir 直下のディレクトリをすべて移動
    for entry in os.listdir(run_dir):
        entry_path = os.path.join(run_dir, entry)
        if os.path.isdir(entry_path):
            dst_path = os.path.join(backup_dir, entry)
            print(f" [Move] {entry} → {backup_dir}")
            shutil.move(entry_path, dst_path)


    # run_dir を削除（空であることを確認）
    try:
        os.rmdir(run_dir)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"run_dir を削除しました: {run_dir}\n")
        print(f"\n✅ run_dir を削除しました: {run_dir}")
    except OSError as e:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"n[Warning] run_dir の削除に失敗しました（空でない可能性あり）: {run_dir} → {e}n")
        print(f"\n[Warning] run_dir の削除に失敗しました（空でない可能性あり）: {run_dir} → {e}")

# ============================================================
# 実行部分
# ============================================================

def run(ROOT, log_path):
    base_dir = os.path.join(ROOT, "temp")
    for trg_folder in os.listdir(base_dir):
        trg_path = os.path.join(base_dir, trg_folder) 
        # trg_ から始まるディレクトリ以外はスキップ
        if not (os.path.isdir(trg_path) and trg_folder.startswith("trg_")):
            continue
        trg_dir(ROOT, log_path, trg_path)

if __name__ == "__main__":
    run(ROOT, log_path)
