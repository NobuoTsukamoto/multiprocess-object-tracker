# Requirements — camera-controller

> 逆生成 spec。出典は [`src/camera_controller.py`](../../../src/camera_controller.py)。コードが正。
> 記法は [`../../steering/conventions.md`](../../steering/conventions.md) の EARS 節に従う。
> **各要求に出典 `file:line` を付与済み。人手レビューで突き合わせること。**

## 対象 / スコープ

- **対象モジュール/機能**: [`src/camera_controller.py`](../../../src/camera_controller.py)（撮像ワーカープロセス。カメラから取得 → 必要ならリサイズ → 追跡用/GUI 用の2つの共有メモリプールへ書き込む）。
- **スコープ内**: `CameraController`（`multiprocessing.Process` サブクラス）の初期化・`run()` ループ・カメラ open/設定・フレーム取得・リサイズ・両プールへの書き込み・ドロップ警告・停止/後始末。
- **スコープ外**:
  - 共有メモリプールの内部実装（[`shared-frame-pool`](../shared-frame-pool/)）。本 spec は `SharedFrameAccessor.write/shape/close` を所与として扱う。
  - プールの生成・`reset_free_slots`/`mark_active`・プロセスの `start`/`stop`（オーケストレーション側＝[`gui_controller.py`](../../../src/gui_controller.py)、別 spec 予定）。
  - 設定スキーマ（[`config-manager`](../config-manager/)）、ロガー構成（[`logger`](../logger/)）。

## 用語集

| 用語 | 定義 |
|:--|:--|
| 追跡用プール / GUI 用プール | それぞれ ObjectTracking / GUI 表示向けの `SharedFramePool`。CameraController は両方へ同一フレームを書く |
| `SharedFrameSpec` | プールへアタッチするための軽量仕様（pickle 可）。子プロセスへ渡される |
| `SharedFrameAccessor` | spec から共有メモリへアタッチする writer/reader ハンドル |
| 期待 shape | プールのスロット形状 `(height, width, 3)`。書き込むフレームはこれに一致する必要がある |
| ドロップ | プール書き込みが `False` を返し、フレームが破棄されること |

## 要求一覧（EARS）

各要求は一意 ID・EARS 文・出典・対応テストを記す。ID 接頭辞は `R-CAM`。テストは [`tests/test_camera_controller.py`](../../../tests/test_camera_controller.py)（純関数系＋`run()` モックテスト `CameraRunTest`）。

| ID | 種別 | 要求（EARS） | 出典 | 対応テスト |
|:--|:--|:--|:--|:--|
| R-CAM-01 | ユビキタス | システムは `CameraController` を `multiprocessing.Process` のサブクラスとして定義し、独立プロセスで動作させること。 | `src/camera_controller.py:19` | `tests/test_camera_controller.py::InitStateTest::test_subclasses_multiprocessing_process` |
| R-CAM-02 | イベント駆動 | 生成されたとき、システムは camera 設定・logging 設定・追跡用/GUI 用 spec・`stop_event`・`error_queue` を保持し、`frame_id` を 0 に初期化すること。 | `src/camera_controller.py:20-37` | `tests/test_camera_controller.py::InitStateTest::test_init_keeps_collaborators_and_zeroes_frame_id` |
| R-CAM-03 | イベント駆動 | `run()` 開始時、システムは**子プロセス内で**ロガーを構成し、2つの `SharedFrameAccessor` をアタッチすること。 | `src/camera_controller.py:79-84` | `tests/test_camera_controller.py::CameraRunTest::test_run_configures_logger_and_attaches_both_pools` |
| R-CAM-04 | 異常系 | カメラを開けないとき、システムは error をログし、両プールを `close` して `run()` を終了すること。 | `src/camera_controller.py:88-93` | `tests/test_camera_controller.py::CameraRunTest::test_open_failure_reports_error_closes_pools_and_returns` |
| R-CAM-05 | ユビキタス | システムはカメラへ解像度（width/height）と FPS を設定値で**要求**すること（カメラが従う保証はない）。 | `src/camera_controller.py:95-97` | `tests/test_camera_controller.py::CameraRunTest::test_requests_resolution_and_fps_from_config` |
| R-CAM-06 | 状態駆動 | `stop_event` がセットされていない間、システムはフレーム取得→書き込みのループを繰り返すこと。 | `src/camera_controller.py:100` | `tests/test_camera_controller.py::CameraRunTest::test_stop_event_exits_loop_and_releases_resources` |
| R-CAM-07 | 異常系 | フレーム取得に失敗（`ret` が False）したとき、システムは warning をログし 0.1 秒スリープして次の反復へ継続すること（**リトライ上限なし＝正式仕様**）。 | `src/camera_controller.py:102-105` | `tests/test_camera_controller.py::CameraRunTest::test_grab_failure_warns_and_continues` |
| R-CAM-08 | イベント駆動 | 取得フレームの shape が期待 shape と異なるとき、システムは期待 shape（幅・高さ）へ `cv2.resize` すること（`_fit_to_pool` 内）。 | `src/camera_controller.py:63-76,113` | `tests/test_camera_controller.py::FitToPoolTest::test_resizes_when_height_width_differ`, `::test_returns_frame_when_shape_already_matches` |
| R-CAM-09 | イベント駆動 | フレーム取得後、システムは同一フレームに撮像 `timestamp` を付与し、追跡用・GUI 用の両プールへ書き込むこと。 | `src/camera_controller.py:122-125` | `tests/test_camera_controller.py::CameraRunTest::test_frames_written_to_both_pools_with_incrementing_frame_id` |
| R-CAM-10 | 異常系 | いずれかのプール書き込みが False（ドロップ）を返したとき、システムは該当プール名と `frame_id` を warning にログすること。 | `src/camera_controller.py:127-136` | `tests/test_camera_controller.py::CameraRunTest::test_write_failure_warns_per_pool_but_frame_id_advances` |
| R-CAM-11 | ユビキタス | システムは各反復で `frame_id` を単調増加（+1）させること（ドロップ時は加算しない）。 | `src/camera_controller.py:139` | `tests/test_camera_controller.py::CameraRunTest::test_frames_written_to_both_pools_with_incrementing_frame_id`、`::test_channel_mismatch_frame_dropped_without_frame_id_increment` |
| R-CAM-12 | イベント駆動 | ループ終了時（`finally`）、システムはカメラを `release` し、両プールを `close` し、停止 info をログすること。 | `src/camera_controller.py:141-145` | `tests/test_camera_controller.py::CameraRunTest::test_stop_event_exits_loop_and_releases_resources` |
| R-CAM-13 | ユビキタス | システムはカメラソースを設定値 `camera.source` から `_resolve_camera_source` で決定し `cv2.VideoCapture` に渡すこと（**実装済み**）。型解釈は R-CAM-13a〜d（ルール B）に従う。 | `src/camera_controller.py:51-61,86-87` | `tests/test_camera_controller.py::ResolveCameraSourceTest` |
| R-CAM-13a | イベント駆動 | `camera.source` が整数のとき、システムはデバイスインデックスとしてそのまま `VideoCapture(int)` に渡すこと。 | `src/camera_controller.py:59-61` | `tests/test_camera_controller.py::ResolveCameraSourceTest::test_int_passes_through_as_device_index` |
| R-CAM-13b | イベント駆動 | `camera.source` が数字のみの文字列（`[0-9]+`）のとき、システムは int へ変換しデバイスインデックスとして扱うこと。 | `src/camera_controller.py:59-60` | `tests/test_camera_controller.py::ResolveCameraSourceTest::test_digit_string_becomes_int_device_index` |
| R-CAM-13c | イベント駆動 | `camera.source` がそれ以外の文字列のとき、システムはパス/URL としてそのまま `VideoCapture(str)` に渡すこと。 | `src/camera_controller.py:61` | `tests/test_camera_controller.py::ResolveCameraSourceTest::test_non_digit_string_passes_through_as_path_or_url` |
| R-CAM-13d | ユビキタス | `camera.source` が未指定のとき、システムは既定値 `0`（デバイス0）を用いること（後方互換）。 | `src/config_manager.py:14-15`（CameraConfig.source 既定） | `tests/test_camera_controller.py::ResolveCameraSourceTest::test_default_source_is_device_zero` |
| R-CAM-14 | 異常系 | カメラを開けないとき、システムは error をログし、`error_queue` へ `WorkerError(source="camera", message, timestamp)` を送ってから両プールを `close` して `run()` を終了すること（**実装済み**）。 | `src/camera_controller.py:39-49,88-93` | `tests/test_camera_controller.py::CameraRunTest::test_open_failure_reports_error_closes_pools_and_returns` |
| R-CAM-15 | 異常系 | `cv2.resize` 後もフレームの shape（特にチャンネル数）が期待 shape と一致しないとき、システムは error をログし当該フレームをドロップ（書き込みスキップ＝`continue`、`frame_id` を加算しない）して継続すること（**実装済み**。`_fit_to_pool` が `None` を返した場合）。 | `src/camera_controller.py:63-76,113-120` | `tests/test_camera_controller.py::FitToPoolTest::test_returns_none_for_grayscale_frame`, `::test_returns_none_for_four_channel_frame`, `::CameraRunTest::test_channel_mismatch_frame_dropped_without_frame_id_increment` |

## 前提条件 / 不変条件

- **アタッチは子プロセス内**: `SharedFrameAccessor` の生成は `run()`（子プロセス）で行う。コンストラクタには pickle 可能な `SharedFrameSpec` のみ渡る。出典 `src/camera_controller.py:31-33,83-84`。
- **両プールは同一 shape**: GUI 側が両プールを同一 `frame_shape=(height, width, 3)` で生成するため、リサイズ基準を `tracking_pool.shape` 一本にしても GUI 用プールにも適合する。出典 `src/gui_controller.py:68,84-95`、`src/camera_controller.py:112`。
- **同一フレームを2プールへ**: 1枚のフレームを別スロットへ2回書き込む（追跡用・GUI 用）。出典 `src/camera_controller.py:124-125`。
- **`frame_id` の単調性とリセット**: プロセス生存中は 0 から単調増加。停止・再開で新インスタンスが作られ `frame_id` は 0 に戻る。GUI 側はこの ID でカメラ画像と追跡結果を突合する。出典 `src/camera_controller.py:36,139`。
- **FPS ペーシングは `cap.read()` 依存**: 追加のスリープは行わず、`cap.read()` のブロッキングでカメラ FPS に合わせる。出典 `src/camera_controller.py:140`。
- **停止の協調**: `stop_event`（`multiprocessing.Event`）を毎反復監視し、セットで脱出。owner（GUI）がセットする。出典 `src/camera_controller.py:100`。
- **エラー通知は送出のみ**: `_report_error` は `error_queue` へ `WorkerError` を put して return するだけで、停止判断は GUI が行う（[`gui-controller`](../gui-controller/) R-GUI-44）。`error_queue` が None でも安全（no-op）。出典 `src/camera_controller.py:39-49`。
- **カメラソース解釈（ルール B）**: `_resolve_camera_source` は int をそのまま、数字のみ文字列を int 化、それ以外の文字列をパス/URL として返す。`"0"` でもデバイス0になり YAML が int/str いずれでも頑健。出典 `src/camera_controller.py:51-61`、[`config-manager`](../config-manager/)。

## 確定事項（レビュー反映済み）

- ✅ **カメラソースを `camera.source` で設定キー化（実装済み）**: `cv2.VideoCapture(0)` 固定をやめ、`_resolve_camera_source(self.config.source)` でソースを決める（`camera_controller.py:51-61,86-87`）。型解釈は **ルール B**（数字文字列は int 化）で確定（R-CAM-13a〜d）:
  - int → デバイスインデックス
  - 数字のみの文字列（`[0-9]+`）→ int 化してデバイスインデックス（`source: 0` でも `"0"` でもデバイス0）
  - それ以外の文字列 → パス/URL（動画ファイル、RTSP 等）としてそのまま渡す
  - 既定値 `0`（後方互換、`config_manager.py:14-15`）。相対パスは OpenCV 既定（作業ディレクトリ基準）。
  - 補足: GStreamer パイプライン文字列は第2引数 `cv2.CAP_GSTREAMER` が要るため今回は対象外（将来 `camera.api_preference` を検討）。
- ✅ **オープン失敗時は GUI へ通知（実装済み）**: error ログに加え、`error_queue` へ `data_models.WorkerError(source="camera", ...)` を送ってから両プールを `close`→`return`（`camera_controller.py:39-49,90`）。GUI 側は [`gui-controller`](../gui-controller/) R-GUI-44 でこれを受けて状態「エラー」を表示する。通知機構は**ステータス Queue に確定**（tracking R-OTC-23 と共通）。新設要求 **R-CAM-14**。
- ✅ **grab 連続失敗は無限リトライのまま（仕様）**: `ret=False` の間、`stop_event` まで 0.1 秒間隔で再試行する現状挙動を正式仕様とする（上限/バックオフは入れない）。R-CAM-07 を正式仕様として確定。
- ✅ **チャンネル数不一致はエラー扱いでドロップ（実装済み）**: `cv2.resize` は高さ・幅のみ補正するため、チャンネル数が期待と異なるフレームは shape 不一致のまま。これを `_fit_to_pool` で検出し（`None` を返す）、呼び出し側で **error ログ＋当該フレームをドロップ（`continue`、`frame_id` を加算しない）して継続**する（R-CAM-15、`camera_controller.py:63-76,113-120`）。
- ✅ **コメント修正（実装済み）**: 旧「Resize/pad」コメントを実装（resize のみ＋チャンネル不一致ドロップ）に合わせて書き換え済み（`camera_controller.py:107-111`）。

## 未確定 / 要レビュー事項

- （解消済み）GUI 通知機構の選択 → [`gui-controller`](../gui-controller/) R-GUI-44 で方針確定（専用エラー通知＋GUI 表示、**ステータス Queue 推奨**、camera/tracking 共通）。最終的な実装形（Event か Queue か）は実装時に 3 モジュール横断で確定する。
