# Tasks — camera-controller

> 逆生成 spec。`src/camera_controller.py` のテストカバレッジ状況と、未文書化挙動・テスト不足・将来改善を列挙する。

## テストカバレッジ状況（逆生成時）

[`tests/test_camera_controller.py`](../../../tests/test_camera_controller.py) が純関数寄りの `_fit_to_pool`/`_resolve_camera_source` に加え、`run()` の経路（open 失敗/grab 失敗/書き込み/ドロップ/finally）を `cv2.VideoCapture`・`SharedFrameAccessor` モック（`CameraRunTest`）でカバーする。

| 要求 ID | 対応テスト | 状態 |
|:--|:--|:--|
| R-CAM-01（Process サブクラス） | `InitStateTest::test_subclasses_multiprocessing_process` | ✅ カバー済み |
| R-CAM-02（init 状態） | `InitStateTest::test_init_keeps_collaborators_and_zeroes_frame_id` | ✅ カバー済み |
| R-CAM-03（子プロセスでアタッチ） | — | ⬜ 未カバー |
| R-CAM-04（open 失敗→終了） | `CameraRunTest::test_open_failure_reports_error_closes_pools_and_returns` | ✅ カバー済み |
| R-CAM-05（解像度/FPS 要求） | — | ⬜ 未カバー |
| R-CAM-06（stop まで反復） | `CameraRunTest::test_stop_event_exits_loop_and_releases_resources` | ✅ カバー済み |
| R-CAM-07（grab 失敗→warning+sleep） | `CameraRunTest::test_grab_failure_warns_and_continues` | ✅ カバー済み |
| R-CAM-08（shape 不一致→resize） | `FitToPoolTest::test_resizes_when_height_width_differ` / `::test_returns_frame_when_shape_already_matches` | ✅ カバー済み（`_fit_to_pool`） |
| R-CAM-09（両プール書き込み） | `CameraRunTest::test_frames_written_to_both_pools_with_incrementing_frame_id` | ✅ カバー済み |
| R-CAM-10（ドロップ→warning） | `CameraRunTest::test_write_failure_warns_per_pool_but_frame_id_advances` | ✅ カバー済み |
| R-CAM-11（frame_id 単調増加） | `CameraRunTest::test_frames_written_to_both_pools_with_incrementing_frame_id` | ✅ カバー済み |
| R-CAM-12（finally 後始末） | `CameraRunTest::test_stop_event_exits_loop_and_releases_resources` | ✅ カバー済み |
| R-CAM-13a〜d（source 型解釈・ルールB） | `ResolveCameraSourceTest`（int/数字文字列/パス・URL） | ✅ カバー済み（`_resolve_camera_source`、実装済み） |
| R-CAM-14（open 失敗→GUI 通知） | `CameraRunTest::test_open_failure_reports_error_closes_pools_and_returns` | ✅ カバー済み |
| R-CAM-15（チャンネル不一致→error+drop） | `FitToPoolTest`（`None` 返却）＋`CameraRunTest::test_channel_mismatch_frame_dropped_without_frame_id_increment`（run の error/continue/frame_id 非加算） | ✅ カバー済み |

## タスク

### 文書化 / 整合
- [x] ✅確定: 旧「Resize/pad」コメントを実装（resize＋チャンネル不一致ドロップ）に合わせて書き換え済み（`camera_controller.py:93-97`）。
- [ ] 解像度/FPS は「要求のみ（非保証）」である点を README へ補足。
- [x] `camera.source`（int/文字列対応）を README 設定表・`config/default.yaml`・config-manager spec に追記（**完了**）。

### テスト
- [x] `tests/test_camera_controller.py` を新設。`_fit_to_pool` の resize（R-CAM-08）／チャンネル不一致 `None`（R-CAM-15）を numpy 配列で検証。
- [x] init 状態のテスト（R-CAM-01/02、`InitStateTest`）: `Process` サブクラスであること、生成時に camera/logging 設定・両 spec・`stop_event`・`error_queue` を保持し `frame_id=0`・`logger=None` であることを検証。
- [x] `run()` 経路を `cv2.VideoCapture` モックで補完（`CameraRunTest`）。
  - [x] open 失敗時に error ログ＋`_report_error`＋プール close＋早期 return（R-CAM-04/14）。
  - [x] grab 失敗（ret=False）で warning＋sleep＋継続（R-CAM-07）。
  - [x] `_fit_to_pool` が `None` を返すフレームで error ログ＋`continue`＋`frame_id` 非加算（R-CAM-15）。
  - [x] 取得フレームが両プールへ write されること（R-CAM-09）。
  - [x] write が False のとき該当プール名で warning（R-CAM-10）。
  - [x] `frame_id` が反復ごとに +1（R-CAM-11）。
  - [x] `stop_event` セットでループ脱出＋release/close（R-CAM-06/12）。

### 実装（✅完了）
- [x] **カメラソースの設定キー化**（R-CAM-13a〜d、ルールB、**実装済み**）: `CameraConfig` に `source`（既定 `0`、`Union[int, str]`、`config_manager.py:14-15`）を追加。`_resolve_camera_source`（`camera_controller.py:51-61`）で int→そのまま / `[0-9]+` 文字列→`int()` / それ以外の文字列→そのまま と解釈し `cv2.VideoCapture(resolved)` へ（`:86-87`）。`config/default.yaml`・README・config-manager spec も同期。`ResolveCameraSourceTest` 3本を追加。
- [x] **オープン失敗の GUI 通知**（R-CAM-14、**実装済み**）: `error_queue` へ `data_models.WorkerError(source="camera", ...)` を送出（`_report_error`、`camera_controller.py:39-49,90`）。コンストラクタに `error_queue` 引数追加。GUI 側は [`gui-controller`](../gui-controller/) R-GUI-44 で受信・表示。機構は**ステータス Queue に確定**（tracking R-OTC-23 と共通）。
- [x] **`_report_error` のテスト**（R-CAM-14）: `error_queue` スタブで open 失敗時に `WorkerError(source="camera")` が put され早期 return することを検証（`CameraRunTest::test_open_failure_reports_error_closes_pools_and_returns`）。
- [x] **チャンネル不一致の error ドロップ**（R-CAM-15、**実装済み**）: `_fit_to_pool` が `cv2.resize` 後も shape 不一致なら `None` を返し、`run()` 側で error ログ＋`continue`（書き込みスキップ、`frame_id` 非加算）。`_fit_to_pool` の単体テスト2本を追加。
- [ ] grab 連続失敗は無限リトライのまま（R-CAM-07、変更不要）。

### 実装 / 改善（将来）
- [ ] 型注釈の補強（`run()` 内ローカルや戻り値）。
- [ ] フレーム書き込み失敗率（ドロップ率）のメトリクス化（performance ログ連携）。

## メモ / 申し送り

- ✅ カメラソースは `camera.source` で設定キー化（R-CAM-13a〜d、**実装済み**）。型解釈は**ルールB**（int / 数字文字列→int / それ以外→パスURL）。`_resolve_camera_source` + `ResolveCameraSourceTest`。
- ✅ open 失敗は GUI へ専用エラー通知（R-CAM-14、**実装済み**。`error_queue` + `WorkerError`、gui R-GUI-44 と共通・ステータス Queue に確定）。
- ✅ grab 連続失敗は無限リトライのまま（R-CAM-07、仕様確定）。
- ✅ チャンネル不一致は error ログ＋ドロップ（R-CAM-15、**実装済み**）。`_fit_to_pool`（`None`）→ run で `continue`（`frame_id` 非加算）。
- 🔎 両プールは GUI が同一 `frame_shape` で生成するため、`tracking_pool.shape` 基準のリサイズで GUI 用にも適合する（前提が崩れると GUI 用がドロップする）。
- 🔎 `frame_id` はプロセス生存中のみ単調増加。停止・再開で 0 にリセット（GUI の frame_id 突合に影響＝gui-controller spec で扱う）。
- 🔎 FPS ペーシングは `cap.read()` 依存（追加 sleep 無し）。
- ✅ `cv2.VideoCapture`/`SharedFrameAccessor` モックで `run()` 経路（open 失敗・grab 失敗・書き込み・ドロップ・finally）と init 状態（`InitStateTest`）を整備済み（計 15 テスト）。残りは子プロセス内アタッチ（R-CAM-03）・解像度/FPS 要求（R-CAM-05）・source 既定値（R-CAM-13d）のみ。
