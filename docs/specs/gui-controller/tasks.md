# Tasks — gui-controller

> 逆生成 spec。`src/gui_controller.py` のテストカバレッジ状況と、未文書化挙動・テスト不足・将来改善を列挙する。

## テストカバレッジ状況（逆生成時）

専用テスト [`tests/test_gui_controller.py`](../../../tests/test_gui_controller.py) は、純関数寄りのロジック（バッファ上限算出・FPS 算出・Queue drain・表示フレーム選択/オーバーレイミス・workers_alive）を `object.__new__` で UI を起こさずにカバーする。UI 構築・プロセス起動/停止・描画・終了処理は **未カバー**（tkinter / multiprocessing 依存のため）。

| 要求 ID | 対応テスト | 状態 |
|:--|:--|:--|
| R-GUI-11, R-GUI-12（バッファ上限） | `test_frame_buffer_max_uses_seconds_but_keeps_minimum` | ✅ カバー済み |
| R-GUI-14（Queue drain 件数） | `test_drain_queue_nowait_returns_drained_item_count` | ✅ カバー済み |
| R-GUI-29（一致フレーム優先＋古い破棄） | `test_select_display_frame_prefers_matching_tracking_frame` | ✅ カバー済み |
| R-GUI-30（オーバーレイミス一度だけ） | `test_select_display_frame_logs_stale_overlay_miss_once` | ✅ カバー済み |
| R-GUI-31（未着 frame_id はミスログ無し） | `test_select_display_frame_does_not_log_when_track_frame_is_pending` | ✅ カバー済み |
| R-GUI-37（FPS 算出） | `test_calculate_rate_uses_elapsed_between_samples` | ✅ カバー済み（算出のみ。ラベル更新は未） |
| R-GUI-42（workers_alive） | `test_workers_alive_checks_camera_and_tracking_processes` | ✅ カバー済み |
| R-GUI-01〜10（init/UI/プール/Queue 生成） | — | ⬜ 未カバー |
| R-GUI-13, R-GUI-15〜18（開始） | — | ⬜ 未カバー |
| R-GUI-19〜24（停止/強制終了） | — | ⬜ 未カバー |
| R-GUI-25〜28（GUI ループ/drain/結果保持） | — | ⬜ 未カバー |
| R-GUI-32〜36（空バッファ/描画/減光/状態色） | — | ⬜ 未カバー |
| R-GUI-38〜41, R-GUI-43（終了/cleanup/mainloop） | — | ⬜ 未カバー |
| R-GUI-44（ワーカーエラー→全停止+表示） | （`_handle_worker_error` 直接テストは未） | ⬜ 部分（実装済み） |
| R-GUI-46（error_queue 生成/受け渡し） | — | ⬜ 未カバー（実装済み） |
| R-GUI-47（error_queue drain） | `test_drain_worker_errors_returns_first_and_drains_rest` / `..._returns_none_when_empty` | ✅ カバー済み |
| R-GUI-48（開始時のエラーリセット） | — | ⬜ 未カバー（実装済み） |
| R-GUI-45（class_id 範囲外は無視） | （描画/リスト経路の直接テストは未） | ⬜ 部分（実装済み） |
| R-GUI-49（`_safe_class_name` 範囲チェック） | `test_safe_class_name_returns_name_in_range` / `..._returns_none_out_of_range` | ✅ カバー済み |

## タスク

### 文書化 / 整合
- [ ] README のモジュール構成図／設定表に、GUI が共有メモリプール owner であること・`frame_buffer_seconds` の意味（同期表示用バッファ秒数）を明記。
- [ ] `n_slots = max_queue_length + 2`・両プール同一 shape の前提を design に明記済み → README とも整合確認。
- [ ] borderless maximized と `Escape`/`Alt-F4` クローズの仕様を README（操作方法）に注記。

### テスト
- [ ] `_drain_frames` のバッファ上限超過時トリミング（最古破棄）（R-GUI-26）を `read_nowait` スタブで単体テスト。
- [ ] `_drain_track_results` が最新のみ保持し、Listbox を先頭10件＋"..."で更新すること（R-GUI-28）をスタブで検証。
- [ ] `_select_display_frame` の「バッファ空 → (None, None)」（R-GUI-32）を追加。
- [ ] `_stop_process`/`_terminate_process_if_alive` の段階的終了（join→terminate→kill）（R-GUI-23, R-GUI-24）を `Process` スタブで検証。
- [ ] `_update_gui` の render_key 差分（変化時のみ再描画）（R-GUI-33）を `_render_image` モックで検証。

### 実装（✅完了）
- [x] **ワーカーエラー通知の受信＋GUI 表示**（R-GUI-44, R-GUI-46〜48）: `data_models.WorkerError` を専用 `error_queue`（無制限 `multiprocessing.Queue`）で受け、`_handle_worker_error` で全停止→状態「エラー」（専用色＋メッセージ）→開始再有効化。camera R-CAM-14 / tracking R-OTC-23 と共通機構。**機構はステータス Queue に確定**。
- [x] `error_queue` 受信で「ワーカーの自然死/エラー死」を区別（自然死=stop_event 起因、エラー死=WorkerError 受信）。
- [ ] **`_handle_worker_error` の直接テスト**（R-GUI-44）: プロセス/プール stub で「stop_event セット・mark_inactive・状態エラー・開始再有効化」を検証（現状は drain 部のみカバー）。
- [x] **`class_id` 範囲外は無視**（R-GUI-45, R-GUI-49、**完了**）: 共通ヘルパ `_safe_class_name`（`:789-800`）で範囲チェックし、`_drain_track_results`（`:577-588`）は当該項目をスキップ、`_render_image`（`:647-665`）はクラス名を省いて `ID:<tracker_id> (<conf>)` のみ表示。`_safe_class_name` の単体テスト2本を追加。
- [ ] **描画/リスト経路の直接テスト**（R-GUI-45）: 範囲外 `class_id` を含む追跡結果で Listbox スキップ・ラベル省略を検証（GUI スタブ要）。描画側のラベル省略分岐は `RenderImageSmokeTest`（data-models ガードレール、`tests/test_gui_controller.py`）で通過済み。Listbox 側が残り。

### 実装 / 改善（将来）
- [ ] **「停止失敗」後はアプリ再起動を前提**（R-GUI-22、確定）: 停止失敗時に `_update_gui` が止まる（`stop_event` set 済み）が、リカバリ導線は設けず**最低限の実装**とする。状態「停止失敗」表示と再起動案内（ログ/UI 文言）に留める。出典 `src/gui_controller.py:444-454,762-763`。
- [ ] **`start_tracking` 例外のユーザー通知**: 起動失敗を GUI 上で可視化するか検討（現状は再 raise → `main.py` で stderr 出力＋終了）。R-GUI-44 の専用エラー表示に寄せる案も含める。
- [ ] **`_drain_track_results` の Listbox 全消去＋再挿入の最適化**: 多数追跡時の再描画コスト削減（差分更新等）。
- [ ] 型注釈の補強（`_select_display_frame`/`_render_image` の戻り値・引数型、`_frame_buffer: OrderedDict[int, np.ndarray]` 等）。

## メモ / 申し送り

- ✅ ワーカーエラー通知（R-GUI-44）は **実装済み**。`data_models.WorkerError` を専用 `error_queue`（`multiprocessing.Queue`、無制限）で受け、全停止＋状態「エラー」表示＋開始再有効化。camera R-CAM-14 / tracking R-OTC-23 と共通機構（**ステータス Queue に確定**）。
- ✅ 「停止失敗」後はアプリ再起動で復帰（R-GUI-22、最低限実装で許容）。
- ✅ `class_id` 範囲外（`class_names` 添字外）は**無視**して表示継続（R-GUI-45、**実装済み**）。共通ヘルパ `_safe_class_name`（R-GUI-49）でガード。リストはスキップ、オーバーレイは ID のみ表示。
- 🔎 `frame_read_policy`/`max_frame_skip` は **GUI 表示側に作用しない**（コード確認済み）。GUI は全カメラフレームをバッファ＋最新追跡結果で同期表示。ポリシーは tracking ワーカー入力読み出し専用。
- 🔎 **同期表示の核心**: 最新カメラフレームではなく「追跡結果の `frame_id` に一致するフレーム」へオーバーレイを描く。一致が破棄済みなら最新フレームをオーバーレイ無しで表示し、オーバーレイミスを一度だけ警告。
- 🔎 **render_key 差分描画**: `(表示 frame_id, オーバーレイ frame_id)` が不変なら再描画しない。
- 🔎 **共有メモリ安全性**: `reset_free_slots` は開始時（前回停止済み前提）、`cleanup` は終了時（全停止確認後のみ）。ワーカー生存中は cleanup をスキップして error ログ。
- 🔎 **段階的強制終了**: `join(5s)`→`terminate`→`join(2s)`→`kill`→`join(2s)`。
- 🔎 フレームバッファは `frame_id` 昇順の `OrderedDict`（最古=先頭/最新=末尾）。上限は `frame_buffer_seconds × fps` と `max_queue_length+2` の大きい方。
