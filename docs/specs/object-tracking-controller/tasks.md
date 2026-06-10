# Tasks — object-tracking-controller

> 逆生成 spec。`src/object_tracking_controller.py` のテストカバレッジ状況と、未文書化挙動・テスト不足・将来改善を列挙する。

## テストカバレッジ状況（逆生成時）

[`tests/test_object_tracking_controller.py`](../../../tests/test_object_tracking_controller.py) が純関数寄りの `_read_frame`/`_preprocess`/`_postprocess`、ONNX ロード失敗・`_report_error`、抽出済みの `_filter_detections`/`_publish_result` をカバーする。`run()` ループの結線部分は未カバー（`sv.ByteTrack` 等のモック統合テストが要る）。

| 要求 ID | 対応テスト | 状態 |
|:--|:--|:--|
| R-OTC-01〜04（init/ロード） | — | ⬜ 未カバー |
| R-OTC-05（ONNX 失敗→通知→終了） | `OnnxLoadFailureTest::test_load_failure_reports_worker_error_and_returns` | ✅ カバー済み |
| R-OTC-06（ByteTrack 初期化） | — | ⬜ 未カバー |
| R-OTC-07（アタッチ） | — | ⬜ 未カバー |
| R-OTC-08（stop までループ） | — | ⬜ 未カバー |
| R-OTC-09（ポリシー別読み出し） | `ReadFrameTest`（fifo/latest/bounded_latest/負値クランプ） | ✅ カバー済み |
| R-OTC-10（未知ポリシー→fallback） | `ReadFrameTest::test_unknown_policy_warns_and_falls_back_to_bounded_latest` | ✅ カバー済み |
| R-OTC-11（Empty→continue） | — | ⬜ 未カバー |
| R-OTC-12（取得後 stop→break） | — | ⬜ 未カバー |
| R-OTC-13（input_lag/delta/skipped） | — | ⬜ 未カバー |
| R-OTC-14（前処理/後処理） | `PreprocessTest`（形状/dtype/ratio/パディング）、`PostprocessTest`（グリッドデコード） | ✅ カバー済み |
| R-OTC-15（xyxy/スコア） | — | ⬜ 未カバー |
| R-OTC-16（段階フィルタ） | `FilterDetectionsTest`（各段の除去・境界） | ✅ カバー済み（`_filter_detections` 抽出済み） |
| R-OTC-17（ByteTrack 更新） | — | ⬜ 未カバー |
| R-OTC-18（TrackInfo 構築） | — | ⬜ 未カバー |
| R-OTC-19（TrackingResult 構築） | — | ⬜ 未カバー |
| R-OTC-20（queue Full→drop-oldest） | `PublishResultTest`（空き/Full→最古破棄/なお Full→warning） | ✅ カバー済み（`_publish_result` 抽出済み） |
| R-OTC-21（PERFORMANCE ログ） | — | ⬜ 未カバー |
| R-OTC-22（finally 後始末） | — | ⬜ 未カバー |
| R-OTC-23（ONNX 失敗→GUI 通知） | `OnnxLoadFailureTest`、`ReportErrorTest`（put/None/put 失敗） | ✅ カバー済み |

## タスク

### 文書化 / 整合
- [x] `score_threshold` が ByteTrack 活性化閾値（生検出フィルタではない）である点を README 設定表に注記済み（config-manager spec と共通）。
- [x] 読み出しポリシー（`fifo`/`latest`/`bounded_latest`）と `max_frame_skip` の挙動（不正値フォールバック含む）を README 設定表に明記。
- [ ] YOLOX 前提（`p6=False`、strides `[8,16,32]`）を README/設計に明記。

### テスト
- [x] `tests/test_object_tracking_controller.py` を新設（`_preprocess`/`_postprocess`/`_read_frame` は純関数的に単体テスト可能）。
  - [x] `_read_frame` が各ポリシーで適切な呼び出しと3-tuple を返すこと（R-OTC-09、`ReadFrameTest`）。
  - [x] 未知ポリシーで warning＋bounded_latest フォールバック（R-OTC-10）。
  - [x] `_preprocess` の出力形状/dtype/ratio（R-OTC-14、`PreprocessTest`。`_postprocess` のグリッドデコードも `PostprocessTest` で検証）。
  - [x] 段階フィルタ（confidence/NMS/class/area）の境界（R-OTC-16、`FilterDetectionsTest`）。`_filter_detections` に `sv.Detections` を直接渡して検証（confidence は排他 `>`、area は包含 `>=` の境界含む）。
  - [x] `track_queue` Full 時の drop-oldest（R-OTC-20、`PublishResultTest`）。`queue.Queue(maxsize=1)` と常時 Full スタブで検証。

### リファクタ（✅完了: テスト可能化、挙動不変）
- [x] `run()` の段階フィルタ4式を `_filter_detections(detections) -> sv.Detections` へ抽出（R-OTC-16、`object_tracking_controller.py:124-132`）。
- [x] `run()` の `track_queue` 送出（put_nowait→Full→最古破棄→再put→warning）を `_publish_result(tracking_result)` へ抽出（R-OTC-20、`:134-148`）。
- [x] 抽出後の行番号ずれを spec（requirements/design/tasks、config-manager・logger・gui-controller・data-models の参照元）へ反映。
  - [x] ONNX ロード失敗で早期 return（R-OTC-05、`InferenceSession` モック、`OnnxLoadFailureTest`）。

### 実装（✅完了）
- [x] **ONNX ロード失敗の GUI 通知**（R-OTC-23）: error ログに加え `error_queue` へ `data_models.WorkerError(source="tracking", ...)` を送って `return`（`_report_error`、`object_tracking_controller.py:46-56,161`）。コンストラクタに `error_queue` 引数を追加。GUI 側は [`gui-controller`](../gui-controller/) R-GUI-44 で受信・表示。通知機構は camera-controller R-CAM-14 と共通（**ステータス Queue に確定**）。
- [x] **`_report_error` のテスト**（R-OTC-05/23）: `error_queue` スタブで ONNX ロード失敗時に `WorkerError` が put され早期 return することを検証（`OnnxLoadFailureTest`/`ReportErrorTest`）。
- [x] **検出閾値の設定化**（**実装済み**）: 生検出 confidence フィルタ→`self.det_config.detection_threshold`（`:127`）、NMS→`self.det_config.nms_iou_threshold`（`:129`）に差し替え。`config_manager`/`default.yaml`/README も同期。既定は従来同値（0.1 / 0.45）で挙動不変。

### 実装 / 改善（将来）
- [ ] **他モデル対応**（将来）: YOLOX 固定（`p6=False`、strides `[8,16,32]`、`scores=obj×cls`）を脱し、他検出モデル/他ストライド構成に対応。今回は対象外（当面 YOLOX 固定で確定）。
- [ ] `input_name = session.get_inputs()[0].name` をループ外へ巻き上げ（`:202`、軽微な最適化）。
- [ ] 例外耐性: 推論中の例外（不正フレーム等）を握って継続するか、致命扱いにするかの方針明文化。
- [ ] 型注釈の補強（`_read_frame`/`_preprocess`/`_postprocess` の戻り値型）。

## メモ / 申し送り

- ✅ ONNX ロード失敗は **GUI へ専用エラー通知**（R-OTC-23、**実装済み**。`error_queue` + `WorkerError`、camera R-CAM-14 / gui R-GUI-44 と同一機構・ステータス Queue に確定）。
- ✅ 当面 **YOLOX 固定**で進める（他モデル対応は将来）。
- ✅ 検出閾値を設定キー化（**実装済み**）: `0.1`→`detection.detection_threshold`、`0.45`→`detection.nms_iou_threshold`。消費側を `self.det_config.*` へ差し替え（既定同値で挙動不変）。
- 🔎 `_read_frame` は `read`(2-tuple)/`read_latest`(3-tuple) を `(frame_ref, image, skipped)` に正規化（`fifo` は skip=0）。
- 🔎 検出フィルタ順は confidence→NMS→class→area（`_filter_detections` に抽出済み）。NMS はクラス選別前に全体へ適用。confidence は排他 `>`、area は包含 `>=`。
- 🔎 空検出/`tracker_id` None でも `TrackingResult` は送出（`track_infos` 空）。
- 🔎 レイテンシ恒等式 `total == queue + process`（data-models spec と共通）。
- ✅ 純関数寄りの `_preprocess`/`_postprocess`/`_read_frame`、ONNX 失敗系、段階フィルタ（`_filter_detections`）、送出（`_publish_result`）のテストを整備済み（17 テスト）。残りは `run()` ループの結線部分（R-OTC-08/11〜13/15/17〜19/21/22）で、カバーするなら ONNX セッション・ByteTrack を含むループ全体のモック統合テストが要る。
