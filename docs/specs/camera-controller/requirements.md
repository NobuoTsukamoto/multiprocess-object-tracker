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

各要求は一意 ID・EARS 文・出典・対応テストを記す。ID 接頭辞は `R-CAM`。専用テストは**存在しない**（`tests/test_camera_controller.py` 無し）。

| ID | 種別 | 要求（EARS） | 出典 | 対応テスト |
|:--|:--|:--|:--|:--|
| R-CAM-01 | ユビキタス | システムは `CameraController` を `multiprocessing.Process` のサブクラスとして定義し、独立プロセスで動作させること。 | `src/camera_controller.py:18` | — |
| R-CAM-02 | イベント駆動 | 生成されたとき、システムは camera 設定・logging 設定・追跡用/GUI 用 spec・`stop_event`・`error_queue` を保持し、`frame_id` を 0 に初期化すること。 | `src/camera_controller.py:19-36` | — |
| R-CAM-03 | イベント駆動 | `run()` 開始時、システムは**子プロセス内で**ロガーを構成し、2つの `SharedFrameAccessor` をアタッチすること。 | `src/camera_controller.py:50-56` | — |
| R-CAM-04 | 異常系 | カメラを開けないとき、システムは error をログし、両プールを `close` して `run()` を終了すること。 | `src/camera_controller.py:58-64` | — |
| R-CAM-05 | ユビキタス | システムはカメラへ解像度（width/height）と FPS を設定値で**要求**すること（カメラが従う保証はない）。 | `src/camera_controller.py:66-68` | — |
| R-CAM-06 | 状態駆動 | `stop_event` がセットされていない間、システムはフレーム取得→書き込みのループを繰り返すこと。 | `src/camera_controller.py:71` | — |
| R-CAM-07 | 異常系 | フレーム取得に失敗（`ret` が False）したとき、システムは warning をログし 0.1 秒スリープして次の反復へ継続すること（**リトライ上限なし＝正式仕様**）。 | `src/camera_controller.py:73-76` | — |
| R-CAM-08 | イベント駆動 | 取得フレームの shape が期待 shape と異なるとき、システムは期待 shape（幅・高さ）へ `cv2.resize` すること。 | `src/camera_controller.py:81-85` | — |
| R-CAM-09 | イベント駆動 | フレーム取得後、システムは同一フレームに撮像 `timestamp` を付与し、追跡用・GUI 用の両プールへ書き込むこと。 | `src/camera_controller.py:87-90` | — |
| R-CAM-10 | 異常系 | いずれかのプール書き込みが False（ドロップ）を返したとき、システムは該当プール名と `frame_id` を warning にログすること。 | `src/camera_controller.py:92-101` | — |
| R-CAM-11 | ユビキタス | システムは各反復で `frame_id` を単調増加（+1）させること。 | `src/camera_controller.py:104` | — |
| R-CAM-12 | イベント駆動 | ループ終了時（`finally`）、システムはカメラを `release` し、両プールを `close` し、停止 info をログすること。 | `src/camera_controller.py:106-110` | — |
| R-CAM-13 | ユビキタス | システムはカメラソースを設定値 `camera.source` から決定し `cv2.VideoCapture` に渡すこと（**改修予定**。現状は `0` 固定）。型解釈は R-CAM-13a〜d に従う。 | `src/camera_controller.py:58` | — |
| R-CAM-13a | イベント駆動 | `camera.source` が整数のとき、システムはデバイスインデックスとして `VideoCapture(int)` に渡すこと。 | `src/camera_controller.py:58`（改修予定） | — |
| R-CAM-13b | イベント駆動 | `camera.source` が数字のみの文字列（`^\d+$`）のとき、システムは int へ変換しデバイスインデックスとして扱うこと。 | `src/camera_controller.py:58`（改修予定） | — |
| R-CAM-13c | イベント駆動 | `camera.source` がそれ以外の文字列のとき、システムはパス/URL としてそのまま `VideoCapture(str)` に渡すこと。 | `src/camera_controller.py:58`（改修予定） | — |
| R-CAM-13d | ユビキタス | `camera.source` が未指定のとき、システムは既定値 `0`（デバイス0）を用いること（後方互換）。 | `src/config_manager.py:12-17`（CameraConfig 既定、改修予定） | — |
| R-CAM-14 | 異常系 | カメラを開けないとき、システムは error をログし、`error_queue` へ `WorkerError(source="camera", message, timestamp)` を送ってから両プールを `close` して `run()` を終了すること（**実装済み**）。 | `src/camera_controller.py:38-48,58-64` | — |
| R-CAM-15 | 異常系 | リサイズ後もフレームの shape（特にチャンネル数）が期待 shape と一致しないとき、システムは error をログし当該フレームをドロップして継続すること（**改修予定**。現状は `write` の False による warning のみ）。 | `src/camera_controller.py:81-90`、`src/shared_frame_pool.py:175-177` | — |

## 前提条件 / 不変条件

- **アタッチは子プロセス内**: `SharedFrameAccessor` の生成は `run()`（子プロセス）で行う。コンストラクタには pickle 可能な `SharedFrameSpec` のみ渡る。出典 `src/camera_controller.py:31-32,55-56`。
- **両プールは同一 shape**: GUI 側が両プールを同一 `frame_shape=(height, width, 3)` で生成するため、リサイズ基準を `tracking_pool.shape` 一本にしても GUI 用プールにも適合する。出典 `src/gui_controller.py:67,80-91`、`src/camera_controller.py:81`。
- **同一フレームを2プールへ**: 1枚のフレームを別スロットへ2回書き込む（追跡用・GUI 用）。出典 `src/camera_controller.py:89-90`。
- **`frame_id` の単調性とリセット**: プロセス生存中は 0 から単調増加。停止・再開で新インスタンスが作られ `frame_id` は 0 に戻る。GUI 側はこの ID でカメラ画像と追跡結果を突合する。出典 `src/camera_controller.py:35,104`。
- **FPS ペーシングは `cap.read()` 依存**: 追加のスリープは行わず、`cap.read()` のブロッキングでカメラ FPS に合わせる。出典 `src/camera_controller.py:105`。
- **停止の協調**: `stop_event`（`multiprocessing.Event`）を毎反復監視し、セットで脱出。owner（GUI）がセットする。出典 `src/camera_controller.py:71`。
- **エラー通知は送出のみ**: `_report_error` は `error_queue` へ `WorkerError` を put して return するだけで、停止判断は GUI が行う（[`gui-controller`](../gui-controller/) R-GUI-44）。`error_queue` が None でも安全（no-op）。出典 `src/camera_controller.py:38-48`。

## 確定事項（レビュー反映済み）

- ✅ **カメラソースを `camera.source` で設定キー化（キー名確定）**: `cv2.VideoCapture(0)` 固定（`camera_controller.py:43`）をやめ、設定値 `camera.source` からソースを決める。型解釈は **ルール B**（数字文字列は int 化）で確定（R-CAM-13a〜d）:
  - int → デバイスインデックス
  - 数字のみの文字列（`^\d+$`）→ int 化してデバイスインデックス（`source: 0` でも `"0"` でもデバイス0）
  - それ以外の文字列 → パス/URL（動画ファイル、RTSP 等）としてそのまま渡す
  - 既定値 `0`（後方互換）。相対パスは OpenCV 既定（作業ディレクトリ基準）。
  - 補足: GStreamer パイプライン文字列は第2引数 `cv2.CAP_GSTREAMER` が要るため今回は対象外（将来 `camera.api_preference` を検討）。
- ✅ **オープン失敗時は GUI へ通知（実装済み）**: error ログに加え、`error_queue` へ `data_models.WorkerError(source="camera", ...)` を送ってから両プールを `close`→`return`（`camera_controller.py:38-48,61`）。GUI 側は [`gui-controller`](../gui-controller/) R-GUI-44 でこれを受けて状態「エラー」を表示する。通知機構は**ステータス Queue に確定**（tracking R-OTC-23 と共通）。新設要求 **R-CAM-14**。
- ✅ **grab 連続失敗は無限リトライのまま（仕様）**: `ret=False` の間、`stop_event` まで 0.1 秒間隔で再試行する現状挙動を正式仕様とする（上限/バックオフは入れない）。R-CAM-07 を正式仕様として確定。
- ✅ **チャンネル数不一致はエラー扱いでドロップ**: `cv2.resize` は高さ・幅のみ補正するため、チャンネル数が期待と異なるフレームは shape 不一致のまま。これを**明示的に検出して error ログを出し、当該フレームをドロップ（書き込みスキップ）して継続**する。新設要求 **R-CAM-15**。
- ✅ **コメント修正**: 「Resize/pad」コメント（`camera_controller.py:62`）を実装（resize のみ）に合わせて修正する（tasks 文書化）。

## 未確定 / 要レビュー事項

- （解消済み）GUI 通知機構の選択 → [`gui-controller`](../gui-controller/) R-GUI-44 で方針確定（専用エラー通知＋GUI 表示、**ステータス Queue 推奨**、camera/tracking 共通）。最終的な実装形（Event か Queue か）は実装時に 3 モジュール横断で確定する。
