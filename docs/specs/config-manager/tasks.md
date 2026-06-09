# Tasks — config-manager

> 逆生成 spec。`src/config_manager.py` のテストカバレッジ状況と、未文書化挙動・テスト不足・将来改善を列挙する。

## テストカバレッジ状況（逆生成時）

`config_manager` 専用テストは**存在しない**（`tests/test_config_manager.py` 無し）。全要求が未カバー。

| 要求 ID | 対応テスト | 状態 |
|:--|:--|:--|
| R-CM-01（スキーマ定義） | — | ⬜ 未カバー |
| R-CM-02（デフォルト完備） | — | ⬜ 未カバー |
| R-CM-03（YAML 読込→AppConfig） | — | ⬜ 未カバー |
| R-CM-04（欠落セクション→デフォルト） | — | ⬜ 未カバー |
| R-CM-05（get_config 取得） | — | ⬜ 未カバー |
| R-CM-06（ファイル無し→FileNotFoundError） | — | ⬜ 未カバー |
| R-CM-07（未知キー→TypeError） | — | ⬜ 未カバー |
| R-CM-08（不明セクション→AttributeError） | — | ⬜ 未カバー |
| R-CM-09（空ファイル→AttributeError） | — | ⬜ 未カバー |
| R-CM-10（無検証で格納） | — | ⬜ 未カバー |

## タスク

### 文書化 / 整合
- [ ] **README 設定表を実態に同期**（`README.md:90-114`）: 欠落している `tracking.frame_read_policy` / `tracking.max_frame_skip` / `gui.frame_buffer_seconds` を追加（`camera.source` は追記済み）。
- [ ] steering（`structure.md:48-49`）の「設定キー追加時は config_manager・default.yaml・README を同期」記述と本 spec をリンク。
- [ ] `score_threshold` の実際の用途（ByteTrack 活性化閾値であり生検出フィルタではない）を README/設定表に注記。

### テスト
- [ ] `tests/test_config_manager.py` を新設。
  - [ ] 欠落セクションが全デフォルトで構築されること（R-CM-04）。
  - [ ] `get_config(section)` が対応 dataclass を返すこと（R-CM-05）。
  - [ ] ファイル無しで `FileNotFoundError`（R-CM-06）。
  - [ ] 未知キーで `TypeError`（R-CM-07）。
  - [ ] 不明セクションで `AttributeError`（R-CM-08）。
  - [ ] 空ファイルで明示的エラー（R-CM-09、改修後の挙動）。

### コード削除（✅確定: fp16 と max_track_num を削除）
- [ ] `src/config_manager.py:26` の `fp16` を削除（FP16 はモデル側で対応）。
- [ ] `config/default.yaml:11` の `fp16` 行を削除。
- [ ] `README.md:98` の `fp16` 行を削除。
- [ ] `src/config_manager.py:37` の `max_track_num` を削除。
- [ ] `config/default.yaml:28` の `max_track_num` 行を削除。
- [ ] `README.md:105` の `max_track_num` 行を削除。

### 実装（✅確定）
- [x] **`camera.source` の追加**（camera-controller R-CAM-13、**実装済み**）: `CameraConfig` に `source: Union[int, str] = 0` を追加（`config_manager.py:14-15`）。`default.yaml`・README 設定表も同期。型解釈は消費側 `CameraController._resolve_camera_source`。
- [ ] **NMS 関連の設定キー化**: `DetectionConfig` に `detection_threshold`（既定 0.1）・`nms_iou_threshold`（既定 0.45）を追加し、`object_tracking_controller.py:204-205` のハードコードを差し替え。`default.yaml`・README 設定表も同期。（命名確定）
- [ ] **空ファイル時の専用例外**: `_load_config`（`src/config_manager.py:73-76`）で `config_dict is None` を検出し、専用例外 `EmptyConfigError`（仮称）をメッセージ付きで送出。`main.py` のハンドリングも併せて確認。テスト R-CM-09 を改修後の挙動へ更新。

### 実装 / 改善（将来）
- [ ] 値域・型の軽量バリデーション（例: `frame_read_policy` の enum 化、`level` の許容値チェック）を ConfigManager 側に持たせるか検討。
- [ ] `AppConfig` 等を `frozen=True` 化して不変性を担保するか検討。

## メモ / 申し送り

- ✅ `camera.source`（`Union[int, str]`、既定 0）を追加（**実装済み**、camera-controller R-CAM-13）。型解釈はルール B で消費側委譲。
- ✅ `detection.fp16`（FP16 はモデル側で対応）と `tracking.max_track_num` は共に **削除** で確定。
- ✅ NMS 関連ハードコード（`0.1` / `0.45`）は **設定キー化** で確定（`detection_threshold` / `nms_iou_threshold`、命名確定）。
- ✅ 空ファイル時は **専用例外**（`EmptyConfigError` 仮称）で明示的検証へ改修で確定。
- 🆕 **整合**: README 設定表が default.yaml/コードと不一致（frame_read_policy/max_frame_skip/frame_buffer_seconds 欠落）。
- 🔎 **検証の非対称性**: 「未知キー＝厳格（TypeError）」だが「不正値＝無検証」。値の妥当性は消費側依存。
- 🔎 `score_threshold` は生検出フィルタではなく ByteTrack の活性化閾値。生フィルタ閾値 `0.1` は別途ハードコード。
- 専用テストが皆無のため、まず正常系（R-CM-04/05）と異常系（R-CM-06〜09）の最小スイートを整備するのが優先。
