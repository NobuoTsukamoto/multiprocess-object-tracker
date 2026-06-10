# Tasks — object-tracking-controller

> 逆生成 spec。`src/object_tracking_controller.py` のテストカバレッジ状況と、未文書化挙動・テスト不足・将来改善を列挙する。

## テストカバレッジ状況（逆生成時）

専用テストは**存在しない**（`tests/test_object_tracking_controller.py` 無し）。全要求が未カバー。ONNX/ByteTrack 依存のため、`onnxruntime.InferenceSession` と `sv.ByteTrack` のモック化、または小型ダミーモデルが要る。

| 要求 ID | 対応テスト | 状態 |
|:--|:--|:--|
| R-OTC-01〜04（init/ロード） | — | ⬜ 未カバー |
| R-OTC-05（ONNX 失敗→通知→終了） | — | ⬜ 未カバー（実装済み） |
| R-OTC-06（ByteTrack 初期化） | — | ⬜ 未カバー |
| R-OTC-07（アタッチ） | — | ⬜ 未カバー |
| R-OTC-08（stop までループ） | — | ⬜ 未カバー |
| R-OTC-09（ポリシー別読み出し） | — | ⬜ 未カバー |
| R-OTC-10（未知ポリシー→fallback） | — | ⬜ 未カバー |
| R-OTC-11（Empty→continue） | — | ⬜ 未カバー |
| R-OTC-12（取得後 stop→break） | — | ⬜ 未カバー |
| R-OTC-13（input_lag/delta/skipped） | — | ⬜ 未カバー |
| R-OTC-14（前処理/後処理） | — | ⬜ 未カバー |
| R-OTC-15（xyxy/スコア） | — | ⬜ 未カバー |
| R-OTC-16（段階フィルタ） | — | ⬜ 未カバー |
| R-OTC-17（ByteTrack 更新） | — | ⬜ 未カバー |
| R-OTC-18（TrackInfo 構築） | — | ⬜ 未カバー |
| R-OTC-19（TrackingResult 構築） | — | ⬜ 未カバー |
| R-OTC-20（queue Full→drop-oldest） | — | ⬜ 未カバー |
| R-OTC-21（PERFORMANCE ログ） | — | ⬜ 未カバー |
| R-OTC-22（finally 後始末） | — | ⬜ 未カバー |
| R-OTC-23（ONNX 失敗→GUI 通知） | — | ⬜ 未カバー（実装済み） |

## タスク

### 文書化 / 整合
- [x] `score_threshold` が ByteTrack 活性化閾値（生検出フィルタではない）である点を README 設定表に注記済み（config-manager spec と共通）。
- [x] 読み出しポリシー（`fifo`/`latest`/`bounded_latest`）と `max_frame_skip` の挙動（不正値フォールバック含む）を README 設定表に明記。
- [ ] YOLOX 前提（`p6=False`、strides `[8,16,32]`）を README/設計に明記。

### テスト
- [ ] `tests/test_object_tracking_controller.py` を新設（`_preprocess`/`_postprocess`/`_read_frame` は純関数的に単体テスト可能）。
  - [ ] `_read_frame` が各ポリシーで適切な呼び出しと3-tuple を返すこと（R-OTC-09）。
  - [ ] 未知ポリシーで warning＋bounded_latest フォールバック（R-OTC-10）。
  - [ ] `_preprocess` の出力形状/dtype/ratio（R-OTC-14）。
  - [ ] 段階フィルタ（confidence/NMS/class/area）の境界（R-OTC-16）。
  - [ ] `track_queue` Full 時の drop-oldest（R-OTC-20）。
  - [ ] ONNX ロード失敗で早期 return（R-OTC-05、`InferenceSession` モック）。

### 実装（✅完了）
- [x] **ONNX ロード失敗の GUI 通知**（R-OTC-23）: error ログに加え `error_queue` へ `data_models.WorkerError(source="tracking", ...)` を送って `return`（`_report_error`、`object_tracking_controller.py:46-56,135`）。コンストラクタに `error_queue` 引数を追加。GUI 側は [`gui-controller`](../gui-controller/) R-GUI-44 で受信・表示。通知機構は camera-controller R-CAM-14 と共通（**ステータス Queue に確定**）。
- [ ] **`_report_error` のテスト**（R-OTC-05/23）: `error_queue` スタブで ONNX ロード失敗時に `WorkerError` が put され早期 return することを検証。
- [x] **検出閾値の設定化**（**実装済み**）: 生検出 confidence フィルタ→`self.det_config.detection_threshold`（`:205`）、NMS→`self.det_config.nms_iou_threshold`（`:208`）に差し替え。`config_manager`/`default.yaml`/README も同期。既定は従来同値（0.1 / 0.45）で挙動不変。

### 実装 / 改善（将来）
- [ ] **他モデル対応**（将来）: YOLOX 固定（`p6=False`、strides `[8,16,32]`、`scores=obj×cls`）を脱し、他検出モデル/他ストライド構成に対応。今回は対象外（当面 YOLOX 固定で確定）。
- [ ] `input_name = session.get_inputs()[0].name` をループ外へ巻き上げ（`:176`、軽微な最適化）。
- [ ] 例外耐性: 推論中の例外（不正フレーム等）を握って継続するか、致命扱いにするかの方針明文化。
- [ ] 型注釈の補強（`_read_frame`/`_preprocess`/`_postprocess` の戻り値型）。

## メモ / 申し送り

- ✅ ONNX ロード失敗は **GUI へ専用エラー通知**（R-OTC-23、**実装済み**。`error_queue` + `WorkerError`、camera R-CAM-14 / gui R-GUI-44 と同一機構・ステータス Queue に確定）。
- ✅ 当面 **YOLOX 固定**で進める（他モデル対応は将来）。
- ✅ 検出閾値を設定キー化（**実装済み**）: `0.1`→`detection.detection_threshold`、`0.45`→`detection.nms_iou_threshold`。消費側を `self.det_config.*` へ差し替え（既定同値で挙動不変）。
- 🔎 `_read_frame` は `read`(2-tuple)/`read_latest`(3-tuple) を `(frame_ref, image, skipped)` に正規化（`fifo` は skip=0）。
- 🔎 検出フィルタ順は confidence→NMS→class→area。NMS はクラス選別前に全体へ適用。
- 🔎 空検出/`tracker_id` None でも `TrackingResult` は送出（`track_infos` 空）。
- 🔎 レイテンシ恒等式 `total == queue + process`（data-models spec と共通）。
- 専用テスト皆無。純関数寄りの `_preprocess`/`_postprocess`/`_read_frame` から着手するのが費用対効果が高い。
