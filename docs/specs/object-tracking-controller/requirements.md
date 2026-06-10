# Requirements — object-tracking-controller

> 逆生成 spec。出典は [`src/object_tracking_controller.py`](../../../src/object_tracking_controller.py)。コードが正。
> 記法は [`../../steering/conventions.md`](../../steering/conventions.md) の EARS 節に従う。
> **各要求に出典 `file:line` を付与済み。人手レビューで突き合わせること。**

## 対象 / スコープ

- **対象モジュール/機能**: [`src/object_tracking_controller.py`](../../../src/object_tracking_controller.py)（推論+追跡ワーカープロセス。追跡用プールからフレームを読み、ONNX 推論 + NMS + フィルタ → `supervision.ByteTrack` → `TrackingResult` を Queue で GUI へ送る）。
- **スコープ内**: `ObjectTrackingController`（`multiprocessing.Process`）の初期化・`run()`・読み出しポリシー（`_read_frame`）・前処理/後処理（YOLOX）・検出フィルタ・追跡更新・`TrackingResult` 生成と送出・PERFORMANCE ログ・停止/後始末。
- **スコープ外**:
  - 共有メモリプールの内部実装（[`shared-frame-pool`](../shared-frame-pool/)）。`read`/`read_latest`/`close` は所与。
  - `TrackingResult`/`TrackInfo`/`FrameRef` の定義（[`data-models`](../data-models/)）。
  - 設定スキーマ（[`config-manager`](../config-manager/)）、ロガー（[`logger`](../logger/)）、プロセス起動/停止（gui-controller、別 spec 予定）。

## 用語集

| 用語 | 定義 |
|:--|:--|
| 読み出しポリシー | `fifo`（全フレーム）/ `latest`（最新追従）/ `bounded_latest`（最大 `max_frame_skip` まで読み飛ばし） |
| YOLOX デコード | `_postprocess` の grid/stride 復元（strides `[8,16,32]`、`p6=False`） |
| `sv.Detections` | supervision の検出コンテナ（xyxy/confidence/class_id/tracker_id） |
| ByteTrack | supervision の追跡器。`tracker_id` を付与する |
| `skipped_count` | `read_latest` が読み飛ばした古いフレーム数 |

## 要求一覧（EARS）

各要求は一意 ID・EARS 文・出典・対応テストを記す。ID 接頭辞は `R-OTC`。専用テストは**存在しない**（`tests/test_object_tracking_controller.py` 無し）。

| ID | 種別 | 要求（EARS） | 出典 | 対応テスト |
|:--|:--|:--|:--|:--|
| R-OTC-01 | ユビキタス | システムは `ObjectTrackingController` を `multiprocessing.Process` のサブクラスとして定義すること。 | `src/object_tracking_controller.py:25` | — |
| R-OTC-02 | イベント駆動 | 生成されたとき、システムは detection/tracking/camera 設定・logging・`frame_pool_spec`・`track_queue`・`stop_event`・`error_queue` を保持すること。 | `src/object_tracking_controller.py:26-44` | — |
| R-OTC-03 | イベント駆動 | `run()` 開始時、システムは**子プロセス内で**ロガーを構成すること。 | `src/object_tracking_controller.py:151-152` | — |
| R-OTC-04 | イベント駆動 | `run()` 開始時、システムは `model_path`/`providers` で ONNX セッションをロードし、入力 shape を取得すること。 | `src/object_tracking_controller.py:154-158` | — |
| R-OTC-05 | 異常系 | ONNX ロードに失敗したとき、システムは error をログし `error_queue` へ `WorkerError` を送って `run()` を終了すること（R-OTC-23）。 | `src/object_tracking_controller.py:159-162` | `tests/test_object_tracking_controller.py::OnnxLoadFailureTest` |
| R-OTC-06 | イベント駆動 | システムは `ByteTrack` を `track_activation_threshold=score_threshold` / `lost_track_buffer=max_lost` / `minimum_matching_threshold=iou_threshold` / `frame_rate=camera.fps` で初期化すること。 | `src/object_tracking_controller.py:164-169` | — |
| R-OTC-07 | イベント駆動 | システムは子プロセス内で `frame_pool` にアタッチすること。 | `src/object_tracking_controller.py:171` | — |
| R-OTC-08 | 状態駆動 | `stop_event` がセットされていない間、システムは読み出し→推論→送出のループを繰り返すこと。 | `src/object_tracking_controller.py:180` | — |
| R-OTC-09 | イベント駆動 | システムは `frame_read_policy` に従いフレームを読むこと（`fifo`=`read`、`latest`/`bounded_latest`=`read_latest`、タイムアウト `FRAME_READ_TIMEOUT_SEC=0.1`）。 | `src/object_tracking_controller.py:22,58-80,183` | `tests/test_object_tracking_controller.py::ReadFrameTest` |
| R-OTC-10 | 異常系 | `frame_read_policy` が未知の値のとき、システムは warning をログし `bounded_latest` にフォールバックすること。 | `src/object_tracking_controller.py:75-80` | `tests/test_object_tracking_controller.py::ReadFrameTest::test_unknown_policy_warns_and_falls_back_to_bounded_latest` |
| R-OTC-11 | 異常系 | フレーム読み出しが `Empty`（タイムアウト）のとき、システムは次の反復へ continue すること。 | `src/object_tracking_controller.py:184-185` | — |
| R-OTC-12 | イベント駆動 | フレーム取得後に `stop_event` がセットされていたとき、システムはループを break すること。 | `src/object_tracking_controller.py:186-187` | — |
| R-OTC-13 | ユビキタス | システムは入力遅延（`input_lag`）・`frame_id_delta`・`skipped_count` を計測・保持すること。 | `src/object_tracking_controller.py:189-196` | — |
| R-OTC-14 | イベント駆動 | システムはフレームを前処理（letterbox、pad 値 114、CHW 転置、float32）→ ONNX 推論 → YOLOX 後処理（strides `[8,16,32]`）すること。 | `src/object_tracking_controller.py:82-122,198-211` | `tests/test_object_tracking_controller.py::PreprocessTest`、`::PostprocessTest`（推論部は未カバー） |
| R-OTC-15 | イベント駆動 | システムは推論出力から box を xywh→xyxy 変換して `ratio` で逆スケールし、`class_id=argmax(obj×cls)`・`confidence=max(obj×cls)` で `sv.Detections` を構築すること。 | `src/object_tracking_controller.py:213-229` | — |
| R-OTC-16 | イベント駆動 | システムは検出を confidence>`detection.detection_threshold` → NMS(IoU=`detection.nms_iou_threshold`) → `class_id ∈ tracking.class_id` → `area ≥ min_box_area` の順でフィルタすること。 | `src/object_tracking_controller.py:124-132,230`（`_filter_detections` + 呼び出し） | `tests/test_object_tracking_controller.py::FilterDetectionsTest` |
| R-OTC-17 | イベント駆動 | システムは ByteTrack でフィルタ後の検出を追跡更新すること。 | `src/object_tracking_controller.py:232` | — |
| R-OTC-18 | イベント駆動 | `tracker_id` が付与されているとき、システムは各追跡について `TrackInfo`（track_id/class_id を `int()` キャスト）を構築すること（box/score は削除済み）。 | `src/object_tracking_controller.py:234-241` | — |
| R-OTC-19 | イベント駆動 | システムは `TrackingResult`（frame_id/timestamp/track_infos/detections/process_time_ms/queue_latency_ms/total_latency_ms）を構築すること。 | `src/object_tracking_controller.py:247-255` | — |
| R-OTC-20 | 異常系 | `track_queue` への `put_nowait` が `Full` のとき、システムは最古の結果を捨てて再 put し、なお `Full` なら warning をログ（ドロップ）すること。 | `src/object_tracking_controller.py:134-148,257`（`_publish_result` + 呼び出し） | `tests/test_object_tracking_controller.py::PublishResultTest` |
| R-OTC-21 | イベント駆動 | `performance_interval` フレームごとに、システムは PERFORMANCE レベルで frame/process_time/avg_fps/frame_id_delta/skipped/input_lag をログすること。 | `src/object_tracking_controller.py:259-276` | — |
| R-OTC-22 | イベント駆動 | ループ終了時（`finally`）、システムは `frame_pool` を `close` し停止 info をログすること。 | `src/object_tracking_controller.py:277-279` | — |
| R-OTC-23 | 異常系 | ONNX ロードに失敗したとき、システムは GUI へロード失敗を `WorkerError(source="tracking", ...)` として `error_queue` に**専用エラー通知**すること（**実装済み**）。GUI 側は状態「エラー」を表示する（[`gui-controller`](../gui-controller/) R-GUI-44）。通知機構は camera-controller R-CAM-14 と共通（**ステータス Queue に確定**）。 | `src/object_tracking_controller.py:46-56,160-162` | `tests/test_object_tracking_controller.py::OnnxLoadFailureTest`、`::ReportErrorTest` |

## 前提条件 / 不変条件

- **子プロセス内アタッチ/構成**: Logger・`SharedFrameAccessor`・ONNX セッション・ByteTrack は `run()`（子プロセス）で生成する。コンストラクタには pickle 可能な spec/queue/event のみ渡る。出典 `src/object_tracking_controller.py:151,154,164,171`。
- **`_read_frame` の戻り正規化**: `read`（2-tuple）も `read_latest`（3-tuple）も、`_read_frame` が `(frame_ref, image, skipped_count)` の3要素へ統一する（`fifo` は skip=0）。出典 `src/object_tracking_controller.py:62-80`。
- **`frame_id` 突合**: `TrackingResult.frame_id == FrameRef.frame_id`。GUI がこの ID でカメラ画像と結合する。出典 `src/object_tracking_controller.py:248`、[`data-models`](../data-models/)。
- **`score_threshold` の意味**: 生検出フィルタ（`detection.detection_threshold`）ではなく ByteTrack の `track_activation_threshold`。出典 `src/object_tracking_controller.py:165,127`、[`config-manager`](../config-manager/)。
- **YOLOX 前提**: 後処理は YOLOX 出力（strides `[8,16,32]`、`p6=False`、`scores=obj×cls`）に固定。出典 `src/object_tracking_controller.py:102-122,214`。
- **レイテンシ恒等式**: `total_latency_ms == queue_latency_ms + process_time_ms`（同一時刻基準）。出典 `src/object_tracking_controller.py:189-191,243-245`、[`data-models`](../data-models/)。
- **エラー通知は送出のみ**: `_report_error` は `error_queue` へ `WorkerError(source="tracking", ...)` を put して return するだけ。全停止判断は GUI（R-GUI-44）。`error_queue` が None でも安全。出典 `src/object_tracking_controller.py:46-56`。

## 確定事項（レビュー反映済み）

- ✅ **ONNX ロード失敗は GUI へ通知（エラー扱い・実装済み、R-OTC-23）**: error ログに加え `error_queue` へ `data_models.WorkerError(source="tracking", ...)` を送って `return`（`object_tracking_controller.py:46-56,160-162`）。camera-controller の R-CAM-14（open 失敗通知）と**同一の専用通知**で、GUI は状態「エラー」を表示する（[`gui-controller`](../gui-controller/) R-GUI-44）。通知機構は**ステータス Queue に確定**。
- ✅ **当面 YOLOX 固定で進める**: `p6=False`・strides `[8,16,32]`・`scores=obj×cls` の YOLOX 前提を当面の正式スコープとする。他モデル対応は将来の拡張テーマとして tasks に残す（今回は実装しない）。
- ✅ **検出フィルタ閾値の設定化（実装済み）**: confidence フィルタ（`:205`）・NMS IoU（`:208`）を `detection.detection_threshold`（既定 0.1）/ `detection.nms_iou_threshold`（既定 0.45）へキー化し、消費側を `self.det_config.*` へ差し替え済み（[`config-manager`](../config-manager/)）。

## 未確定 / 要レビュー事項

- （解消済み）GUI 通知機構の選択 → [`gui-controller`](../gui-controller/) R-GUI-44 で方針確定（専用エラー通知＋GUI 表示、**ステータス Queue 推奨**、camera/tracking 共通）。最終的な実装形（Event か Queue か）は実装時に 3 モジュール横断で確定する。
- [ ] **`input_name` をループ内で毎回取得**: `session.get_inputs()[0].name` を反復ごとに呼ぶ（`:202`）。ループ外へ巻き上げ可能（軽微な最適化、tasks 将来改善）。
- [ ] **空検出/`tracker_id` None の意図確認**: フィルタ後に検出ゼロ、または `tracker_id is None` のとき `track_infos` は空のまま `TrackingResult` を送出する。意図どおりか確認。出典 `src/object_tracking_controller.py:234-241`。
