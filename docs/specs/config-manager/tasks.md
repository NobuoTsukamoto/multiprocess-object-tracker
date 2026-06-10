# Tasks — config-manager

> 逆生成 spec。`src/config_manager.py` のテストカバレッジ状況と、未文書化挙動・テスト不足・将来改善を列挙する。

## テストカバレッジ状況（逆生成時）

[`tests/test_config_manager.py`](../../../tests/test_config_manager.py) が正常系（R-CM-03/04/05）と異常系（R-CM-06〜09/11/12）をカバーする。

| 要求 ID | 対応テスト | 状態 |
|:--|:--|:--|
| R-CM-01（スキーマ定義） | — | ⬜ 未カバー |
| R-CM-02（デフォルト完備） | `ConfigManagerTest::test_missing_sections_built_with_defaults`（間接） | 🟡 部分 |
| R-CM-03（YAML 読込→AppConfig） | `ConfigManagerTest::test_loads_default_yaml` | 🟡 部分（default.yaml 読込のみ） |
| R-CM-04（欠落セクション→デフォルト） | `ConfigManagerTest::test_missing_sections_built_with_defaults` | ✅ カバー済み |
| R-CM-05（get_config 取得） | `ConfigManagerTest::test_get_config_returns_section_dataclass` | ✅ カバー済み |
| R-CM-06（ファイル無し→FileNotFoundError） | `ConfigManagerTest::test_missing_file_raises_file_not_found` | ✅ カバー済み |
| R-CM-07（未知キー→TypeError） | `ConfigManagerTest::test_unknown_key_raises_type_error`、`::test_removed_keys_are_rejected` | ✅ カバー済み |
| R-CM-08（不明セクション→AttributeError） | `ConfigManagerTest::test_unknown_section_name_raises_attribute_error` | ✅ カバー済み |
| R-CM-09（空ファイル→EmptyConfigError） | `ConfigManagerTest::test_empty_file_raises_empty_config_error` | ✅ カバー済み（実装済み） |
| R-CM-10（無検証で格納） | — | ⬜ 未カバー |
| R-CM-11（UTF-8 読み込み） | `ConfigManagerTest::test_non_utf8_file_raises_unicode_decode_error` | ✅ カバー済み（実装済み） |
| R-CM-12（未消費キーを持たない） | `ConfigManagerTest::test_removed_keys_are_rejected` | ✅ カバー済み（実装済み） |

## タスク

### 文書化 / 整合
- [x] **README 設定表を実態に同期**: `tracking.frame_read_policy` / `tracking.max_frame_skip` / `gui.frame_buffer_seconds` を追加し、`logging.output` の「console固定」記述をファイルパス指定可に修正（logger spec R-LOG-03 と整合）。
- [x] steering（`structure.md`）の「設定キー追加時は config_manager・default.yaml・README を同期」記述と本 spec をリンク。
- [x] `score_threshold` の実際の用途（ByteTrack 活性化閾値であり生検出フィルタではない）を README 設定表に注記済み。

### テスト
- [x] `tests/test_config_manager.py` を新設。空ファイル→`EmptyConfigError`（R-CM-09）、ファイル無し→`FileNotFoundError`（R-CM-06）、default.yaml 正常読込（R-CM-03）をカバー。
- [x] 残りのケースを追加。
  - [x] 欠落セクションが全デフォルトで構築されること（R-CM-04、`test_missing_sections_built_with_defaults`）。
  - [x] `get_config(section)` が対応 dataclass を返すこと（R-CM-05、`test_get_config_returns_section_dataclass`）。
  - [x] 未知キーで `TypeError`（R-CM-07、`test_unknown_key_raises_type_error`）。
  - [x] 不明セクションで `AttributeError`（R-CM-08、`test_unknown_section_name_raises_attribute_error`）。
  - [x] 非 UTF-8 バイト列で `UnicodeDecodeError`（R-CM-11、`test_non_utf8_file_raises_unicode_decode_error`）。

### コード削除（✅完了: fp16 と max_track_num を削除、R-CM-12）
- [x] `src/config_manager.py` の `fp16` を削除（FP16 はモデル側で対応）。
- [x] `config/default.yaml` の `fp16` 行を削除。
- [x] `README.md` の `fp16` 行を削除。
- [x] `src/config_manager.py` の `max_track_num` を削除。
- [x] `config/default.yaml` の `max_track_num` 行を削除。
- [x] `README.md` の `max_track_num` 行を削除。
- [x] 回帰テスト `ConfigManagerTest::test_removed_keys_are_rejected` を追加（削除キー指定で `TypeError`、R-CM-07/12）。

### 実装（✅完了）
- [x] **`camera.source` の追加**（camera-controller R-CAM-13、**実装済み**）: `CameraConfig` に `source: Union[int, str] = 0` を追加（`config_manager.py:14-15`）。`default.yaml`・README 設定表も同期。型解釈は消費側 `CameraController._resolve_camera_source`。
- [x] **NMS 関連の設定キー化**（**実装済み**）: `DetectionConfig` に `detection_threshold`（既定 0.1、`config_manager.py:27`）・`nms_iou_threshold`（既定 0.45、`:28`）を追加し、`object_tracking_controller.py:205,208` のハードコードを差し替え。`default.yaml`・README 設定表も同期。`ConfigManagerTest::test_detection_threshold_keys_have_defaults` 追加。
- [x] **空ファイル時の専用例外**（R-CM-09、**実装済み**）: `_load_config`（`config_manager.py:77-85`）で `config_dict is None` を検出し `EmptyConfigError`（`ValueError` 派生、`:69-70`）をパス付きで送出。`main.py:41-43` に専用ハンドラ追加。`ConfigManagerTest::test_empty_file_raises_empty_config_error` 追加。
- [x] **設定ファイルの UTF-8 読み込み**（R-CM-11、**実装済み**）: `open(encoding="utf-8")`（`config_manager.py:78-81`）。default.yaml の非 ASCII コメント（`camera.source`）による cp932 `UnicodeDecodeError` を修正。

### 実装 / 改善（将来）
- [ ] 値域・型の軽量バリデーション（例: `frame_read_policy` の enum 化、`level` の許容値チェック）を ConfigManager 側に持たせるか検討。
- [ ] `AppConfig` 等を `frozen=True` 化して不変性を担保するか検討。

## メモ / 申し送り

- ✅ `camera.source`（`Union[int, str]`、既定 0）を追加（**実装済み**、camera-controller R-CAM-13）。型解釈はルール B で消費側委譲。
- ✅ `detection.detection_threshold`（0.1）/ `detection.nms_iou_threshold`（0.45）を追加（**実装済み**）。`object_tracking_controller` の生検出フィルタ/NMS のハードコードを設定値へ差し替え。
- ✅ `detection.fp16`（FP16 はモデル側で対応）と `tracking.max_track_num` は共に **削除** で確定（**実装済み**、R-CM-12）。旧設定ファイルにこれらのキーが残っている場合は R-CM-07 により `TypeError` で起動失敗する（黙殺しない）。
- ✅ NMS 関連ハードコード（`0.1` / `0.45`）は **設定キー化** で確定（`detection_threshold` / `nms_iou_threshold`、命名確定）。
- ✅ 空ファイル時は **専用例外 `EmptyConfigError`** で明示的検証（R-CM-09、**実装済み**）。`main.py` に専用ハンドラ追加。
- ✅ 設定ファイルは **UTF-8 固定**で読み込む（R-CM-11、**実装済み**）。非 ASCII コメント起因の cp932 `UnicodeDecodeError` を修正。
- 🆕 **整合**: README 設定表が default.yaml/コードと不一致（frame_read_policy/max_frame_skip/frame_buffer_seconds 欠落）。
- 🔎 **検証の非対称性**: 「未知キー＝厳格（TypeError）」だが「不正値＝無検証」。値の妥当性は消費側依存。
- 🔎 `score_threshold` は生検出フィルタではなく ByteTrack の活性化閾値。生フィルタ閾値 `0.1` は別途ハードコード。
- ✅ 正常系（R-CM-03/04/05）と異常系（R-CM-06〜09/11/12）の最小スイートを整備済み（`tests/test_config_manager.py`、10 テスト）。残りはスキーマ定義そのもの（R-CM-01）と無検証格納（R-CM-10）のみ。
