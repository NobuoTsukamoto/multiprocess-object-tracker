# Requirements — gui-controller

> 逆生成 spec。出典は [`src/gui_controller.py`](../../../src/gui_controller.py)。コードが正。
> 記法は [`../../steering/conventions.md`](../../steering/conventions.md) の EARS 節に従う。
> **各要求に出典 `file:line` を付与済み。人手レビューで突き合わせること。**

## 対象 / スコープ

- **対象モジュール/機能**: [`src/gui_controller.py`](../../../src/gui_controller.py)（メインプロセス。tkinter UI、共有メモリプール（owner）の所有、ワーカープロセス（camera / tracking）の生成・停止、フレーム表示＋オーバーレイ、性能表示のオーケストレーション）。
- **スコープ内**: `GUIController` の初期化（UI 構築・キュー/プール生成）・開始（`start_tracking`）・停止（`stop_tracking`）・終了（`on_closing`）・GUI ループ（`_update_gui` とその下請け：フレーム/結果の drain・表示フレーム選択・描画・性能ラベル更新）・状態表示・プロセス停止ヘルパ。
- **スコープ外**:
  - 共有メモリプールの内部実装（[`shared-frame-pool`](../shared-frame-pool/)）。`SharedFramePool` / `SharedFrameAccessor` の `spec`/`mark_active`/`mark_inactive`/`reset_free_slots`/`cleanup`/`read_nowait`/`close` は所与。
  - ワーカープロセス本体（[`camera-controller`](../camera-controller/) / [`object-tracking-controller`](../object-tracking-controller/)）。
  - `TrackingResult`/`TrackInfo`/`FrameRef` の定義（[`data-models`](../data-models/)）。
  - 設定スキーマ（[`config-manager`](../config-manager/)）、ロガー（[`logger`](../logger/)）。
  - supervision のアノテーション描画ロジック（`BoxAnnotator`/`LabelAnnotator` は所与）。

## 用語集

| 用語 | 定義 |
|:--|:--|
| GUI 用プール / 追跡用プール | GUI 表示用 / 推論用の `SharedFramePool`。GUI（メインプロセス）が owner として両方を生成・所有する |
| フレームバッファ | `frame_id` をキーに直近フレーム画像と timestamp を保持する `OrderedDict`（`_frame_buffer`/`_frame_timestamps`） |
| 表示フレーム選択 | 最新追跡結果に一致するフレームを優先表示し、無ければ最新フレームをオーバーレイ無しで表示する処理（`_select_display_frame`） |
| オーバーレイミス | 最新追跡結果の `frame_id` がフレームバッファの最古より古く、対応フレームが既に破棄されている状態（`_record_overlay_miss_if_stale`） |
| render_key | `(表示 frame_id, オーバーレイ対象 frame_id)` のタプル。前回と同一なら再描画をスキップする差分キー（`_update_gui`） |
| borderless maximized | タイトルバー無し（`overrideredirect(True)`）で作業領域いっぱいに広げたウィンドウ |
| 状態色 | `STATUS_COLORS`（実行中/待機中/停止処理中/停止中/停止失敗/エラー）に対応する背景色 |

## 要求一覧（EARS）

各要求は一意 ID・EARS 文・出典・対応テストを記す。ID 接頭辞は `R-GUI`。専用テストは [`tests/test_gui_controller.py`](../../../tests/test_gui_controller.py)（純関数寄りの一部のみカバー）。

### 初期化 / リソース所有

| ID | 種別 | 要求（EARS） | 出典 | 対応テスト |
|:--|:--|:--|:--|:--|
| R-GUI-01 | イベント駆動 | 生成されたとき、システムは `config_manager`・ロガー（`logger.get_logger()`）・gui/camera 設定を保持すること。 | `src/gui_controller.py:47-51` | — |
| R-GUI-02 | イベント駆動 | 生成されたとき、システムは tkinter ルートウィンドウを作成し、タイトル「物体検出・追跡」とアイコンを設定し、gui 設定のサイズ/位置で初期配置すること。 | `src/gui_controller.py:53-59,193-207` | — |
| R-GUI-03 | イベント駆動 | 生成されたとき、システムをタイトルバー無し（`overrideredirect(True)`）かつ作業領域いっぱいの borderless maximized 表示にすること。`TclError` のときは通常表示にフォールバックすること。 | `src/gui_controller.py:60,146-160` | — |
| R-GUI-04 | イベント駆動 | borderless 化でクローズ手段が失われるため、システムは `Escape` と `Alt-F4` を `on_closing` にバインドすること。 | `src/gui_controller.py:156-157` | — |
| R-GUI-05 | イベント駆動 | 作業領域取得時、Windows では `SystemParametersInfoW`（`SPI_GETWORKAREA`）でタスクバーを除いた領域を求め、取得失敗/非 Windows ではスクリーン全体にフォールバックすること。 | `src/gui_controller.py:162-191` | — |
| R-GUI-06 | イベント駆動 | 生成されたとき、システムは協調停止用 `multiprocessing.Event`（`stop_event`）を作成すること。 | `src/gui_controller.py:63` | — |
| R-GUI-07 | イベント駆動 | 生成されたとき、システムは追跡用/GUI 用/追跡結果用の3つの `multiprocessing.Queue`（各 `maxsize=camera.max_queue_length`）を作成すること。 | `src/gui_controller.py:64,71-79` | — |
| R-GUI-08 | イベント駆動 | 生成されたとき、システムは `frame_shape=(camera.height, camera.width, 3)`・`n_slots=max_queue_length+2` で追跡用/GUI 用の2つの `SharedFramePool` を owner として作成すること。 | `src/gui_controller.py:66-95` | — |
| R-GUI-09 | イベント駆動 | 生成されたとき、システムは GUI 用プールに対する読み出しハンドル（`SharedFrameAccessor`）をメインプロセス内に作成すること。 | `src/gui_controller.py:98` | — |
| R-GUI-10 | イベント駆動 | 生成されたとき、システムは性能計測用の固定長 deque（`maxlen=100`）3本と各レイテンシ変数を初期化すること。 | `src/gui_controller.py:104-111` | — |
| R-GUI-11 | イベント駆動 | 生成されたとき、システムはフレームバッファ上限を `_calculate_frame_buffer_max(fps, frame_buffer_seconds, minimum=max_queue_length+2)` で決定すること。 | `src/gui_controller.py:40-45,113-120` | `tests/test_gui_controller.py::GUIControllerTest::test_frame_buffer_max_uses_seconds_but_keeps_minimum` |
| R-GUI-12 | ユビキタス | システムは `frame_buffer_max` を「`ceil(max(0,fps) × max(0.0,seconds))` と `minimum` の大きい方」として算出すること。 | `src/gui_controller.py:40-45` | `tests/test_gui_controller.py::GUIControllerTest::test_frame_buffer_max_uses_seconds_but_keeps_minimum` |

### 開始（start_tracking）

| ID | 種別 | 要求（EARS） | 出典 | 対応テスト |
|:--|:--|:--|:--|:--|
| R-GUI-13 | イベント駆動 | 「開始」時、システムは前回実行で残ったスロットを回収するため両プールの `reset_free_slots()` を呼ぶこと。 | `src/gui_controller.py:356-357` | — |
| R-GUI-14 | イベント駆動 | 「開始」時、システムは `track_queue` を全 drain し、drain 件数があれば info ログすること。 | `src/gui_controller.py:342-350,358-362` | `tests/test_gui_controller.py::GUIControllerTest::test_drain_queue_nowait_returns_drained_item_count` |
| R-GUI-15 | イベント駆動 | 「開始」時、システムはフレームバッファ・最新追跡結果・表示キャッシュ・性能計測・各レイテンシをリセットし、`run_started_at` を記録し、`stop_event` をクリアすること。 | `src/gui_controller.py:365-382` | — |
| R-GUI-16 | イベント駆動 | 「開始」時、システムは `CameraController`（追跡用/GUI 用 spec を渡す）と `ObjectTrackingController`（追跡用 spec と `track_queue` を渡す）を生成し、両者に共通の `stop_event`・`error_queue` を渡すこと。 | `src/gui_controller.py:384-401` | — |
| R-GUI-17 | イベント駆動 | 「開始」時、システムはプロセス起動前に両プールを `mark_active()` し、起動後にボタン状態（開始=無効/停止=有効）と状態「実行中」を設定して GUI ループ（`_update_gui`）を開始すること。 | `src/gui_controller.py:403-404,418-421` | — |
| R-GUI-18 | 異常系 | プロセス起動（`start()`）が例外を投げたとき、システムは `stop_event` をセットし両プロセスを終了させ、両プールを `mark_inactive()` してから例外を再送出すること。 | `src/gui_controller.py:405-416` | — |

### 停止（stop_tracking）

| ID | 種別 | 要求（EARS） | 出典 | 対応テスト |
|:--|:--|:--|:--|:--|
| R-GUI-19 | イベント駆動 | 「停止」時、システムは状態を「停止処理中」に更新して即時再描画し、`stop_event` をセットすること。 | `src/gui_controller.py:424-428` | — |
| R-GUI-20 | イベント駆動 | 「停止」時、システムは camera/tracking プロセスをこの順で停止待ちすること。 | `src/gui_controller.py:430-433` | — |
| R-GUI-21 | イベント駆動 | 両プロセスが停止したとき、システムは両プールを `mark_inactive()` し、ボタン状態（開始=有効/停止=無効）と状態「停止中」を設定し、最後の表示画像を減光して表示し、所要時間を info ログすること。 | `src/gui_controller.py:434-443` | — |
| R-GUI-22 | 異常系 | いずれかのプロセスが停止しなかったとき、システムは error ログ（プール reset 不可）を出し、開始=無効/停止=有効のまま状態「停止失敗」を設定し、所要時間を warning ログすること。 | `src/gui_controller.py:444-454` | — |
| R-GUI-23 | イベント駆動 | プロセス停止待ち時、システムは `join(timeout=5)` し、なお生存していれば warning ログして強制終了すること（停止できれば `True`）。 | `src/gui_controller.py:456-467` | — |
| R-GUI-24 | 異常系 | プロセスが `terminate()` 後も生存するとき、システムは `join(timeout=2)`→`kill()`→`join(timeout=2)` の順で強制終了を試み、各段の失敗を error ログすること。 | `src/gui_controller.py:469-482` | — |

### GUI ループ / 表示

| ID | 種別 | 要求（EARS） | 出典 | 対応テスト |
|:--|:--|:--|:--|:--|
| R-GUI-25 | 状態駆動 | `stop_event` がセットされていない間、システムは GUI ループを `after(5ms)` で繰り返すこと（セット時は再スケジュールしない）。 | `src/gui_controller.py:730-763` | — |
| R-GUI-26 | イベント駆動 | GUI ループ各反復で、システムは GUI 用プールから読める全フレームを `read_nowait` で取り出し、`frame_id` をキーに画像と timestamp をバッファし、上限超過分は最古から破棄すること。 | `src/gui_controller.py:530-553` | — |
| R-GUI-27 | イベント駆動 | 開始後に最初の GUI フレームを受信したとき、システムは frame_id・経過時間・カメラレイテンシを一度だけ info ログすること。 | `src/gui_controller.py:540-547` | — |
| R-GUI-28 | イベント駆動 | GUI ループ各反復で、システムは `track_queue` を drain して最新の `TrackingResult` のみ保持し、`process_time_ms`/`queue_latency_ms`/`total_latency_ms` を更新し、追跡物体リスト（先頭10件＋超過時 "..."）を更新すること。 | `src/gui_controller.py:555-588` | — |
| R-GUI-29 | イベント駆動 | 表示フレーム選択時、最新追跡結果の `frame_id` がバッファに在れば、システムはそれより古いフレームを破棄したうえで当該フレームと検出（オーバーレイ）を返すこと。 | `src/gui_controller.py:603-611` | `tests/test_gui_controller.py::GUIControllerTest::test_select_display_frame_prefers_matching_tracking_frame` |
| R-GUI-30 | 異常系 | 最新追跡結果の `frame_id` がバッファ最古より古い（対応フレーム破棄済み）とき、システムはオーバーレイミスを同一 frame_id につき一度だけ warning ログすること。 | `src/gui_controller.py:612,619-642` | `tests/test_gui_controller.py::GUIControllerTest::test_select_display_frame_logs_stale_overlay_miss_once` |
| R-GUI-31 | イベント駆動 | 追跡結果が無い／一致フレームが未着（未来の frame_id）／バッファに一致が無いとき、システムは最新フレームをオーバーレイ無しで表示し、ミスログを出さないこと。 | `src/gui_controller.py:603-617,625-626` | `tests/test_gui_controller.py::GUIControllerTest::test_select_display_frame_does_not_log_when_track_frame_is_pending` |
| R-GUI-32 | 異常系 | フレームバッファが空のとき、システムは表示対象を持たず（`None`）描画をスキップすること。 | `src/gui_controller.py:598-600,740` | — |
| R-GUI-33 | イベント駆動 | 表示フレームか追跡結果が前回と変化した（render_key 不一致）ときのみ、システムは画像を再描画し、表示レート/表示レイテンシを更新し、表示キャッシュを更新すること。 | `src/gui_controller.py:740-758` | — |
| R-GUI-34 | イベント駆動 | 検出があるフレームを描画するとき、システムは `BoxAnnotator`＋`LabelAnnotator`（ラベルは `ID:<tracker_id> <class_name> (<conf>)`）でオーバーレイを描き、BGR→RGB 変換のうえ表示領域に収まるよう縦横比維持で LANCZOS 縮小すること。 | `src/gui_controller.py:644-689` | — |
| R-GUI-35 | 状態駆動 | 非アクティブ表示（停止中など）の間、システムは直近表示画像をグレースケール化＋減光（明度 0.45）して状態文字とともに表示すること。 | `src/gui_controller.py:670-672,691-699` | — |
| R-GUI-36 | ユビキタス | システムは状態文字に応じた背景色（`STATUS_COLORS`、未知は「待機中」色）を状態ラベルに適用し、実行中は中央オーバーレイを隠し、非実行中は中央オーバーレイを表示すること。 | `src/gui_controller.py:31-38,333-340` | — |
| R-GUI-37 | ユビキタス | システムは camera/detection/display の FPS をサンプル間経過時間から算出（2点未満は 0.0）し、各レイテンシ（待ち/処理/合計）を性能テーブルに表示すること。 | `src/gui_controller.py:139-144,701-728` | `tests/test_gui_controller.py::GUIControllerTest::test_calculate_rate_uses_elapsed_between_samples` |

### 終了（on_closing）

| ID | 種別 | 要求（EARS） | 出典 | 対応テスト |
|:--|:--|:--|:--|:--|
| R-GUI-38 | イベント駆動 | ウィンドウクローズ（`WM_DELETE_WINDOW`/`Escape`/`Alt-F4`/「終了」）時、ワーカーが生存していればシステムはまず `stop_tracking` を実行すること。 | `src/gui_controller.py:137,270-276,765-767` | — |
| R-GUI-39 | イベント駆動 | クローズ時、システムは GUI 用プールの読み出しハンドルを `close()` すること（例外は握りつぶす）。 | `src/gui_controller.py:768-772` | — |
| R-GUI-40 | 異常系 | クローズ時にワーカーがまだ生存しているとき、システムは共有メモリ解放をスキップし error ログすること（二重所有/破損回避）。 | `src/gui_controller.py:774-778` | — |
| R-GUI-41 | イベント駆動 | クローズ時にワーカーが全停止しているとき、システムは両プールを `mark_inactive()`＋`cleanup()` し、ルートウィンドウを破棄すること。 | `src/gui_controller.py:779-784` | — |
| R-GUI-42 | ユビキタス | `_workers_alive` は camera/tracking のいずれかが生存していれば真を返すこと。 | `src/gui_controller.py:484-488` | `tests/test_gui_controller.py::GUIControllerTest::test_workers_alive_checks_camera_and_tracking_processes` |
| R-GUI-43 | イベント駆動 | `run()` が呼ばれたとき、システムは tkinter のメインループを開始すること。 | `src/gui_controller.py:786-787` | — |

### ワーカーエラー通知（実装済み）

| ID | 種別 | 要求（EARS） | 出典 | 対応テスト |
|:--|:--|:--|:--|:--|
| R-GUI-44 | 異常系 | ワーカーがカメラオープン失敗（camera R-CAM-14）／ONNX ロード失敗（tracking R-OTC-23）を `WorkerError` として `error_queue` に通知したとき、システムは `stop_event` をセットして両ワーカーを停止し、状態「エラー」（専用の状態色＋エラー文）を表示し、開始ボタンを再有効化（再試行可）すること。これによりプロセスの自然死（stop_event 起因）とエラー終了を区別する。 | `src/gui_controller.py:503-528,730-734` | — |
| R-GUI-46 | イベント駆動 | 生成されたとき、システムはワーカーエラー用の `error_queue`（無制限 `multiprocessing.Queue`）を owner として作成し、開始時に両ワーカーへ渡すこと。 | `src/gui_controller.py:80-82,377-401` | — |
| R-GUI-47 | イベント駆動 | GUI ループ各反復の冒頭で、システムは `error_queue` を確認し、エラーがあれば最初の1件（=根本原因）を取り出して残りを drain し、エラー処理へ遷移すること。 | `src/gui_controller.py:490-501,730-734` | `tests/test_gui_controller.py::GUIControllerTest::test_drain_worker_errors_returns_first_and_drains_rest`, `::test_drain_worker_errors_returns_none_when_empty` |
| R-GUI-48 | イベント駆動 | 「開始」時、システムは `error_queue` を drain し直前のエラー状態（`_worker_error`）をリセットすること。 | `src/gui_controller.py:363-364` | — |

### class_id 範囲外ガード（実装済み）

| ID | 種別 | 要求（EARS） | 出典 | 対応テスト |
|:--|:--|:--|:--|:--|
| R-GUI-45 | 異常系 | 描画／追跡リスト更新で `class_id` が `detection.class_names` の範囲外（設定不整合）のとき、システムは例外で表示を止めず、追跡リストでは当該項目を無視（スキップ）し、オーバーレイではクラス名を省いて `ID:<tracker_id> (<conf>)` のみ表示すること。 | `src/gui_controller.py:577-588,647-665` | — |
| R-GUI-49 | ユビキタス | システムは `class_id` が `0 <= class_id < len(class_names)` のときのみクラス名を返し、範囲外では `None` を返す共通ヘルパ（`_safe_class_name`）を提供すること。 | `src/gui_controller.py:789-800` | `tests/test_gui_controller.py::GUIControllerTest::test_safe_class_name_returns_name_in_range`, `::test_safe_class_name_returns_none_out_of_range` |

## 前提条件 / 不変条件

- **メインプロセスが owner**: 共有メモリプール・各 Queue（`error_queue` を含む）・`stop_event` は GUI（メインプロセス）が生成・所有する。ワーカーには pickle 可能な `spec`/`queue`/`event` のみ渡る。出典 `src/gui_controller.py:63-98,384-401`、[`structure.md`](../../steering/structure.md) IPC 節。
- **スロット二重所有の回避**: `reset_free_slots()` は**全ワーカー停止後のみ**呼ぶ。`start_tracking` 冒頭で呼ぶのは前回ワーカーが既に停止済み（停止は `stop_tracking`/`on_closing` で待機）である前提に依存する。出典 `src/gui_controller.py:356-357`、[`shared-frame-pool`](../shared-frame-pool/)。
- **`mark_active`/`mark_inactive` の対称性**: プロセス起動前に `mark_active`、停止確定後に `mark_inactive`。起動失敗時・エラー時も `mark_inactive` で巻き戻す。出典 `src/gui_controller.py:403-416,435-436,515-517`。
- **両プール同一 shape**: 追跡用/GUI 用とも `frame_shape=(camera.height, camera.width, 3)`。CameraController が同一フレームを両プールへ書く前提と整合。出典 `src/gui_controller.py:68,84-95`、[`camera-controller`](../camera-controller/)。
- **`n_slots = max_queue_length + 2`**: consumer が常に在庫スロットを1つ確保できるよう余裕を持たせる。出典 `src/gui_controller.py:66-69`。
- **`frame_id` 突合**: GUI は `TrackingResult.frame_id` でカメラ画像（フレームバッファ）と追跡結果を結合する。出典 `src/gui_controller.py:603-611`、[`data-models`](../data-models/)。
- **フレームバッファは frame_id 昇順**: `OrderedDict` に到着順（=`frame_id` 昇順）で挿入される前提で「最古=先頭」「最新=末尾」を使う。出典 `src/gui_controller.py:551-553,607,615`。
- **GUI ループ単一スレッド**: エラー確認・drain・選択・描画・再スケジュールは tkinter メインスレッドの `after` 連鎖で逐次実行される。出典 `src/gui_controller.py:730-763`。
- **エラー通知は GUI が停止判断**: ワーカーは `WorkerError` を `error_queue` に置くだけで自プロセスを `return` する。全停止・状態遷移・再試行可否の判断は GUI（`_handle_worker_error`）が一手に行う。出典 `src/gui_controller.py:503-528`。

## 確定事項（レビュー反映済み）

- ✅ **ワーカーエラーは専用エラーとして GUI に表示（R-GUI-44、実装済み）**: カメラオープン失敗（camera R-CAM-14）・ONNX ロード失敗（tracking R-OTC-23）を `data_models.WorkerError` として専用 `error_queue` で GUI に伝え、状態「エラー」（専用色＋エラー文）で表示する。**機構はステータス Queue に確定**（`multiprocessing.Queue`、無制限）。エラー時は `stop_event` で全停止し、開始ボタンを再有効化して再試行可能にする。出典 `src/gui_controller.py:80-82,490-528,720-724`、`src/data_models.py:56-67`。
- ✅ **「停止失敗」後はアプリ再起動を要する（最低限実装で許容）**: `stop_tracking` は `stop_event.set()` 済みのため停止失敗時に `_update_gui` が再スケジュールされず表示が固まる（`:762-763`）。これは許容とし、リカバリ導線は設けず**アプリ再起動で復帰**する前提とする（最低限の実装）。
- ✅ **`class_id` 範囲外は無視（R-GUI-45、実装済み）**: 共通ヘルパ `_safe_class_name`（R-GUI-49）で範囲チェックし、追跡リストは当該項目をスキップ、オーバーレイはクラス名を省いて `ID:<tracker_id> (<conf>)` のみ表示する（例外で止めない）。出典 `:577-588,647-665,789-800`。

## 未確定 / 要レビュー事項

- [ ] **`start_tracking` 中の例外通知**: 起動例外は再送出される（`:416`）が、`main.py` は捕捉して終了する（`src/main.py:41-43`）。GUI 上のユーザー通知（ダイアログ等）が無くて良いか確認（R-GUI-44 の専用エラー表示に寄せるかも含めて検討）。
- [ ] **`_drain_track_results` の Listbox 更新コスト**: 反復ごとに `track_list.delete(0, END)`＋再挿入（`:577-588`）。多数追跡時の再描画コストは許容範囲か確認（将来改善）。
