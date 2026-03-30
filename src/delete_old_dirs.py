import os
import shutil
import re
from datetime import datetime, timedelta

def run(ROOT, log_path):
    base_dirs = [
        os.path.join(ROOT, "backup"),
        os.path.join(ROOT, "temp"),
        os.path.join(ROOT, "themes"),
        os.path.join(ROOT, "戦型別"),
    ]

    cutoff = datetime.now() - timedelta(days=90)  # 3ヶ月 ≈ 90日
    dir_pattern = re.compile(r'.+-\d{8}_\d{6}$')

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"=== delete_old_dirs 開始: cutoff={cutoff.strftime('%Y-%m-%d')} ===\n")
    print(f"=== delete_old_dirs 開始: cutoff={cutoff.strftime('%Y-%m-%d')} ===")

    deleted_count = 0

    for base in base_dirs:
        if not os.path.exists(base):
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[Skip] ディレクトリが見つかりません: {base}\n")
            print(f"[Skip] ディレクトリが見つかりません: {base}")
            continue

        # battle_id ディレクトリを再帰走査（topdown=False で子から削除）
        for root, dirs, files in os.walk(base, topdown=False):
            for d in list(dirs):
                if not dir_pattern.match(d):
                    continue
                try:
                    date_part = d.split('-')[-1]
                    dt = datetime.strptime(date_part, "%Y%m%d_%H%M%S")
                except ValueError:
                    continue

                if dt < cutoff:
                    full_path = os.path.join(root, d)
                    try:
                        shutil.rmtree(full_path)
                        with open(log_path, "a", encoding="utf-8") as f:
                            f.write(f"[Deleted] {full_path}\n")
                        print(f"[Deleted] {full_path}")
                        deleted_count += 1
                    except Exception as e:
                        with open(log_path, "a", encoding="utf-8") as f:
                            f.write(f"[Error] {full_path} の削除に失敗: {e}\n")
                        print(f"[Error] {full_path} の削除に失敗: {e}")

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"古いデータ削除完了: {deleted_count} 個のディレクトリを削除しました。\n")
    print(f"古いデータ削除完了: {deleted_count} 個のディレクトリを削除しました。")

    # ---------------------------------------------------------
    # logs ディレクトリ: 100件超で古いものから削除
    # ---------------------------------------------------------
    logs_dir = os.path.join(ROOT, "logs")
    log_file_pattern = re.compile(r"log_(\d{8}_\d{6})\.txt$")

    if os.path.exists(logs_dir):
        log_files = []
        for fname in os.listdir(logs_dir):
            match = log_file_pattern.match(fname)
            if match:
                date_str = match.group(1)
                try:
                    dt = datetime.strptime(date_str, "%Y%m%d_%H%M%S")
                    log_files.append({
                        "path": os.path.join(logs_dir, fname),
                        "datetime": dt
                    })
                except ValueError:
                    continue

        log_files.sort(key=lambda x: x["datetime"], reverse=True)

        if len(log_files) > 100:
            to_delete = log_files[100:]
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"logs ディレクトリに {len(log_files)} 個のログがあり、古いものを削除します...\n")
            print(f"logs ディレクトリに {len(log_files)} 個のログがあり、古いものを削除します...")
            for item in to_delete:
                try:
                    os.remove(item["path"])
                    with open(log_path, "a", encoding="utf-8") as f:
                        f.write(f"[Log Deleted] {item['path']}\n")
                    print(f"[Log Deleted] {item['path']}")
                except Exception as e:
                    with open(log_path, "a", encoding="utf-8") as f:
                        f.write(f"[Error] ログ削除失敗: {item['path']} : {e}\n")
                    print(f"[Error] ログ削除失敗: {item['path']} : {e}")
        else:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"logs ディレクトリは {len(log_files)} 個のため削除不要。\n")
    else:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("[Skip] logs ディレクトリが存在しません。\n")
        print("[Skip] logs ディレクトリが存在しません。")


if __name__ == "__main__":
    run(ROOT, log_path)
