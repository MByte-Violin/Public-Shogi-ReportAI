import os
import json


def run(ROOT, log_path):
    base_temp_dir = os.path.join(ROOT, "temp")
    output_path = os.path.join(base_temp_dir, "local_summarys.json")

    summary = {"各対局の振り返り": {}}
    error_files = []

    for root, dirs, files in os.walk(base_temp_dir):
        if "local_report.json" not in files:
            continue

        report_path = os.path.join(root, "local_report.json")
        try:
            with open(report_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            block = data.get("各対局の振り返り", {})
            if block:
                # 以前のgemini_local.pyのアップデートで追加した「解析URL」キーを除外して集約する
                filtered_block = {}
                for battle_id, details in block.items():
                    # 必要なキー（対局データ、将棋プロ棋士AIの解説）のみをコピー
                    filtered_details = {
                        "対局データ": details.get("対局データ"),
                        "将棋プロ棋士AIの解説": details.get("将棋プロ棋士AIの解説")
                    }
                    filtered_block[battle_id] = filtered_details
                
                summary["各対局の振り返り"].update(filtered_block)

        except Exception as e:
            error_files.append(f"{report_path}: {e}")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[ERROR] local_report.json 読み込み失敗: {report_path}: {e}\n")
            print(f"[ERROR] local_report.json 読み込み失敗: {report_path}: {e}")

    # 出力
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    count = len(summary["各対局の振り返り"])
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"=== Step3: local_summarys.json 集約完了: {count} 件 ===\n")
    print(f"=== Step3: local_summarys.json 集約完了: {count} 件 ===")


if __name__ == "__main__":
    # 実行環境に合わせて ROOT, log_path を定義して呼び出してください
    run(ROOT, log_path)
    pass
