# Design — gui-controller

> 逆生成 spec。`src/gui_controller.py` が「どう実現されているか」を記す。コードが正。
> 関連: [`shared-frame-pool`](../shared-frame-pool/)（所有するプール）、[`camera-controller`](../camera-controller/) / [`object-tracking-controller`](../object-tracking-controller/)（生成するワーカー）、[`data-models`](../data-models/)（`TrackingResult`/`WorkerError`）、[`config-manager`](../config-manager/)・[`logger`](../logger/)。

## 概要

`gui-controller` はアプリのメインプロセス兼オーケストレータである。tkinter による全画面 UI を構築し、IPC リソース（2つの共有メモリプール・4つの `Queue`・`stop_event`）を **owner として所有**する。「開始」でワーカープロセス（[`camera-controller`](../camera-controller/) / [`object-tracking-controller`](../object-tracking-controller/)）を起動し、「停止」で協調停止＋強制終了フォールバックにより確実に終わらせ、「終了」で共有メモリを解放する。出典 `src/gui_controller.py:30-800`。

表示面の要点は、① GUI 用プールから読んだフレームを `frame_id` キーでバッファし、② 最新 `TrackingResult` の `frame_id` に一致するフレームへオーバーレイを描く（**フレームと検出の同期表示**）、③ 一致が破棄済みなら最新フレームをオーバーレイ無しで出す、④ render_key 差分で**無駄な再描画を抑止**、の4点。制御面の要点は、⑤ `mark_active`/`mark_inactive` とプロセス join/terminate/kill の段階的停止で**共有メモリの二重所有・リークを防ぐ**こと、⑥ ワーカーの致命エラーを `error_queue` で受けて**全停止＋エラー表示**へ遷移すること。

## 責務と構成要素

| 要素 | 役割 | 出典 |
|:--|:--|:--|
| `__init__` | UI 構築、プール/Queue/Event 生成、状態初期化 | `src/gui_controller.py:47-137` |
| `_calculate_frame_buffer_max` | バッファ上限算出（秒×fps と最小値の大きい方） | `src/gui_controller.py:40-45` |
| `_configure_borderless_maximized` / `_get_work_area_geometry` / `_set_window_icon` | 全画面・作業領域・アイコン | `src/gui_controller.py:146-207` |
| `_create_widgets` | 画像表示・操作・性能テーブル・追跡リストの配置 | `src/gui_controller.py:209-331` |
| `start_tracking` | リセット→ワーカー生成→`mark_active`→起動→ループ開始 | `src/gui_controller.py:352-421` |
| `stop_tracking` / `_stop_process` / `_terminate_process_if_alive` | 協調停止＋段階的強制終了 | `src/gui_controller.py:423-482` |
| `_drain_worker_errors` / `_handle_worker_error` | ワーカーエラー通知の受信と全停止＋エラー表示 | `src/gui_controller.py:490-528` |
| `_drain_frames` / `_drain_track_results` | プール/Queue から最新を吸い上げ | `src/gui_controller.py:530-588` |
| `_select_display_frame` / `_record_overlay_miss_if_stale` | 同期表示フレーム選択、ミスログ | `src/gui_controller.py:590-642` |
| `_render_image` / `_show_inactive_display` | オーバーレイ描画・縮小・減光 | `src/gui_controller.py:644-699` |
| `_update_performance_label` / `_calculate_rate` | FPS/レイテンシ表示 | `src/gui_controller.py:139-144,701-728` |
| `_update_gui` | GUI ループ本体（エラー確認→drain→選択→描画→再スケジュール） | `src/gui_controller.py:730-763` |
| `on_closing` / `run` | 終了処理（停止→close→cleanup→destroy）/ mainloop | `src/gui_controller.py:765-787` |
| `_safe_class_name` | `class_id`→クラス名の範囲安全な解決（範囲外は `None`） | `src/gui_controller.py:789-800` |

## 公開インターフェース

```
GUIController(config_manager, logger)            # :47  UI とリソースを構築
.run()                                           # :786 tkinter mainloop
# UI ボタン経由（コマンドコールバック）:
.start_tracking()  # :352  開始
.stop_tracking()   # :423  停止
.on_closing()      # :765  終了（WM_DELETE_WINDOW / Escape / Alt-F4 / 終了ボタン）
# 静的ヘルパ:
GUIController._calculate_frame_buffer_max(fps, frame_buffer_seconds, minimum)  # :40
GUIController._calculate_rate(timestamps)                                      # :139
GUIController._drain_queue_nowait(queue)                                       # :342
```

## データ構造 / 状態

- **所有 IPC リソース**: `stop_event`（`multiprocessing.Event`）、`tracking_data_queue`/`gui_data_queue`/`track_queue`（各 `maxsize=max_queue_length`）、`error_queue`（ワーカーエラー用・無制限 `multiprocessing.Queue`）、`tracking_pool`/`gui_pool`（`SharedFramePool`）、`gui_pool_reader`（`SharedFrameAccessor`）。出典 `:63-98`。
- **エラー状態**: `_worker_error`（直近に受信した `WorkerError` または `None`）。出典 `:130,363-364,508`。
- **プロセスハンドル**: `camera_process`/`tracking_process`（初期 `None`）。出典 `:100-101,384-401`。
- **フレーム同期状態**: `_frame_buffer`/`_frame_timestamps`（`OrderedDict`、`frame_id` キー）、`_frame_buffer_max`、`_latest_track`（`TrackingResult`）、`_last_display_frame_id`、`_last_render_key`、`_last_display_image`/`_last_display_detections`（非アクティブ再描画用キャッシュ）、`_overlay_miss_count`/`_last_overlay_miss_frame_id`。出典 `:113-127`。
- **性能計測**: `camera_frame_times`/`tracking_result_times`/`display_times`（`deque(maxlen=100)`）、`last_*_latency_ms`/`last_process_time_ms`、`_run_started_at`/`_first_frame_logged`。出典 `:104-111,128-129`。
- **UI 要素**: `status_label`/`video_status_label`/`image_label`/`start_button`/`stop_button`/`exit_button`/`perf_values`/`track_list`、`STATUS_COLORS`。出典 `:31-38,209-331`。

## データフロー / 制御フロー

### ライフサイクル（開始→停止→終了）

```mermaid
flowchart TD
    INIT[__init__: UI + プール/Queue/Event] --> RUN[run: mainloop]
    RUN -->|開始| ST[start_tracking]
    ST --> RST[reset_free_slots + drain + 状態リセット] --> MA[mark_active] --> SP[camera/tracking start]
    SP -->|例外| ERR[stop_event.set + terminate + mark_inactive + raise]
    SP --> LOOP[_update_gui を after5ms で連鎖]
    RUN -->|停止| STOP[stop_tracking: stop_event.set]
    STOP --> JOIN[join5s → terminate → kill]
    JOIN -->|両停止| MI[mark_inactive + 状態 停止中 + 減光表示]
    JOIN -->|生存| FAIL[状態 停止失敗 + error/warning ログ]
    RUN -->|終了| CLOSE[on_closing]
    CLOSE --> CS{workers_alive?}
    CS -->|yes| STOP
    CS --> RC[reader.close] --> CC{workers_alive?}
    CC -->|yes| SKIP[cleanup スキップ + error ログ]
    CC -->|no| CU[mark_inactive + cleanup + destroy]
```

出典: `src/gui_controller.py:352-421,423-454,765-784`。

### GUI ループ（_update_gui、`:730-763`）

```mermaid
flowchart LR
    ERR{_drain_worker_errors} -->|エラー有| HE[_handle_worker_error: 全停止+エラー表示] --> STOP[ループ終了]
    ERR -->|無| DF[_drain_frames: GUI プール→バッファ]
    DF --> DT[_drain_track_results: 最新 TrackingResult]
    DT --> SEL[_select_display_frame]
    SEL -->|matched fid| OV[該当フレーム + detections]
    SEL -->|stale| MISS[overlay miss を一度だけ warning]
    SEL -->|none/pending| NEW[最新フレーム / overlay 無し]
    OV --> RK{render_key 変化?}
    NEW --> RK
    RK -->|yes| RENDER[_render_image + 表示レート/レイテンシ更新]
    RK -->|no| PERF
    RENDER --> PERF[_update_performance_label]
    PERF --> SCHED{stop_event?}
    SCHED -->|未set| DF
    SCHED -->|set| END[ループ終了]
```

出典: `src/gui_controller.py:490-528,530-588,590-617,730-763`。

## 不変条件 / 前提条件

- **owner はメインプロセス**: プール/Queue（`error_queue` 含む）/Event を GUI が生成・所有。ワーカーには `spec`/`queue`/`event` のみ渡る。出典 `:63-98,384-401`。
- **`reset_free_slots` は全停止後のみ**: `start_tracking` 冒頭の reset は前回ワーカー停止済みを前提とする。出典 `:356-357`、[`shared-frame-pool`](../shared-frame-pool/)。
- **`mark_active`/`mark_inactive` 対称**: 起動前 active・停止確定後 inactive・起動失敗時/エラー時も inactive へ巻き戻し。出典 `:403-416,435-436,515-517,779-781`。
- **frame_id 突合**: `TrackingResult.frame_id` でカメラ画像と結合。バッファは `frame_id` 昇順（最古=先頭/最新=末尾）。出典 `:603-611`、[`data-models`](../data-models/)。
- **両プール同一 shape / `n_slots = max_queue_length+2`**: 出典 `:66-95`、[`camera-controller`](../camera-controller/)。
- **GUI ループ単一スレッド**: `after` 連鎖でメインスレッド逐次実行。共有状態のロック不要。出典 `:730-763`。
- **エラー通知は GUI が停止判断**: ワーカーは `WorkerError` を `error_queue` へ置いて `return` するだけ。全停止・状態遷移は GUI（`_handle_worker_error`）が行う。出典 `:503-528`。

## エッジケース / 異常系

- **プロセス起動失敗**: `stop_event.set`→両プロセス terminate→`mark_inactive`→再 raise。プールを active のまま残さない。出典 `:405-416`。
- **停止できないワーカー**: `join5s`→warning→`terminate`→`join2s`→`kill`→`join2s`、各失敗を error ログ。なお生存なら「停止失敗」で共有メモリ reset を見送る。出典 `:456-482,444-454`。
- **終了時もワーカー生存**: 共有メモリ `cleanup` をスキップし error ログ（破損/二重解放回避）。出典 `:774-778`。
- **ワーカーエラー通知**: `error_queue` に `WorkerError` が来たら、`stop_event` で全停止→状態「エラー」＋メッセージ表示→開始再有効化。停止できないワーカーがあれば `mark_inactive` を見送り error ログ（停止失敗と同じ安全策）。出典 `:490-528`。複数エラーが積まれても最初の1件（根本原因）を採用し残りは drain。出典 `:490-501`。
- **オーバーレイミス（追跡結果が古すぎ）**: 対応フレームが破棄済み。最新フレームをオーバーレイ無しで表示し、同一 frame_id につき一度だけ warning。出典 `:612,619-642`。
- **追跡結果が未来 frame_id（未着）**: ミスログを出さず最新フレーム表示（`track_frame_id >= oldest` で早期 return）。出典 `:625-626`。
- **フレームバッファ空**: 描画スキップ（`image is None`）。出典 `:598-600,740`。
- **表示領域が未確定（winfo が 1px 以下）**: gui 設定の `display_image_width/height` にフォールバック。出典 `:674-678`。
- **borderless 不可（TclError）**: 通常ウィンドウへフォールバック。出典 `:147-150`。
- **作業領域取得失敗**: スクリーン全体へフォールバック。出典 `:184-191`。
- **追跡リスト 10 件超**: 先頭10件＋"..."。出典 `:578-588`。
- **`class_id` が `class_names` 範囲外（設定不整合）**: **実装済み**（R-GUI-45）。`_safe_class_name` で範囲チェックし、追跡リストは当該項目をスキップ、オーバーレイはクラス名を省いて `ID:<tracker_id> (<conf>)` のみ表示（例外で止めない）。出典 `:577-588,647-665,789-800`。

## トレードオフ / 設計判断

- **フレームと検出の同期表示**: 推論には時間がかかるため、最新カメラフレームではなく「追跡結果の frame_id に一致するフレーム」へオーバーレイを描く。これで box と画像のズレを防ぐ。代償として表示は推論レイテンシ分だけ過去になる。出典 `:590-617`。
- **render_key 差分描画**: `(表示 frame_id, オーバーレイ frame_id)` が不変なら再描画しない。tkinter 描画コストを抑える。出典 `:746-749`。
- **フレームバッファ上限 = 秒×fps**: 推論が遅れても一致フレームを保持できるよう `frame_buffer_seconds` 分を確保。下限は `max_queue_length+2`。バッファが小さいとオーバーレイミスが増える。出典 `:40-45,113-120,619-642`。
- **borderless maximized + キーバインド**: 没入表示のためタイトルバーを消すが、クローズ手段が失われるので `Escape`/`Alt-F4` を明示バインド（**コメントに意図明記**）。出典 `:151-157`。
- **段階的強制終了**: graceful join → terminate → kill。確実な後始末と、無応答ワーカーでの UI 凍結回避のバランス。出典 `:456-482`。
- **ワーカーエラーの可視化（実装済み・機構確定）**: ワーカーがエラーで `return` するだけでは GUI は区別できず「停止失敗」や無音停止になる。これを解消するため、camera R-CAM-14 / tracking R-OTC-23 と**共通の専用通知**として `data_models.WorkerError`（`source`/`message`/`timestamp`）を**無制限の `error_queue`（`multiprocessing.Queue`）** で GUI に送る。GUI は `_update_gui` 冒頭で `error_queue` を確認し、エラーがあれば `_handle_worker_error` で `stop_event` を立てて全停止 → 状態「エラー」＋メッセージ表示 → 開始ボタン再有効化（再試行可）へ遷移する。Event ではなくエラー内容を運べる Queue を採用した。出典 `:80-82,490-528,730-734`、`src/data_models.py:39-49`。
- **「停止失敗」後はアプリ再起動で復帰（最低限実装で許容）**: `stop_event.set()` 済みのため停止失敗時は `_update_gui` が止まり表示が固まる。リカバリ導線は設けず、アプリ再起動を前提とする（R-GUI-22、確定）。出典 `:444-454,762-763`。
- **`max_frame_skip`/`frame_read_policy` は表示側に作用しない（コード確認済み）**: `gui_controller.py` はこれらのキーを参照しない。`_drain_frames` は `read_nowait` をループで全フレームをバッファ（`frame_buffer_max` 超過分のみ最古を破棄）、`_drain_track_results` は最新 `TrackingResult` のみ保持する。読み飛ばしポリシーは **tracking ワーカーの入力読み出しにのみ作用**し、GUI 表示側の挙動は「全カメラフレームをバッファ＋最新追跡結果で同期表示」で固定。出典 `:530-572`。

## 関連コードパス

- `src/gui_controller.py:30-800` — 本体
- `src/main.py:29-36` — `GUIController` 生成・`run()` 呼び出し
- `src/shared_frame_pool.py` — `SharedFramePool`/`SharedFrameAccessor`（`spec`/`mark_active`/`mark_inactive`/`reset_free_slots`/`cleanup`/`read_nowait`/`close`、[`shared-frame-pool`](../shared-frame-pool/)）
- `src/camera_controller.py` — 生成するワーカー（[`camera-controller`](../camera-controller/)）
- `src/object_tracking_controller.py` — 生成するワーカー（[`object-tracking-controller`](../object-tracking-controller/)）
- `src/data_models.py:20-49` — `TrackInfo`/`TrackingResult`/`WorkerError`（[`data-models`](../data-models/)）
- `src/camera_controller.py:38-48,76` / `src/object_tracking_controller.py:46-56,161` — `_report_error`（ワーカー側送出）
- `src/config_manager.py:42-50` — `GuiConfig`、`:12-19` — `CameraConfig`（[`config-manager`](../config-manager/)）
