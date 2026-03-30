# Public-Shogi-Report — CLAUDE.md

Claude Code がこのプロジェクトを正確に理解するためのリファレンス。
**ソースコードが「正」。このファイルや他のドキュメントとの矛盾はソースコードを優先すること。**

---

## プロジェクト概要

将棋ウォーズの棋譜を自動取得し、Gemini AI で解析・コーチングレポートを生成する **Python パイプライン** と、その結果をスマホ・Webから閲覧し Gemini と対話する **WebUI** の2層構成。ユーザーIDは `WARS_ID` 環境変数から取得。

- Pythonパイプライン: GitHub Actions で日本時間の毎日夜（am1時）に `src/main.exe` を実行
- WebUI: Render にデプロイし、GitHub リポジトリのデータを API 経由で閲覧

---

## 実行エントリーポイント

### Pythonパイプライン
```
src/main.py  （または PyInstaller でビルドした src/main.exe）
```
- `ROOT` は `main.exe` の1つ上のディレクトリ（= `Public-Shogi-Report/`）として算出
- 仮想環境: `C:\Python_venv\Shogi_analysis\Scripts`
- 環境変数: `WARS_ID`, `GEMINI_MODELS`, `API_KEY01`〜`API_KEY05`
  - `load_dotenv()` が有効。ローカルでは `.env` から読み込み、GitHub Actions では OS 環境変数（Secrets）から取得

### WebUI
```
npx tsx server.ts  （本番）
npm run dev        （開発: Vite + Express の統合起動）
```
- 環境変数: `APP_PASSCODE`（必須）, `REPO_ACCESS_TOKEN`（必須）, `GITHUB_OWNER`（必須）, `GITHUB_REPO`（必須）, `API_KEY01`〜`API_KEY05`, `GEMINI_MODELS`, `WARS_ID`
- `RENDER_GIT_BRANCH`（Renderが自動設定）が参照ブランチの優先度最高

---

## パイプライン（現在の実装）

**main.py は全段階が有効。コメントアウトなし。**
段階4〜7（xlsx 作成・分類・バックアップ・削除）は `trend_trg = True` のとき（＝傾向分析実行条件成立時）のみ実行される。

| 段階 | モジュール | 概要 |
|------|-----------|------|
| 0 | `main.py` | ディレクトリ作成（backup, logs, reports, temp, 戦型別, themes） |
| 1 | `kif_download.py` | 棋譜取得→重複除去→古いデータ除外→最新10局絞り込み |
| 2 | `gemini_local.py` | raw.kif → Gemini → local_report.pdf + local_report.json |
| 3 | `set_local_sammarys.py` | local_report.json 集約 → local_summarys.json |
| 4 | `gemini_trend.py` + `sorting.py` | 傾向分析レポート + Sorting.json 更新 |
| 5 | `make_xlsx.py` | 将棋の敗因傾向.xlsx 作成 |
| 6 | `branch_out.py` | 戦型別 / themes/ へコピー分類 |
| 7 | `move_backup.py` + `delete_old_dirs.py` | backup 移動・古いデータ削除 |
| 8 | `main.py` | ログ記録まとめ |

---

## ディレクトリ構成（実際）

```
Public-Shogi-Report/
├── [WebUI - ルート直下]
│   ├── server.ts              # Expressサーバー（APIエンドポイント）
│   ├── package.json           # Node.js依存関係
│   ├── vite.config.ts         # フロントエンドビルド設定
│   └── tsconfig.json
├── src/
│   ├── [Pythonパイプライン]
│   │   ├── main.py / main.exe     # エントリーポイント
│   │   ├── kif_download.py
│   │   ├── gemini_local.py
│   │   ├── set_local_sammarys.py
│   │   ├── gemini_trend.py
│   │   ├── sorting.py
│   │   ├── make_xlsx.py
│   │   ├── branch_out.py
│   │   ├── move_backup.py
│   │   └── delete_old_dirs.py
│   └── [WebUIフロントエンド]
│       ├── main.tsx           # Reactエントリーポイント
│       └── App.tsx            # シングルページアプリ本体
├── temp/
│   ├── trg_YYYYMMDD_HHMM/
│   │   └── {battle_id}/
│   │       ├── raw.kif
│   │       ├── response.txt           # Gemini解析テキスト（WebUIが参照）
│   │       ├── local_report.json      # 対局データ・解析結果・解析URL
│   │       ├── local_report.pdf
│   │       └── banmen_all_full.png    # 盤面図（WebUI表示用。削除対象外）
│   ├── rate_trg_YYYYMMDD_HHMM/   # 勝率集計用（make_xlsx が作成・削除）
│   └── local_summarys.json
├── backup/
│   └── {battle_id}/
├── 戦型別/
│   └── {戦型名}/
│       └── {battle_id}/
├── themes/                         # main.py が作成、branch_out.py が使用
│   └── {dir_name}/
│       └── {battle_id}/
├── reports/
│   ├── trend_reportYYYYMMDD.md
│   ├── Sorting.json
│   └── 将棋の敗因傾向.xlsx
├── logs/
│   └── log_YYYYMMDD_HHMMSS.txt
├── .env.example                    # 環境変数テンプレート
├── workspace/                      # 設計ドキュメント（参考資料）
├── Fonts/
├── requirements.txt
└── .github/workflows/auto-run.yml
```

---

## 各モジュール詳細（Pythonパイプライン）

### kif_download.py

**重要: ドキュメント未記載の関数あり**

| 関数 | 役割 |
|------|------|
| `has_many_missing_reports(ROOT)` | 未解析 battle_id が 5件以上あれば `True` を返す。`run()` がこれを先にチェックし、True なら新規ダウンロードをスキップする |
| `fetch_battles_raw()` | shogi-extend.com API から最大100件取得 |
| `fetch_kif()` | 個別 KIF をダウンロード |
| `create_run_directory()` | `temp/trg_YYYYMMDD_HHMM/` を作成して返す |
| `save_raw_kif()` | `{run_dir}/{battle_id}/raw.kif` に保存 |
| `is_user_lost()` | raw.kif からユーザーの勝敗を判定（`wars_id` 引数で対象ユーザーを指定） |
| `cleanup_duplicate_kif()` | temp/backup/戦型別 との重複を削除 |
| `exclude_by_date()` | 最新 trend_report より古い対局を処理（負け→削除、勝ち→backup） |
| `limit_to_latest_10()` | 未解析の負け対局を最新10局に絞り込み（勝ち→backup） |
| `run()` | 上記を順番に実行。`run_dir` を返す（main.py では使用しない） |

**勝敗判定（is_user_lost）:** raw.kif の「先手/後手：{WARS_ID}」と「先手の勝ち/後手の勝ち/勝者：▲/△」を組み合わせて判定。

---

### gemini_local.py

**実際の設定:**

```python
WARS_ID = os.getenv("WARS_ID", "")
FONT_NAME = "meiryo"
THINKING_MODELS = {"gemini-3.1-pro-preview", "gemini-3.1-flash-preview"}
_key_index = 0  # 次に使うAPIキーのインデックス（モジュールレベル、周回管理）
```

**処理フロー（1対局あたり）:**

1. `cut_unnecessary_kif()` で raw.kif の不要行をカット
2. `response.txt` が既に存在すれば再利用（API コスト削減ロジック）。なければ Gemini API 呼び出し → `response.txt` に保存
3. `txt_to_docx_with_images()` で `※※〇〇手目の局面※※` を抽出
4. Selenium で UserLocal 将棋解析サイトから局面スクリーンショット取得（最大5並列）
5. `make_report_pdf()` で PDF 生成（reportlab）
6. `local_report.pdf` / `local_report.json` を保存
7. `delete_png_and_docx_files()` で中間ファイル削除（`banmen_all_full.png` は残す）

**Gemini API 呼び出し（call_gemini_analysis）— モデルロールバック仕様:**
- `GEMINI_MODELS` 環境変数からモデルリストを構築
- 外ループ: モデルを先頭から順にトライ
- 内ループ: `_key_index` から始めて `API_KEY01`〜`API_KEY05` をローテーション
- 成功したら `_key_index = (idx + 1) % 5` に更新して終了（次局は次のキーから）
- キー失敗時: 10秒後に次のキーへ移行
- 全キー失敗時: 10秒待機して次のモデルへ移行
- `THINKING_MODELS` に含まれるモデルのみ `thinking_config` を適用（`thinking_level="high"`）
- 全モデル・全キー失敗時は `RuntimeError` を発生させる

**WebUI との連携:**
- `response.txt` — WebUI の server.ts が読み込み、Gemini チャットのコンテキストとして使用
- `banmen_all_full.png` — WebUI の盤面図表示に使用（削除対象から除外済み）
- `local_report.json` の `"解析URL"` — WebUI が UserLocal のリンクとして表示

---

### gemini_trend.py

```python
WARS_ID = os.getenv("WARS_ID", "")
THINKING_MODELS = {"gemini-3.1-pro-preview", "gemini-3.1-flash-preview"}
```

**実行条件（should_run_trend）:**
1. 今月の `trend_reportYYYYMMDD.md` が未作成
2. `local_summarys.json` の件数が 40 件以上

**Gemini API 呼び出し（call_gemini_trend）— モデルロールバック仕様:**
- `GEMINI_MODELS` 環境変数からモデルリストを構築
- 外ループ: モデルを先頭から順にトライ
- 内ループ: `API_KEY01`〜`API_KEY05` をローテーション
- `THINKING_MODELS` に含まれるモデルのみ `thinking_config` を適用
- 全モデル・全キー失敗時は空文字 `""` を返す

**実装済みの追加アップデート（run()内）:**
- `local_summarys.json` を読み込んだ後、日付降順で40局目以降を削除して上書き保存
- その後 Gemini API を呼び出す

**既知のバグ:**
- `get_latest_report()` 内で `return f.read()` の後にログ書き込みがあり到達しない

---

### sorting.py

```python
THINKING_MODELS = {"gemini-3.1-pro-preview", "gemini-3.1-flash-preview"}
```

- `API_KEY01`〜`API_KEY05` + `GEMINI_MODELS` を使用（モデルロールバック仕様）
- `response_mime_type="application/json"` でJSON出力モードを使用（thinking なし）
- 最新の `trend_report*.md` の「4. 敗因ごとのグループ分け」を読み取り
- 既存 `Sorting.json` に統合して上書き保存

---

### make_xlsx.py

**4つのシート:**
1. **戦型別頻度表** — `local_summarys.json` → `temp/backup/戦型別/` を走査して集計
2. **敗因別頻度表** — `Sorting.json` のテーマ別件数
3. **勝率推移表** — `kif_download` で100件ダウンロード → 30日以内のデータで集計
4. **勝率推移グラフ** — 折れ線グラフ

**勝率集計の実装済み追加アップデート:**
- 以前の `rate_trg_*` ディレクトリとの重複 battle_id を削除
- 旧 `rate_trg_*` ディレクトリを削除

**_is_user_lost()（make_xlsx.py 独自実装）:** `kif_download.py` の同名関数より詳細な判定あり（「勝者：▲」「勝者：△」も考慮）

---

### branch_out.py

- **6.1** `copy_to_style_dir()`: `戦型別/{相手の戦型}/{battle_id}/` へ `shutil.copytree`
- **6.2** `copy_to_theme_dir()`: `themes/{dir_name}/{battle_id}/` へ `shutil.copytree`
- `run()` は `temp/trg_*` を全て走査して両方を実行
- **注意:** `Sorting.json` が存在しない場合は 6.2 をスキップ

---

### delete_old_dirs.py

```python
base_dirs = ["backup", "temp", "themes", "戦型別"]  # themes も対象
cutoff = datetime.now() - timedelta(days=90)         # 90日（3ヶ月）以上前を削除
```

- `*-YYYYMMDD_HHMMSS` パターンの battle_id ディレクトリを再帰走査して削除
- `logs/` は 100件超で古いものから削除

---

### set_local_sammarys.py

- `temp/` 配下を再帰走査して `local_report.json` を収集
- `{"各対局の振り返り": { battle_id: {...} }}` 形式で集約
- `temp/local_summarys.json` に上書き保存

---

### move_backup.py

- `temp/trg_*` 配下の全 battle_id を `backup/` へ `shutil.move`
- 空になった `trg_*` ディレクトリを `os.rmdir` で削除

---

## WebUI サブシステム

### server.ts（Express バックエンド）

**起動時チェック:** `APP_PASSCODE`, `REPO_ACCESS_TOKEN`, `GITHUB_OWNER`, `GITHUB_REPO` が未設定の場合はエラーログを出力してプロセス終了。

**APIエンドポイント一覧:**

| メソッド | パス | 説明 |
|---------|------|------|
| POST | `/api/auth` | パスコード認証（`APP_PASSCODE` 環境変数と照合） |
| GET | `/api/github/categories/:category` | カテゴリ内ディレクトリ一覧（`temp` では `rate_trg_` プレフィックスを除外） |
| GET | `/api/github/battles/:category/:subCategory` | battle_id 一覧 |
| GET | `/api/github/report/:category/:subCategory/:battleId` | レポート詳細（response.txt・raw.kif・local_report.json・banmen_all_full.png を一括取得） |
| POST | `/api/chat` | Gemini AIチャット（GEMINI_MODELS モデルロールバック対応） |
| GET | `/api/health` | ヘルスチェック |

**GitHub API 参照ブランチの優先順位:**
1. `RENDER_GIT_BRANCH`（Renderが自動設定）
2. `GITHUB_BRANCH`（手動設定）
3. デフォルト: `"main"`

**画像取得の実装:**
- `banmen_all_full.png` は GitHub API の raw コンテンツを `arraybuffer` で取得し、Base64 エンコードして `data:image/png;base64,...` 形式でフロントエンドに返す
- battle_id ディレクトリ直下を先に試し、404 の場合は subCategory 直下も試す

**チャットモデル（server.ts）— モデルロールバック仕様:**
- `GEMINI_MODELS` 環境変数からモデルリストを構築
- `API_KEY01`〜`API_KEY05` をローテーション
- `THINKING_MODELS` に含まれるモデルのみ `ThinkingLevel.HIGH` を適用
- システムプロンプトに `raw.kif` と `response.txt` のテキストを埋め込む（`WARS_ID` 変数を動的挿入）
- SDK: `@google/genai`（`google.genai` とは別ライブラリ）

### App.tsx（React フロントエンド）

**画面遷移（ViewState）:**
- `login` → パスコード入力画面
- `dashboard` → 対局選択・プレビュー画面
- `chat` → Geminiチャット画面

**API通信フロー（dashboard 画面）:**
1. タブ選択 → `/api/github/categories/:category` でディレクトリ一覧取得
2. ディレクトリ選択 → `/api/github/battles/:category/:subCategory` で battle_id 一覧取得
3. battle_id 選択 → `/api/github/report/...` でレポート詳細取得

**サマリー抽出ロジック（server.ts内）:**
- `response.txt` から正規表現で「1. 対局の流れ・総評」以降〜「2. 私の敗因」直前を最大400文字抽出

---

## 重要な定数・仕様

| 項目 | ファイル | 値 |
|------|---------|-----|
| `WARS_ID` | 各ファイル共通 | `os.getenv("WARS_ID", "")` |
| `GEMINI_MODELS` | 各ファイル共通 | 環境変数から取得（デフォルト: gemini-3.1-pro-preview,... 5モデル） |
| `THINKING_MODELS` | gemini_local/trend/sorting/server.ts | `{"gemini-3.1-pro-preview", "gemini-3.1-flash-preview"}` |
| APIキー | 各ファイル共通 | `API_KEY01`〜`API_KEY05` |
| `FONT_NAME` | gemini_local.py | `"meiryo"` |
| 未解析スキップ閾値 | kif_download.py | 5件以上 |
| 最新局絞り込み数 | kif_download.py | 10局 |
| 傾向分析実行条件 | gemini_trend.py | 40局以上 |
| 古いデータ削除基準 | delete_old_dirs.py | 90日 |

---

## 既知のバグ

| ファイル | 内容 |
|---------|------|
| `gemini_trend.py` | `get_latest_report()` 内で `return f.read()` の後にログ書き込みがあり到達しない |

---

## 作業ルール

- ソースコードを修正する場合は、変更前に必ずソースを Read で読むこと
- ドキュメント（workspace/、README.md）はソースコードより後に書かれた情報であっても、ソースコードと矛盾する場合はソースコードを「正」とする
- GitHub Actions 環境は `windows-latest`。Word/LibreOffice は使用できないため PDF は reportlab で生成
- `load_dotenv()` は有効。ローカルでは `.env` から読み込む（`.env` は `.gitignore` で除外済み）
- PyInstaller ビルドコマンド: `pyinstaller --onefile main.py`（src/main.spec も存在）
- WebUI の Gemini SDK は Python 側（`google.genai`）と異なり `@google/genai` (Node.js) を使用
- 機密情報（WARS_ID・APIキー・アクセストークン）はすべて環境変数経由で取得する。コードへのハードコードは禁止
