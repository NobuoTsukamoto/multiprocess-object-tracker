# Tasks — data-models

> 逆生成 spec。`src/data_models.py` のテストカバレッジ状況と、未文書化挙動・テスト不足・将来改善を列挙する。

## テストカバレッジ状況（逆生成時）

`data_models` 専用のテストは存在しない。`FrameRef` のみ `test_shared_frame_pool.py` で間接的に生成される（構築のみ、フィールド検証はなし）。

| 要求 ID | 対応テスト | 状態 |
|:--|:--|:--|
| R-DM-01 | — | ⬜ 未カバー |
| R-DM-02 (`FrameData`) | — | 🗑️ 削除済み |
| R-DM-03 (`FrameRef`) | `tests/test_shared_frame_pool.py:180,215,218`（生成のみ） | 🟡 部分的（フィールド契約は未検証） |
| R-DM-04 (`DetectionResult`) | — | 🗑️ 削除済み |
| R-DM-05 (`TrackInfo`、2フィールドへ縮小済み） | — | ⬜ 未カバー（実装済み） |
| R-DM-06 (`TrackingResult`) | — | ⬜ 未カバー |
| R-DM-07 (デフォルト値) | — | ⬜ 未カバー |
| R-DM-08 (`detections: Any`) | — | ⬜ 未カバー |
| R-DM-09 (picklability) | — | ⬜ 未カバー |
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
- [ ] `tests/test_data_models.py` を新設し、各 dataclass のフィールド/型/デフォルト値（R-DM-05〜07）を検証。
- [ ] レイテンシ2フィールド欠落時の後方互換（`getattr` 既定 `0.0`）を再現するテスト（R-DM-07）。

#### `detections: Any` 維持方針のガードレール（✅必須・優先）
> 「`Any` のまま、supervision バージョンアップ時に直してテストパスで OK」という方針が機能する前提。
> 下記が無いと描画が壊れても CI がグリーンのまま通る（requirements「確定事項」参照）。
- [ ] **pickle 往復テスト**: 実 `sv.Detections` を `detections` に入れた `TrackingResult` を pickle→unpickle し、`len()`/`.confidence`/`.class_id`/`.tracker_id` が復元されることを検証（R-DM-08/09）。
- [ ] **GUI 描画スモークテスト**: 実 `sv.Detections` を `_render_image`（`src/gui_controller.py:644-689`）経路に通し、`.confidence`/`.class_id`/`.tracker_id` 参照と annotator 再投入が成立することを確認。

### 実装 / 改善（将来）
- [ ] `TrackingResult.detections` の `Any` を見直し（`TYPE_CHECKING` 下での `sv.Detections` 注釈導入）。型安全性と循環依存回避のバランスを検討。
- [ ] dataclass に `frozen=True` / `slots=True` を導入し、不変性・メモリ効率を検討（IPC 値オブジェクトとして妥当か要評価）。

### コード削除（✅完了）
- [x] `src/data_models.py` から `FrameData` と `DetectionResult` を削除（不要になった `import numpy as np` も除去）。
- [x] `README.md` のクラス図から `FrameData` クラス・エッジを削除。
- [x] `docs/steering/structure.md:21` の `data_models.py` 注記を実態（`FrameRef/TrackInfo/TrackingResult/WorkerError`）へ更新。
- [x] `R-DM-02`（FrameData）・`R-DM-04`（DetectionResult）は ID を保持しつつ「削除済み」へ更新（ID 安定のため除去せず）。
- [x] `TrackInfo` から `box`/`score` を削除し、`track_id`/`class_id` の2フィールドへ縮小（detections に一本化）。
- [x] 併せて生成側 `src/object_tracking_controller.py:213-220` の `box=`/`score=` を除去。
- [x] `R-DM-05` の定義を2フィールドへ更新。

## メモ / 申し送り

- ✅ `FrameData` / `DetectionResult` は **削除済み**（古い実装の残骸）。`import numpy as np` も除去。
- ✅ `box`/`boxes` 座標系は `xyxy`（削除済みのため、xyxy は `sv.Detections` にのみ残る）。
- ✅ レイテンシ2フィールドのデフォルト `0.0` の経緯は確定（コミット `0ded396`）。dataclass 文法制約 + 後方互換。`getattr` 防御は単一バージョン内では実質冗長。
- ✅ `detections` は **`Any` 型を維持**で確定。ランタイム影響ゼロ・pickle 世代間不整合は同一バージョン往復のため発生しない。実リスクは supervision API 結合のみで「壊れたら追従」方針。ただし上記ガードレール2本（pickle 往復・描画スモーク）が方針成立の前提。
- ✅ `TrackInfo.box`/`score` は **削除済み（detections に一本化）**。`TrackInfo` は `track_id`/`class_id` の2フィールド。
- ✅ `queue_latency_ms` は **リネームせず docstring で定義固定** で確定（名前据え置き）。
- 🔎 レイテンシ恒等式 `total == queue + process` が厳密成立（同一時刻基準）。`process_time_ms` のみ `getattr` 非経由で、2値が後付けである確定済み経緯を補強。
