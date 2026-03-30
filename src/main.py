#pyinstaller --onefile main.py
import os
import sys
import traceback
from datetime import datetime, timedelta

# 各モジュールのインポート
import kif_download
import gemini_local
import set_local_sammarys
import gemini_trend
import make_xlsx
import branch_out
import sorting
import move_backup
import delete_old_dirs

sys.stdout.reconfigure(encoding='utf-8')

def now_jst():
    return datetime.now() + timedelta(hours=9)

def main():
    # ルートの設定
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(sys.argv[0])))
    stage = 0
    try:
        # 初期設定
        start = now_jst().strftime("%Y-%m-%d %H:%M:%S")
        WARS_ID = os.getenv("WARS_ID", "")
        print(f"--- WARS_ID= {WARS_ID} ---\n")
        if WARS_ID == "":
            print("ウォーズIDが設定されていません。")
            raise RuntimeError("ウォーズIDが設定されていません。")
        
        # 段階0: 必要なディレクトリを作成（themes/ は作成しない）
        os.makedirs(os.path.join(ROOT, 'backup'), exist_ok=True)
        os.makedirs(os.path.join(ROOT, 'logs'), exist_ok=True)
        os.makedirs(os.path.join(ROOT, 'reports'), exist_ok=True)
        os.makedirs(os.path.join(ROOT, 'temp'), exist_ok=True)
        os.makedirs(os.path.join(ROOT, '戦型別'), exist_ok=True)
        os.makedirs(os.path.join(ROOT, 'themes'), exist_ok=True)

        log_path = os.path.join(ROOT, "logs", "log_" + str(now_jst().strftime("%Y%m%d_%H%M%S")) + ".txt")
        print(f"--- Pipeline Start: {now_jst()} ---")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"--- Pipeline Start: {now_jst()} ---\n")
            
        error_msg = ""
        made_report = False

        # 段階1: 棋譜取得
        stage = 1
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"--- [段階{stage}] kif_download 開始: {now_jst()} ---\n")
        print(f"--- [段階{stage}] kif_download 開始 ---")
        kif_download.run(ROOT, log_path)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"--- [段階{stage}] kif_download 完了: {now_jst()} ---\n")
        print(f"--- [段階{stage}] kif_download 完了 ---")

        # 段階2: 局所分析（raw.kif → Gemini → local_report.pdf + local_report.json）
        stage = 2
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"--- [段階{stage}] gemini_local 開始: {now_jst()} ---\n")
        print(f"--- [段階{stage}] gemini_local 開始 ---")
        gemini_local.run(ROOT, log_path)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"--- [段階{stage}] gemini_local 完了: {now_jst()} ---\n")
        print(f"--- [段階{stage}] gemini_local 完了 ---")

        # 段階3: レポート集約（local_report.json → local_summarys.json）
        stage = 3
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"--- [段階{stage}] set_local_sammarys 開始: {now_jst()} ---\n")
        print(f"--- [段階{stage}] set_local_sammarys 開始 ---")
        set_local_sammarys.run(ROOT, log_path)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"--- [段階{stage}] set_local_sammarys 完了: {now_jst()} ---\n")
        print(f"--- [段階{stage}] set_local_sammarys 完了 ---")

        # 段階4: 傾向分析（条件付き：今月未作成 AND 未解析40局以上）
        stage = 4
        trend_trg = gemini_trend.should_run_trend(ROOT)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"--- trend_trg={trend_trg} ---\n")
        #trend_trg = True # デバック用
        if trend_trg:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"--- [段階{stage}] gemini_trend 実行条件 OK: {now_jst()} ---\n")
            print(f"--- [段階{stage}] gemini_trend を実行します ---")

            made_report = gemini_trend.run(ROOT, log_path)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"--- [段階{stage}] gemini_trend 完了: made_report={made_report}: {now_jst()} ---\n")

            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"--- [段階{stage}] sorting 開始: {now_jst()} ---\n")
            print(f"--- [段階{stage}] sorting 開始 ---")
            sorting.run(ROOT, log_path)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"--- [段階{stage}] sorting 完了: {now_jst()} ---\n")
            print(f"--- [段階{stage}] sorting 完了 ---")

            # # 段階5: 将棋の敗因傾向.xlsx 作成
            stage = 5
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"--- [段階{stage}] make_xlsx 開始: {now_jst()} ---\n")
            print(f"--- [段階{stage}] make_xlsx 開始 ---")
            make_xlsx.run(ROOT, log_path)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"--- [段階{stage}] make_xlsx 完了: {now_jst()} ---\n")
            print(f"--- [段階{stage}] make_xlsx 完了 ---")

            # 段階6: 戦型別×敗因別分類（made_report のとき実行）
            stage = 6
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"--- [段階{stage}] branch_out 開始: {now_jst()} ---\n")
            print(f"--- [段階{stage}] branch_out 開始 ---")
            branch_out.run(ROOT, log_path)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"--- [段階{stage}] branch_out 完了: {now_jst()} ---\n")
            print(f"--- [段階{stage}] branch_out 完了 ---")

            # 段階7: バックアップ・古いデータ削除
            stage = 7
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"--- [段階{stage}] move_backup 開始: {now_jst()} ---\n")
            print(f"--- [段階{stage}] move_backup 開始 ---")
            move_backup.run(ROOT, log_path)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"--- [段階{stage}] move_backup 完了: {now_jst()} ---\n")
            print(f"--- [段階{stage}] move_backup 完了 ---")

            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"--- [段階{stage}] delete_old_dirs 開始: {now_jst()} ---\n")
            print(f"--- [段階{stage}] delete_old_dirs 開始 ---")
            delete_old_dirs.run(ROOT, log_path)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"--- [段階{stage}] delete_old_dirs 完了: {now_jst()} ---\n")
            print(f"--- [段階{stage}] delete_old_dirs 完了 ---")

        # 段階8: ログ管理まとめ
        stage = 8
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"--- Pipeline Completed: {now_jst()} ---\n")
        print(f"--- Pipeline Completed: {now_jst()} ---")

    except Exception as e:
        error_msg = f"Error at Stage {stage}, {now_jst()}:\n{traceback.format_exc()}\n"
        print(error_msg)
        # log_path が未設定の場合のフォールバック
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[ERROR 段階{stage}] {error_msg}\n")
        except Exception:
            pass

    finish = now_jst().strftime("%Y-%m-%d %H:%M:%S")
    print("プログラムの実行時刻:", start if 'start' in dir() else "不明")
    print("プログラムの終了時刻:", finish)
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("プログラム終了\n")
            f.write(f"プログラムの実行時刻:{start if 'start' in dir() else '不明'}\n")
            f.write(f"プログラムの終了時刻:{finish}\n")
            f.write(f"最終到達段階={stage}\n")
            f.write(f"made_report={made_report}\n")
            f.write(f"error_msg=\n{error_msg}")
    except Exception:
        pass

if __name__ == "__main__":
    main()
