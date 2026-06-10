# Structure — ディレクトリ構成・規約・IPC

> 出典: `src/` 各モジュール、[`README.md`](../../README.md)。コードが正。

## ディレクトリ構成

```
multiprocess-object-tracker/
├── AGENTS.md / CLAUDE.md        # エージェント向けエントリ
├── README.md                    # エンドユーザー向け概要
├── config/default.yaml          # アプリ設定（YAML）
├── models/yolox_s.onnx          # 検出モデル
├── src/                         # アプリ本体
│   ├── main.py                  # エントリ（引数解析→ConfigManager/Logger/GUIController）
│   ├── gui_controller.py        # GUI + プロセスのオーケストレーション（メインプロセス）
│   ├── camera_controller.py     # 撮像ワーカープロセス
│   ├── object_tracking_controller.py  # 推論+追跡ワーカープロセス
│   ├── shared_frame_pool.py     # 共有メモリ・リングバッファ（プロセス間フレーム転送）
│   ├── config_manager.py        # 設定読み込み（dataclass 階層）
│   ├── logger.py                # loguru ラッパ（PERFORMANCE レベル）
│   └── data_models.py           # IPC データ構造（FrameRef/TrackInfo/TrackingResult/WorkerError）
├── tests/                       # 単体テスト（unittest, pytest 実行可）
└── docs/                        # steering / specs（本ドキュメント群）
```

## モジュールの役割と境界

- **GUIController（メインプロセス）**: tkinter UI、開始/停止ボタン、フレーム表示・オーバーレイ、性能表示、ワーカーの生成/停止。共有メモリプール（owner）を所有する。
- **CameraController（ワーカー）**: カメラから取得 → 設定サイズへリサイズ → 2つの `SharedFramePool`（追跡用・GUI 表示用）へ書き込み。
- **ObjectTrackingController（ワーカー）**: 追跡用プールから読み出し → ONNX 推論 + NMS + フィルタ → `supervision.ByteTrack` → `TrackingResult` を Queue で GUI へ。
- **ConfigManager / Logger**: 全コントローラから参照される横断ユーティリティ。

依存関係図（クラス図）は [`README.md`](../../README.md) の「モジュール構成図」を参照。

## IPC（プロセス間通信）の規約

- **フレーム転送はゼロコピー**: 画像バイト列を pickle で送らず、[`shared_frame_pool.py`](../../src/shared_frame_pool.py) の共有メモリリングバッファに格納し、Queue には軽量な参照 `FrameRef`(frame_id, timestamp, slot) だけを流す。
  - 所有権: owner（`SharedFramePool`、メインプロセス）が共有メモリ・`free_queue`・`data_queue` を生成。ワーカーは `SharedFrameSpec` を受け取り `SharedFrameAccessor` でアタッチする。
  - スロット所有権の不変条件: free_queue ↔ data_queue 間でスロット番号を受け渡し、二重所有を避ける。`reset_free_slots()` は **全ワーカー停止後のみ**呼ぶこと（[`shared_frame_pool.py`](../../src/shared_frame_pool.py) の guard 参照）。
- **追跡結果**: `TrackingResult`（frame_id/timestamp/track_infos/detections/各種 latency）を `multiprocessing.Queue` で GUI に送る。GUI 側は frame_id でカメラ画像と突き合わせる。
- **停止通知**: `multiprocessing.Event`（stop_event）。ワーカーは監視し、セットされたらリソース解放して終了する。
- **エラー通知**: ワーカーの致命エラー（カメラオープン失敗・ONNX ロード失敗）は `WorkerError`(source, message, timestamp) を専用の `error_queue`（`multiprocessing.Queue`、GUI が owner）で GUI に送る。GUI は受信すると全ワーカーを停止し状態「エラー」を表示する。プロセスの自然死（stop_event 起因）とエラー終了を区別するための経路（[`data_models.py`](../../src/data_models.py) の `WorkerError`、gui-controller R-GUI-44 / camera R-CAM-14 / tracking R-OTC-23）。
- **読み出しポリシー**: `fifo`（全フレーム）/ `latest`（最新まで読み飛ばし）/ `bounded_latest`（最大 `max_frame_skip` まで読み飛ばし）。設定 `tracking.frame_read_policy` / `tracking.max_frame_skip`。

## 命名・記述規約

- ファイル/モジュール名: `snake_case`。クラス: `PascalCase`。
- IPC データ構造は [`data_models.py`](../../src/data_models.py) に集約（`@dataclass`）。新しい IPC メッセージはここに追加する。
- 設定スキーマは [`config_manager.py`](../../src/config_manager.py) の dataclass に追加し、`config/default.yaml` と README の設定表を同期する。スキーマと全キーの消費側対応は [`config-manager` spec](../specs/config-manager/) を参照。
- ドキュメント本文は日本語、識別子（型名・関数名・skill name 等）は英語。詳細は [`conventions.md`](conventions.md)。
