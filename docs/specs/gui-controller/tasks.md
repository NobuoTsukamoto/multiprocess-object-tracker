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
| R-GUI-44（ワーカーエラー通知） | — | ⬜ 未カバー（改修予定・方針確定） |
| R-GUI-45（class_id 範囲外は無視） | — | ⬜ 未カバー（改修予定・方針確定） |

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

### 実装（✅方針確定・他 spec と連動）
- [ ] **ワーカーエラー通知の受信＋GUI 表示**（R-GUI-44）: camera R-CAM-14（オープン失敗）/ tracking R-OTC-23（ONNX ロード失敗）と**共通の専用通知**を受け、GUI に**専用エラー状態（専用の状態色＋エラー文）**を表示する。通知機構はエラー内容を運べる**ステータス Queue を推奨**（最終確定は実装時、3 モジュール横断で実装）。
- [ ] 上記に伴い `stop_tracking` の「停止失敗」と「ワーカーの自然死/エラー死」を区別できるようにする（現状はプロセス生存有無のみで判定）。
- [ ] **`class_id` 範囲外は無視**（R-GUI-45）: `_drain_track_results`（`:526-535`）と `_render_image`（`:591-606`）の `class_names[class_id]` を範囲チェックし、範囲外の項目はスキップして表示継続（例外で止めない）。

### 実装 / 改善（将来）
- [ ] **「停止失敗」後はアプリ再起動を前提**（R-GUI-22、確定）: 停止失敗時に `_update_gui` が止まる（`stop_event` set 済み）が、リカバリ導線は設けず**最低限の実装**とする。状態「停止失敗」表示と再起動案内（ログ/UI 文言）に留める。出典 `src/gui_controller.py:435-445,698-699`。
- [ ] **`start_tracking` 例外のユーザー通知**: 起動失敗を GUI 上で可視化するか検討（現状は再 raise → `main.py` で stderr 出力＋終了）。R-GUI-44 の専用エラー表示に寄せる案も含める。
- [ ] **`_drain_track_results` の Listbox 全消去＋再挿入の最適化**: 多数追跡時の再描画コスト削減（差分更新等）。
- [ ] 型注釈の補強（`_select_display_frame`/`_render_image` の戻り値・引数型、`_frame_buffer: OrderedDict[int, np.ndarray]` 等）。

## メモ / 申し送り

- ✅ ワーカーエラー通知（R-GUI-44）は camera R-CAM-14 / tracking R-OTC-23 と**同一の専用通知**で受け、GUI に専用エラー状態を表示する（方針確定）。機構はエラー内容を運べる**ステータス Queue を推奨**（最終確定は実装時）。
- ✅ 「停止失敗」後はアプリ再起動で復帰（R-GUI-22、最低限実装で許容）。
- ✅ `class_id` 範囲外（`class_names` 添字外）は**無視**して表示継続（R-GUI-45）。
- 🔎 `frame_read_policy`/`max_frame_skip` は **GUI 表示側に作用しない**（コード確認済み）。GUI は全カメラフレームをバッファ＋最新追跡結果で同期表示。ポリシーは tracking ワーカー入力読み出し専用。
- 🔎 **同期表示の核心**: 最新カメラフレームではなく「追跡結果の `frame_id` に一致するフレーム」へオーバーレイを描く。一致が破棄済みなら最新フレームをオーバーレイ無しで表示し、オーバーレイミスを一度だけ警告。
- 🔎 **render_key 差分描画**: `(表示 frame_id, オーバーレイ frame_id)` が不変なら再描画しない。
- 🔎 **共有メモリ安全性**: `reset_free_slots` は開始時（前回停止済み前提）、`cleanup` は終了時（全停止確認後のみ）。ワーカー生存中は cleanup をスキップして error ログ。
- 🔎 **段階的強制終了**: `join(5s)`→`terminate`→`join(2s)`→`kill`→`join(2s)`。
- 🔎 フレームバッファは `frame_id` 昇順の `OrderedDict`（最古=先頭/最新=末尾）。上限は `frame_buffer_seconds × fps` と `max_queue_length+2` の大きい方。
