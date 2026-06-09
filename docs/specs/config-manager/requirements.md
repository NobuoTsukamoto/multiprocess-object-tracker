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
| R-CM-01 | ユビキタス | システムは設定スキーマを5つの `@dataclass`（`CameraConfig`/`DetectionConfig`/`TrackingConfig`/`GuiConfig`/`LoggingConfig`）と、それらを束ねる `AppConfig` で定義すること。 | `src/config_manager.py:12-66` | — |
| R-CM-02 | ユビキタス | システムは全設定フィールドにデフォルト値を持たせ、`list` 型は `field(default_factory=...)` で定義すること（未指定時に既定値で動作）。 | `src/config_manager.py:15-57,25,28,33` | — |
| R-CM-03 | イベント駆動 | `ConfigManager(config_path)` が生成されたとき、システムは当該 YAML を `yaml.safe_load` で読み、`AppConfig` を構築して保持すること。 | `src/config_manager.py:73-85` | `tests/test_config_manager.py::ConfigManagerTest::test_loads_default_yaml` |
| R-CM-04 | イベント駆動 | あるセクションが設定辞書に存在しないとき、システムは空 dict を渡して当該セクションを全デフォルト値で構築すること。 | `src/config_manager.py:87-94`（`.get(section, {})`） | — |
| R-CM-05 | イベント駆動 | `get_config(name)` が呼ばれたとき、システムは `AppConfig` の属性 `name` に対応する設定オブジェクトを返すこと。 | `src/config_manager.py:96-97` | — |
| R-CM-06 | 異常系 | `config_path` のファイルが存在しないとき、システムは `FileNotFoundError` を送出すること。 | `src/config_manager.py:81`（`open`）、`src/main.py:38-40` | `tests/test_config_manager.py::ConfigManagerTest::test_missing_file_raises_file_not_found` |
| R-CM-07 | 異常系 | あるセクションに dataclass 未定義のキーが含まれるとき、システムは dataclass コンストラクタの `TypeError`（unexpected keyword argument）を送出すること（未知キーを無視しない）。 | `src/config_manager.py:87-94`（`**` 展開の帰結） | — |
| R-CM-08 | 異常系 | `get_config(name)` の `name` が `AppConfig` に存在しないとき、システムは `getattr` 由来の `AttributeError` を送出すること。 | `src/config_manager.py:97` | — |
| R-CM-09 | 異常系 | 設定ファイルが空で `yaml.safe_load` が `None` を返すとき、システムは専用例外 `EmptyConfigError`（メッセージにパスを含む）を送出すること（**実装済み**）。`main.py` は `FileNotFoundError` と同様に専用ハンドラで捕捉し stderr 出力＋`exit(1)` する。 | `src/config_manager.py:69-70,83-84`、`src/main.py:41-43` | `tests/test_config_manager.py::ConfigManagerTest::test_empty_file_raises_empty_config_error` |
| R-CM-10 | ユビキタス | システムは設定値の**型検証・値域検証を行わず**、YAML が与えた値をそのまま dataclass に格納すること（型注釈は強制されない）。 | `src/config_manager.py:87-94` | — |
| R-CM-11 | ユビキタス | システムは設定ファイルを **UTF-8** で読み込むこと（プラットフォーム既定エンコーディング、例: 日本語 Windows の cp932 に依存しない）。 | `src/config_manager.py:78-81` | — |

## 設定キー一覧（スキーマ ↔ 消費側の対応）

> 全キーの「定義（既定値）」と「消費側 `file:line`」。**未消費キー**は ❌ で示す。

| セクション.キー | 既定値 | 消費側出典 | 状態 |
|:--|:--|:--|:--|
| camera.source | 0 | `camera_controller.py:86`（`_resolve_camera_source` 経由） | ✅ |
| camera.fps | 30 | `camera_controller.py:97`, `gui_controller.py:117`, `object_tracking_controller.py:142` | ✅ |
| camera.width | 1280 | `camera_controller.py:95` | ✅ |
| camera.height | 720 | `camera_controller.py:96` | ✅ |
| camera.max_queue_length | 10 | `gui_controller.py:64` | ✅ |
| detection.model_path | models/yolox_s.onnx | `object_tracking_controller.py:129` | ✅ |
| detection.providers | ["CPUExecutionProvider"] | `object_tracking_controller.py:129` | ✅ |
| detection.fp16 | False | — | 🗑️ **削除対象**（FP16 はモデル側で対応） |
| detection.score_threshold | 0.5 | `object_tracking_controller.py:139`（ByteTrack の `track_activation_threshold`） | ✅ ※後述 |
| detection.class_names | [] | `gui_controller.py:576,647` | ✅ |
| detection.detection_threshold（新設予定） | 0.1 | `object_tracking_controller.py:204`（現ハードコード） | 🆕 設定キー化予定 |
| detection.nms_iou_threshold（新設予定） | 0.45 | `object_tracking_controller.py:205`（現ハードコード） | 🆕 設定キー化予定 |
| tracking.class_id | [0] | `object_tracking_controller.py:207` | ✅ |
| tracking.max_lost | 30 | `object_tracking_controller.py:140` | ✅ |
| tracking.min_box_area | 100 | `object_tracking_controller.py:209` | ✅ |
| tracking.iou_threshold | 0.5 | `object_tracking_controller.py:141` | ✅ |
| tracking.max_track_num | 10 | — | 🗑️ **削除対象**（未消費） |
| tracking.frame_read_policy | bounded_latest | `object_tracking_controller.py:60` | ✅ |
| tracking.max_frame_skip | 2 | `object_tracking_controller.py:70,79` | ✅ |
| gui.window_width/height/x/y | 1600/900/100/100 | `gui_controller.py:57-58` | ✅ |
| gui.display_image_width/height | 1280/720 | `gui_controller.py:667-668` | ✅ |
| gui.frame_buffer_seconds | 2.0 | `gui_controller.py:118` | ✅ |
| logging.level | INFO | `logger.py:21` | ✅ |
| logging.output | console | `logger.py:20` | ✅ |
| logging.performance_interval | 100 | `object_tracking_controller.py:253,256` | ✅ |

## 前提条件 / 不変条件

- **デフォルトで完全動作**: すべてのフィールドにデフォルトがあるため、空セクション（または欠落セクション）でも当該設定は構築できる。全セクション欠落でも `config_dict` が `{}` なら `AppConfig` は全デフォルトで成立する。**ただしファイルが完全に空（`None`）の場合は別扱い**（R-CM-09、`EmptyConfigError`）。出典 `src/config_manager.py:15-57,83-94`。
- **未知キーは拒否**: `**config_dict.get(section, {})` 展開のため、未定義キーは黙殺されず `TypeError` になる（タイプミス検出に寄与）。出典 `src/config_manager.py:87-94`。
- **検証は消費側**: 値の妥当性（例: `frame_read_policy` が `fifo`/`latest`/`bounded_latest` のいずれか）は ConfigManager では検証せず、消費側が `getattr` 既定やフォールバックで吸収する。出典 `src/object_tracking_controller.py:58-80`。
- **`score_threshold` の意味**: 生検出のスコアフィルタ（ハードコード `> 0.1`、`object_tracking_controller.py:204`）ではなく、ByteTrack の `track_activation_threshold` として使われる。出典 `src/object_tracking_controller.py:139`。
- **`camera.source` の型解釈は消費側**: `CameraConfig.source` は値を素通しで保持し（既定 `0`）、int/数字文字列/パスURL の解釈は `CameraController._resolve_camera_source` が担う（ルール B）。出典 `src/config_manager.py:14-15`、`src/camera_controller.py:51-61`、[`camera-controller`](../camera-controller/)。

## 確定事項（レビュー反映済み）

- ✅ **`detection.fp16` は削除**: FP16 推論は ONNX モデル自体を FP16 で作成して対応する方針のため、設定キーは不要。スキーマ（`config_manager.py:26`）・`default.yaml:11`・README（`README.md:98`）から除去する。削除タスクは tasks.md「コード削除」。
- ✅ **`tracking.max_track_num` は削除**: スキーマ（`config_manager.py:37`）・`default.yaml:28`・README（`README.md:105`）から除去する。ByteTrack に同時追跡上限を渡す実装は無く、用途が無い。削除タスクは tasks.md「コード削除」。
- ✅ **NMS 関連を設定キー化**: 生検出フィルタ閾値 `0.1`（`object_tracking_controller.py:204`）と NMS IoU `0.45`（`:205`）を `DetectionConfig` の設定キー **`detection.detection_threshold`** / **`detection.nms_iou_threshold`** へ昇格する（命名確定）。既存 `score_threshold`（ByteTrack 活性化）・`tracking.iou_threshold`（ByteTrack マッチング）とは別物。スキーマ追加 + 消費側差し替え + default.yaml/README 同期がセット。実装タスクは tasks.md。
- ✅ **`camera.source` を追加（実装済み）**: `CameraConfig` に `source: Union[int, str] = 0` を追加（`config_manager.py:14-15`）。`default.yaml`・README 設定表も同期済み。型解釈（ルール B）は消費側 `CameraController._resolve_camera_source` が担う（camera-controller R-CAM-13a〜d）。
- ✅ **空ファイル時は専用例外で明示的検証（実装済み）**: `_load_config` で `config_dict is None` を検出し、**専用例外 `EmptyConfigError`**（`ValueError` サブクラス、メッセージにパスを含む）を送出する（R-CM-09、`config_manager.py:69-70,83-84`）。`main.py` は `FileNotFoundError` と同様の専用ハンドラで捕捉し stderr 出力＋`exit(1)`（`main.py:41-43`）。
- ✅ **設定ファイルは UTF-8 で読む（実装済み）**: `open(..., encoding="utf-8")` で読み込み、日本語 Windows（cp932）等のプラットフォーム既定エンコーディングに依存しない（R-CM-11、`config_manager.py:78-81`）。`default.yaml` の非 ASCII コメント等が原因の `UnicodeDecodeError` を防ぐ。

## 未確定 / 要レビュー事項

- [ ] **README 設定表の同期ずれ**: `tracking.frame_read_policy` / `tracking.max_frame_skip` / `gui.frame_buffer_seconds` が README の設定表（`README.md:90-114`）に**載っていない**（`camera.source` は本変更で追記済み）。→ README を実態へ同期（タスク化済み）。
