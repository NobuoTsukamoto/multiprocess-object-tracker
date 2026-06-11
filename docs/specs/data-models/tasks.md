# Tasks — data-models

> 逆生成 spec。`src/data_models.py` のテストカバレッジ状況と、未文書化挙動・テスト不足・将来改善を列挙する。

## テストカバレッジ状況（逆生成時）

[`tests/test_data_models.py`](../../../tests/test_data_models.py) が dataclass 集約（R-DM-01）をカバーする。`FrameRef` は `test_shared_frame_pool.py` でも間接的に生成される（構築のみ、フィールド検証はなし）。

| 要求 ID | 対応テスト | 状態 |
|:--|:--|:--|
| R-DM-01 | `DataclassAggregationTest`（全4型が dataclass / モジュール内 dataclass が4型に一致） | ✅ カバー済み |
| R-DM-02 (`FrameData`) | （再導入は `DataclassAggregationTest::test_data_models_defines_exactly_the_ipc_structures` が検出） | 🗑️ 削除済み |
| R-DM-03 (`FrameRef`) | `FrameRefContractTest`（フィールド契約・全フィールド必須）、`tests/test_shared_frame_pool.py:180,215,218`（生成） | ✅ カバー済み |
| R-DM-04 (`DetectionResult`) | （再導入は `DataclassAggregationTest::test_data_models_defines_exactly_the_ipc_structures` が検出） | 🗑️ 削除済み |
| R-DM-05 (`TrackInfo`、2フィールドへ縮小済み） | `TrackInfoContractTest` | ✅ カバー済み |
| R-DM-06 (`TrackingResult`) | `TrackingResultContractTest`（フィールド名/型・必須/任意の区分） | ✅ カバー済み |
| R-DM-07 (デフォルト値) | `TrackingResultContractTest::test_latency_fields_default_to_zero` | ✅ カバー済み |
| R-DM-08 (`detections: Any`) | `TrackingResultContractTest`（`Any` 宣言）、`DetectionsPickleRoundTripTest`（実 `sv.Detections` 格納）、`tests/test_gui_controller.py::RenderImageSmokeTest`（描画経路） | ✅ カバー済み |
| R-DM-09 (picklability) | `DetectionsPickleRoundTripTest`（TrackInfo/レイテンシ/実 `sv.Detections` 込みの pickle 往復） | ✅ カバー済み |
| R-DM-10 (レイテンシ定義) | — | ⬜ 未カバー |
| R-DM-11 (レイテンシ恒等式) | — | ⬜ 未カバー |
| R-DM-12 (`WorkerError`) | — | ⬜ 未カバー（実装済み・新規） |

## タスク

### 文書化 / 整合
- [x] `TrackInfo.box`/`score` を削除したため、box 座標系（xyxy）の論点は `detections`（`sv.Detections.xyxy`）に一本化（対応不要）。
- [ ] `TrackingResult.detections` が `supervision.Detections` を保持する旨を docstring/型注釈（`"sv.Detections"` 文字列注釈等）で明示。
- [ ] レイテンシ3値の定義（R-DM-10）と恒等式 `total == queue + process`（R-DM-11）を `TrackingResult` の docstring に明記。
- [ ] ✅方針確定: `queue_latency_ms` は**リネームせず**、`TrackingResult` の docstring に「撮像→推論開始の入力遅延（共有プール待ち含む）」と定義を明記。
- [ ] steering（`structure.md:21,48`）の「IPC データ構造」記述と本 spec のリンクを相互参照。

### テスト
- [x] dataclass 集約のテスト（R-DM-01、`DataclassAggregationTest`）: `FrameRef`/`TrackInfo`/`TrackingResult`/`WorkerError` がすべて `@dataclass` であり、`data_models` モジュールに定義された dataclass がこの4つに一致する（=集約されている）ことを検証。`tests/test_data_models.py` を新設。
- [x] `FrameRef` のフィールド契約テスト（R-DM-03、`FrameRefContractTest`）: フィールドが `frame_id:int`/`timestamp:float`/`slot:int` のちょうど3つ（=画像本体を含まない）で、全フィールド必須（デフォルト無し）であることを検証。
- [x] 各 dataclass のフィールド/型/デフォルト値（R-DM-05〜07）の検証を `tests/test_data_models.py` に追加（`TrackInfoContractTest`/`TrackingResultContractTest`。5引数構築でレイテンシ2値が `0.0` になることを含む）。
- [ ] レイテンシ2フィールド欠落時の後方互換（消費側 `getattr` 既定 `0.0`、`gui_controller.py:567-572`）を再現するテスト（R-DM-07 の消費側）。

#### `detections: Any` 維持方針のガードレール（✅必須・優先）
> 「`Any` のまま、supervision バージョンアップ時に直してテストパスで OK」という方針が機能する前提。
> 下記が無いと描画が壊れても CI がグリーンのまま通る（requirements「確定事項」参照）。
- [x] **pickle 往復テスト**（`DetectionsPickleRoundTripTest`）: 実 `sv.Detections` を `detections` に入れた `TrackingResult` を pickle→unpickle し、`len()`/`.xyxy`/`.confidence`/`.class_id`/`.tracker_id` と全フィールドが復元されることを検証（R-DM-08/09）。
- [x] **GUI 描画スモークテスト**（`tests/test_gui_controller.py::RenderImageSmokeTest`）: 実 `sv.Detections` を `_render_image`（`src/gui_controller.py:644-689`）経路に通し、`.confidence`/`.class_id`/`.tracker_id` 参照と実 annotator（`sv.BoxAnnotator`/`sv.LabelAnnotator`）再投入が成立することを確認。Tk 依存の `ImageTk.PhotoImage` のみモック。範囲外 `class_id` の「ID のみラベル」分岐も通す。

### 実装 / 改善（将来）
- [ ] `TrackingResult.detections` の `Any` を見直し（`TYPE_CHECKING` 下での `sv.Detections` 注釈導入）。型安全性と循環依存回避のバランスを検討。
- [ ] dataclass に `frozen=True` / `slots=True` を導入し、不変性・メモリ効率を検討（IPC 値オブジェクトとして妥当か要評価）。

### コード削除（✅完了）
- [x] `src/data_models.py` から `FrameData` と `DetectionResult` を削除（不要になった `import numpy as np` も除去）。
- [x] `README.md` のクラス図から `FrameData` クラス・エッジを削除。
- [x] `docs/steering/structure.md:21` の `data_models.py` 注記を実態（`FrameRef/TrackInfo/TrackingResult/WorkerError`）へ更新。
- [x] `R-DM-02`（FrameData）・`R-DM-04`（DetectionResult）は ID を保持しつつ「削除済み」へ更新（ID 安定のため除去せず）。
- [x] `TrackInfo` から `box`/`score` を削除し、`track_id`/`class_id` の2フィールドへ縮小（detections に一本化）。
- [x] 併せて生成側 `src/object_tracking_controller.py:234-241` の `box=`/`score=` を除去。
- [x] `R-DM-05` の定義を2フィールドへ更新。

## メモ / 申し送り

- ✅ `FrameData` / `DetectionResult` は **削除済み**（古い実装の残骸）。`import numpy as np` も除去。
- ✅ `box`/`boxes` 座標系は `xyxy`（削除済みのため、xyxy は `sv.Detections` にのみ残る）。
- ✅ レイテンシ2フィールドのデフォルト `0.0` の経緯は確定（コミット `0ded396`）。dataclass 文法制約 + 後方互換。`getattr` 防御は単一バージョン内では実質冗長。
- ✅ `detections` は **`Any` 型を維持**で確定。ランタイム影響ゼロ・pickle 世代間不整合は同一バージョン往復のため発生しない。実リスクは supervision API 結合のみで「壊れたら追従」方針。前提となるガードレール2本（pickle 往復・描画スモーク）は**整備済み**。
- ✅ `TrackInfo.box`/`score` は **削除済み（detections に一本化）**。`TrackInfo` は `track_id`/`class_id` の2フィールド。
- ✅ `queue_latency_ms` は **リネームせず docstring で定義固定** で確定（名前据え置き）。
- 🔎 レイテンシ恒等式 `total == queue + process` が厳密成立（同一時刻基準）。`process_time_ms` のみ `getattr` 非経由で、2値が後付けである確定済み経緯を補強。
