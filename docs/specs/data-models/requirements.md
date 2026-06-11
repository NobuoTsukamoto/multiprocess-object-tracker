# Requirements — data-models

> 逆生成 spec。出典は [`src/data_models.py`](../../../src/data_models.py)。コードが正。
> 記法は [`../../steering/conventions.md`](../../steering/conventions.md) の EARS 節に従う。
> **各要求に出典 `file:line` を付与済み。人手レビューで突き合わせること。**

## 対象 / スコープ

- **対象モジュール/機能**: [`src/data_models.py`](../../../src/data_models.py)（プロセス間通信で受け渡す `@dataclass` 構造体の定義集約）。
- **スコープ内**: IPC データ構造（`FrameRef` / `TrackInfo` / `TrackingResult` / `WorkerError`）のフィールド定義・型・デフォルト値・後方互換性。（旧 `FrameData` / `DetectionResult` は未使用のため削除済み。）
- **スコープ外**:
  - これらを **生成/消費する側のロジック**（[`object_tracking_controller.py`](../../../src/object_tracking_controller.py)、[`gui_controller.py`](../../../src/gui_controller.py)、[`shared_frame_pool.py`](../../../src/shared_frame_pool.py)）。
  - 共有メモリのリングバッファ実装（[`shared-frame-pool`](../shared-frame-pool/) を参照）。
  - 設定スキーマ（[`config_manager.py`](../../../src/config_manager.py)）。

## 用語集

| 用語 | 定義 |
|:--|:--|
| IPC データ構造 | `multiprocessing.Queue` 等でプロセス間を流れる軽量な値オブジェクト。`@dataclass` で定義する |
| ゼロコピー転送 | 画像本体を Queue に流さず、共有メモリのスロットに置き、`FrameRef`（参照）だけを流す方式。詳細は [`shared-frame-pool`](../shared-frame-pool/) |
| `supervision.Detections` | `supervision`（`sv`）ライブラリの検出/追跡結果コンテナ。`xyxy`/`confidence`/`class_id`/`tracker_id` を持つ |
| 後方互換フィールド | 後から追加され、デフォルト値を持つフィールド。旧プロセス/旧 pickle でも欠落を許容する |

## 要求一覧（EARS）

各要求は一意 ID・EARS 文・出典・対応テストを記す。ID 接頭辞は `R-DM`。

| ID | 種別 | 要求（EARS） | 出典 | 対応テスト |
|:--|:--|:--|:--|:--|
| R-DM-01 | ユビキタス | システムは IPC データ構造をすべて `@dataclass` として [`data_models.py`](../../../src/data_models.py) に集約すること。 | `src/data_models.py:11-49` | `tests/test_data_models.py::DataclassAggregationTest` |
| R-DM-02 | — | **（削除済み）** `FrameData` は未使用のため削除した（実フレームは `FrameRef` + 共有メモリで転送）。 | （削除） | — |
| R-DM-03 | ユビキタス | システムは `FrameRef` を `frame_id:int` / `timestamp:float` / `slot:int` の3フィールドで定義し、共有メモリスロットへの軽量参照として用いること（画像本体を含めない）。 | `src/data_models.py:11-17` | `tests/test_data_models.py::FrameRefContractTest`、`tests/test_shared_frame_pool.py:180,215,218`（生成） |
| R-DM-04 | — | **（削除済み）** `DetectionResult` は未使用のため削除した（検出は `sv.Detections` を直接扱う）。 | （削除） | — |
| R-DM-05 | ユビキタス | システムは `TrackInfo` を `track_id:int` / `class_id:int` の2フィールドで定義すること（box/score は `detections` に一本化し削除済み）。 | `src/data_models.py:20-23` | `tests/test_data_models.py::TrackInfoContractTest` |
| R-DM-06 | ユビキタス | システムは `TrackingResult` を `frame_id:int` / `timestamp:float` / `track_infos:List[TrackInfo]` / `detections:Any` / `process_time_ms:float`（必須）に加え、`queue_latency_ms:float=0.0` / `total_latency_ms:float=0.0`（任意）で定義すること。 | `src/data_models.py:26-36` | `tests/test_data_models.py::TrackingResultContractTest` |
| R-DM-07 | オプション | `TrackingResult` の `queue_latency_ms` / `total_latency_ms` が与えられない場合、システムは既定値 `0.0` を採用すること。 | `src/data_models.py:35-36` | `tests/test_data_models.py::TrackingResultContractTest::test_latency_fields_default_to_zero` |
| R-DM-08 | ユビキタス | システムは `TrackingResult.detections` を `Any` 型として宣言し、`supervision.Detections`（推論+追跡後の `tracked_detections`）を格納できるようにすること。 | `src/data_models.py:33` | — |
| R-DM-09 | ユビキタス | システムは `TrackInfo` と `TrackingResult` の各フィールドを `int`/`float`/`list`/`Any`(sv.Detections) 等の **picklable な値**で構成し、`multiprocessing.Queue` で安全に転送できるようにすること（`track_id`/`class_id` は `int()` キャスト）。 | `src/data_models.py:20-36`、`src/object_tracking_controller.py:234-255` | — |
| R-DM-10 | ユビキタス | システムは `TrackingResult` のレイテンシ3値を、`queue_latency_ms`=撮像→推論開始（入力遅延）、`process_time_ms`=推論開始→終了、`total_latency_ms`=撮像→終了 として記録すること。 | `src/object_tracking_controller.py:191,244-245,253` | — |
| R-DM-11 | ユビキタス | システムは3つのレイテンシが恒等式 `total_latency_ms == queue_latency_ms + process_time_ms`（同一時刻基準）を満たすよう算出すること。 | `src/object_tracking_controller.py:191,244-245` | — |
| R-DM-12 | ユビキタス | システムは `WorkerError` を `source:str`（"camera"/"tracking"）/ `message:str` / `timestamp:float` の3フィールドで定義し、ワーカープロセスが GUI（メインプロセス）へ致命エラーを通知する picklable な値オブジェクトとして用いること。 | `src/data_models.py:39-49` | — |

## 前提条件 / 不変条件

- **生成側の責務**: `TrackInfo` は `tracker_id is not None` の検出に対してのみ生成され、`track_id`/`class_id` を `int()` にキャストして詰める。出典 `src/object_tracking_controller.py:234-241`。
- **`frame_id` による突き合わせ**: `TrackingResult.frame_id` は元フレーム（`FrameRef.frame_id`）と一致し、GUI 側はこの ID でカメラ画像と追跡結果を突き合わせる。出典 `src/object_tracking_controller.py:247-249`、`src/gui_controller.py:603-611`。
- **`timestamp` の意味**: `FrameRef.timestamp` / `TrackingResult.timestamp` は撮像時刻で、レイテンシ算出（`(now - timestamp)*1000`）の基準になる。出典 `src/object_tracking_controller.py:245`、`src/gui_controller.py:546,549`。
- **後方互換アクセス**: 消費側は `queue_latency_ms` / `total_latency_ms` を `getattr(latest, "...", 0.0)` で読み、旧 `TrackingResult` でも欠落を許容する。一方 `process_time_ms` は直接アクセス（`getattr` なし）で、これが当初からの必須フィールドであることを裏付ける。出典 `src/gui_controller.py:566`（直接）, `:567-572`（getattr）。
- **`detections` の所有**: `TrackingResult.detections` には推論+NMS+追跡を経た `tracked_detections`（`sv.Detections`）が入り、GUI のオーバーレイ描画に使われる。出典 `src/object_tracking_controller.py:251`、`src/gui_controller.py:611`。
- **レイテンシ恒等式（R-DM-11）**: 3値は同一の `start_time`/`end_time`/`frame_ref.timestamp` から算出されるため、`total_latency_ms == queue_latency_ms + process_time_ms` が（浮動小数の誤差を除き）厳密に成立する。出典 `src/object_tracking_controller.py:189-191,243-245`。
- **`track_infos` と `detections` の役割分担**: 追跡結果のうち `track_id`/`class_id` は `track_infos`（`List[TrackInfo]`、GUI リスト表示用）、ボックス/スコアは `detections`（`sv.Detections`、GUI 描画用）が担う。box/score の二重持ちは解消済み。出典 `src/gui_controller.py:585-588,660`。

## 確定事項（レビュー反映済み）

- ✅ **`FrameData` / `DetectionResult` は削除（実装済み）**: いずれも `src/` から参照されておらず、古い実装の残骸だった。実フレーム転送は `FrameRef` + 共有メモリ、検出結果は `sv.Detections` 直接扱いで代替済み。→ `data_models.py`・README クラス図・`structure.md` から削除済み。`import numpy as np` も不要となり除去。
- ✅ **座標系は `xyxy`**（左上 x1,y1・右下 x2,y2、ピクセル単位）: `TrackInfo.box`/`DetectionResult.boxes` は削除済みのため、xyxy セマンティクスは `detections`（`sv.Detections.xyxy`）にのみ残る。出典 `src/object_tracking_controller.py:216-221`。
- ✅ **レイテンシ2フィールドのデフォルト `0.0` の経緯**: `queue_latency_ms` / `total_latency_ms` は本日のコミット `0ded396`（"Improve tracker UI usability"）で、フィールド定義・生成側・消費側 `getattr` 防御アクセスが**同一コミット**で追加された。デフォルト `0.0` が付く第一の理由は **dataclass の文法制約**（必須フィールド `process_time_ms` の後ろに置くため、デフォルト必須）。第二に、5引数のみの既存生成箇所を壊さない後方互換。消費側 `getattr(..., 0.0)`（`src/gui_controller.py:567-572`）は混在/将来バージョン向けの防御であり、単一バージョン内では実質冗長。
- ✅ **`TrackingResult.detections` は `Any` 型を維持する（方針確定）**: 実体は `sv.Detections`（追跡後の `tracked_detections`）で、Queue で pickle 転送され、GUI が `len()`/`.confidence`/`.class_id`/`.tracker_id` と annotator 再投入で消費する（出典 `src/gui_controller.py:607,642-655`）。
  - **`Any` 維持は安全**: 型注釈は静的解析のみに作用し、ランタイム挙動は `Any` でも `sv.Detections` でも同一。`Any` を残してもリスクは増えない。
  - **pickle 世代間不整合は発生しない**: 送信側（worker）と受信側（GUI）は同一 venv・同一 supervision バージョンで同時刻に1往復するため、バージョン食い違いは起き得ない。
  - **実リスクは supervision API への暗黙結合**: バージョンアップで属性名・`Detections` 内部構造・annotator API が変わると壊れる。これは型では防げず、「壊れたら修正して追従する」方針で対応する。
  - **方針成立の前提条件**: 「テストが通れば OK」を機能させるには、(1) `TrackingResult`（実 `sv.Detections` を含む）の pickle 往復テスト、(2) GUI 描画経路を実 `sv.Detections` で通すスモークテスト、の2本が**必須**。これが無いと supervision 上げで描画が壊れても CI がグリーンのまま通る。→ tasks.md でガードレールとしてタスク化。

- ✅ **`TrackInfo.box` / `TrackInfo.score` は削除（detections に一本化、実装済み）**: 両フィールドは `src/` のどこからも読まれていなかった。ボックス/スコアは `detections`（`sv.Detections`）が正とし、`TrackInfo` は `track_id`/`class_id` のみ（GUI リスト表示用、`src/gui_controller.py:583`）へ縮小済み。生成側の `box=`/`score=` も除去（`object_tracking_controller.py:234-241`）。R-DM-05 を2フィールド定義へ更新済み。
- ✅ **`queue_latency_ms` はリネームせず docstring で定義固定**: 実体は「撮像→推論開始」の入力遅延（内部名 `last_input_lag_ms`、共有プール待ち含む。出典 `src/object_tracking_controller.py:191,253`）。フィールド名は据え置き、`TrackingResult` の docstring に定義を明記して曖昧さを解消する。→ docstring 追記をタスク化。

## 未確定 / 要レビュー事項

- （現時点で未確定の論点なし。上記すべてレビューで確定済み。）
