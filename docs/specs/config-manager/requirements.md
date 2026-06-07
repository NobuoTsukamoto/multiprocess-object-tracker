# Requirements — config-manager

> 逆生成 spec。出典は [`src/config_manager.py`](../../../src/config_manager.py)。コードが正。
> 記法は [`../../steering/conventions.md`](../../steering/conventions.md) の EARS 節に従う。
> **各要求に出典 `file:line` を付与済み。人手レビューで突き合わせること。**

## 対象 / スコープ

- **対象モジュール/機能**: [`src/config_manager.py`](../../../src/config_manager.py)（YAML 設定を dataclass 階層へ読み込み、各コントローラへ提供する）。
- **スコープ内**: 設定スキーマ（5つの `@dataclass` + 集約 `AppConfig`）の定義・デフォルト値、`ConfigManager` の読み込み（`_load_config`/`_create_app_config`）・取得（`get_config`）、欠落/未知キー/不正パス等の挙動。
- **スコープ外**:
  - 各設定値を**消費する側**のロジック（camera/object_tracking/gui controller, logger）。本 spec では「どのキーがどこで使われるか」を出典付きで一覧化するに留める。
  - `frame_read_policy` の妥当値検証（消費側 [`object_tracking_controller.py:44-65`](../../../src/object_tracking_controller.py) が担う）。
  - 引数解析・例外の最終ハンドリング（[`main.py:18-43`](../../../src/main.py)）。

## 用語集

| 用語 | 定義 |
|:--|:--|
| 設定 dataclass | `CameraConfig` 等、1セクションを表す `@dataclass`。全フィールドにデフォルト値を持つ |
| `AppConfig` | 5セクションを束ねる集約 dataclass（`camera`/`detection`/`tracking`/`gui`/`logging`） |
| セクション | YAML のトップレベルキー（`camera:` 等）。設定 dataclass 1個に対応する |
| 未消費キー | スキーマに定義されているが `src/` のどこからも読まれていない設定キー |

## 要求一覧（EARS）

各要求は一意 ID・EARS 文・出典・対応テストを記す。ID 接頭辞は `R-CM`。専用テストは**存在しない**（`tests/test_config_manager.py` 無し）。

| ID | 種別 | 要求（EARS） | 出典 | 対応テスト |
|:--|:--|:--|:--|:--|
| R-CM-01 | ユビキタス | システムは設定スキーマを5つの `@dataclass`（`CameraConfig`/`DetectionConfig`/`TrackingConfig`/`GuiConfig`/`LoggingConfig`）と、それらを束ねる `AppConfig` で定義すること。 | `src/config_manager.py:12-64` | — |
| R-CM-02 | ユビキタス | システムは全設定フィールドにデフォルト値を持たせ、`list` 型は `field(default_factory=...)` で定義すること（未指定時に既定値で動作）。 | `src/config_manager.py:14-55,23,26,31` | — |
| R-CM-03 | イベント駆動 | `ConfigManager(config_path)` が生成されたとき、システムは当該 YAML を `yaml.safe_load` で読み、`AppConfig` を構築して保持すること。 | `src/config_manager.py:68-74` | — |
| R-CM-04 | イベント駆動 | あるセクションが設定辞書に存在しないとき、システムは空 dict を渡して当該セクションを全デフォルト値で構築すること。 | `src/config_manager.py:78-82`（`.get(section, {})`） | — |
| R-CM-05 | イベント駆動 | `get_config(name)` が呼ばれたとき、システムは `AppConfig` の属性 `name` に対応する設定オブジェクトを返すこと。 | `src/config_manager.py:85-86` | — |
| R-CM-06 | 異常系 | `config_path` のファイルが存在しないとき、システムは `FileNotFoundError` を送出すること。 | `src/config_manager.py:72`（`open`）、`src/main.py:38-40` | — |
| R-CM-07 | 異常系 | あるセクションに dataclass 未定義のキーが含まれるとき、システムは dataclass コンストラクタの `TypeError`（unexpected keyword argument）を送出すること（未知キーを無視しない）。 | `src/config_manager.py:78-82`（`**` 展開の帰結） | — |
| R-CM-08 | 異常系 | `get_config(name)` の `name` が `AppConfig` に存在しないとき、システムは `getattr` 由来の `AttributeError` を送出すること。 | `src/config_manager.py:86` | — |
| R-CM-09 | 異常系 | 設定ファイルが空で `yaml.safe_load` が `None` を返すとき、システムは `None.get` 由来の `AttributeError` を送出すること（**現状**）。**改修予定**: 空を検出して明示的なエラー（メッセージ付き）を送出する。 | `src/config_manager.py:73-74,77` | — |
| R-CM-10 | ユビキタス | システムは設定値の**型検証・値域検証を行わず**、YAML が与えた値をそのまま dataclass に格納すること（型注釈は強制されない）。 | `src/config_manager.py:76-83` | — |

## 設定キー一覧（スキーマ ↔ 消費側の対応）

> 全キーの「定義（既定値）」と「消費側 `file:line`」。**未消費キー**は ❌ で示す。

| セクション.キー | 既定値 | 消費側出典 | 状態 |
|:--|:--|:--|:--|
| camera.fps | 30 | `camera_controller.py:52`, `gui_controller.py:113`, `object_tracking_controller.py:127` | ✅ |
| camera.width | 1280 | `camera_controller.py:50` | ✅ |
| camera.height | 720 | `camera_controller.py:51` | ✅ |
| camera.max_queue_length | 10 | `gui_controller.py:63` | ✅ |
| detection.model_path | models/yolox_s.onnx | `object_tracking_controller.py:115` | ✅ |
| detection.providers | ["CPUExecutionProvider"] | `object_tracking_controller.py:115` | ✅ |
| detection.fp16 | False | — | 🗑️ **削除対象**（FP16 はモデル側で対応） |
| detection.score_threshold | 0.5 | `object_tracking_controller.py:124`（ByteTrack の `track_activation_threshold`） | ✅ ※後述 |
| detection.class_names | [] | `gui_controller.py:527,594` | ✅ |
| detection.detection_threshold（新設予定） | 0.1 | `object_tracking_controller.py:189`（現ハードコード） | 🆕 設定キー化予定 |
| detection.nms_iou_threshold（新設予定） | 0.45 | `object_tracking_controller.py:190`（現ハードコード） | 🆕 設定キー化予定 |
| tracking.class_id | [0] | `object_tracking_controller.py:192` | ✅ |
| tracking.max_lost | 30 | `object_tracking_controller.py:125` | ✅ |
| tracking.min_box_area | 100 | `object_tracking_controller.py:194` | ✅ |
| tracking.iou_threshold | 0.5 | `object_tracking_controller.py:126` | ✅ |
| tracking.max_track_num | 10 | — | 🗑️ **削除対象**（未消費） |
| tracking.frame_read_policy | bounded_latest | `object_tracking_controller.py:46` | ✅ |
| tracking.max_frame_skip | 2 | `object_tracking_controller.py:56,65` | ✅ |
| gui.window_width/height/x/y | 1600/900/100/100 | `gui_controller.py:56-57` | ✅ |
| gui.display_image_width/height | 1280/720 | `gui_controller.py:618-619` | ✅ |
| gui.frame_buffer_seconds | 2.0 | `gui_controller.py:114` | ✅ |
| logging.level | INFO | `logger.py:21` | ✅ |
| logging.output | console | `logger.py:20` | ✅ |
| logging.performance_interval | 100 | `object_tracking_controller.py:238,241` | ✅ |

## 前提条件 / 不変条件

- **デフォルトで完全動作**: すべてのフィールドにデフォルトがあるため、空セクション（または欠落セクション）でも当該設定は構築できる。全セクション欠落でも `config_dict` が `{}` なら `AppConfig` は全デフォルトで成立する。出典 `src/config_manager.py:14-55,78-82`。
- **未知キーは拒否**: `**config_dict.get(section, {})` 展開のため、未定義キーは黙殺されず `TypeError` になる（タイプミス検出に寄与）。出典 `src/config_manager.py:78-82`。
- **検証は消費側**: 値の妥当性（例: `frame_read_policy` が `fifo`/`latest`/`bounded_latest` のいずれか）は ConfigManager では検証せず、消費側が `getattr` 既定やフォールバックで吸収する。出典 `src/object_tracking_controller.py:44-65`。
- **`score_threshold` の意味**: 生検出のスコアフィルタ（ハードコード `> 0.1`、`object_tracking_controller.py:189`）ではなく、ByteTrack の `track_activation_threshold` として使われる。出典 `src/object_tracking_controller.py:124`。

## 確定事項（レビュー反映済み）

- ✅ **`detection.fp16` は削除**: FP16 推論は ONNX モデル自体を FP16 で作成して対応する方針のため、設定キーは不要。スキーマ（`config_manager.py:24`）・`default.yaml:10`・README（`README.md:97`）から除去する。削除タスクは tasks.md「コード削除」。
- ✅ **`tracking.max_track_num` は削除**: スキーマ（`config_manager.py:35`）・`default.yaml:27`・README（`README.md:104`）から除去する。ByteTrack に同時追跡上限を渡す実装は無く、用途が無い。削除タスクは tasks.md「コード削除」。
- ✅ **NMS 関連を設定キー化**: 生検出フィルタ閾値 `0.1`（`object_tracking_controller.py:189`）と NMS IoU `0.45`（`:190`）を `DetectionConfig` の設定キー **`detection.detection_threshold`** / **`detection.nms_iou_threshold`** へ昇格する（命名確定）。既存 `score_threshold`（ByteTrack 活性化）・`tracking.iou_threshold`（ByteTrack マッチング）とは別物。スキーマ追加 + 消費側差し替え + default.yaml/README 同期がセット。実装タスクは tasks.md。
- ✅ **空ファイル時は専用例外で明示的検証**: 現状は `yaml.safe_load` が `None` を返し `None.get` 由来の `AttributeError`（R-CM-09、分かりにくい）。`_load_config` で `config_dict is None` を検出し、**専用例外**（例: `EmptyConfigError`）をメッセージ付きで送出するよう改修する。実装タスクは tasks.md。

## 未確定 / 要レビュー事項

- [ ] **README 設定表の同期ずれ**: `tracking.frame_read_policy` / `tracking.max_frame_skip` / `gui.frame_buffer_seconds` が README の設定表（`README.md:89-113`）に**載っていない**。→ README を実態へ同期（タスク化済み）。
