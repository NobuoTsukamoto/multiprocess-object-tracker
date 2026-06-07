# Tasks — camera-controller

> 逆生成 spec。`src/camera_controller.py` のテストカバレッジ状況と、未文書化挙動・テスト不足・将来改善を列挙する。

## テストカバレッジ状況（逆生成時）

`camera_controller` 専用テストは**存在しない**（`tests/test_camera_controller.py` 無し）。全要求が未カバー。実カメラ依存のため単体テストには `cv2.VideoCapture` のモック化が要る。

| 要求 ID | 対応テスト | 状態 |
|:--|:--|:--|
| R-CAM-01（Process サブクラス） | — | ⬜ 未カバー |
| R-CAM-02（init 状態） | — | ⬜ 未カバー |
| R-CAM-03（子プロセスでアタッチ） | — | ⬜ 未カバー |
| R-CAM-04（open 失敗→終了） | — | ⬜ 未カバー |
| R-CAM-05（解像度/FPS 要求） | — | ⬜ 未カバー |
| R-CAM-06（stop まで反復） | — | ⬜ 未カバー |
| R-CAM-07（grab 失敗→warning+sleep） | — | ⬜ 未カバー |
| R-CAM-08（shape 不一致→resize） | — | ⬜ 未カバー |
| R-CAM-09（両プール書き込み） | — | ⬜ 未カバー |
| R-CAM-10（ドロップ→warning） | — | ⬜ 未カバー |
| R-CAM-11（frame_id 単調増加） | — | ⬜ 未カバー |
| R-CAM-12（finally 後始末） | — | ⬜ 未カバー |
| R-CAM-13a〜d（source 型解釈・ルールB） | — | ⬜ 未カバー（改修予定） |
| R-CAM-14（open 失敗→GUI 通知） | — | ⬜ 未カバー（改修予定） |
| R-CAM-15（チャンネル不一致→error+drop） | — | ⬜ 未カバー（改修予定） |

## タスク

### 文書化 / 整合
- [ ] ✅確定: 「Resize/pad」コメント（`camera_controller.py:62`）を実装（resize のみ）に合わせて修正。
- [ ] 解像度/FPS は「要求のみ（非保証）」である点を README へ補足。
- [ ] `camera.source`（int/文字列対応）を README 設定表・`config/default.yaml`・config-manager spec に追記。

### テスト
- [ ] `tests/test_camera_controller.py` を新設（`cv2.VideoCapture` をモック）。
  - [ ] open 失敗時に error ログ＋プール close＋早期 return（R-CAM-04）。
  - [ ] grab 失敗（ret=False）で warning＋sleep＋継続（R-CAM-07）。
  - [ ] shape 不一致で resize が呼ばれること（R-CAM-08）。
  - [ ] 取得フレームが両プールへ write されること（R-CAM-09）。
  - [ ] write が False のとき該当プール名で warning（R-CAM-10）。
  - [ ] `frame_id` が反復ごとに +1（R-CAM-11）。
  - [ ] `stop_event` セットでループ脱出＋release/close（R-CAM-06/12）。

### 実装（✅確定）
- [ ] **カメラソースの設定キー化**（R-CAM-13a〜d、ルールB確定）: `CameraConfig` に `source`（既定 `0`、int or str）を追加。解釈ヘルパを実装（int→そのまま / `^\d+$` 文字列→`int()` / それ以外の文字列→そのまま）し `cv2.VideoCapture(resolved)` へ。`config/default.yaml`・README・config-manager spec も同期。
- [ ] **オープン失敗の GUI 通知**（R-CAM-14、機構確定）: [`gui-controller`](../gui-controller/) R-GUI-44 と**共通の専用通知**で GUI に通知（**ステータス Queue 推奨**、tracking R-OTC-23 と共通）。コンストラクタ引数の追加と GUI 側のハンドリング（専用エラー表示）を併せて実装。最終形は実装時に 3 モジュール横断で確定。
- [ ] **チャンネル不一致の error ドロップ**（R-CAM-15）: resize 後に `frame.shape != expected_shape` を明示チェックし、error ログ＋`continue`（書き込みスキップ）。
- [ ] grab 連続失敗は無限リトライのまま（R-CAM-07、変更不要）。

### 実装 / 改善（将来）
- [ ] 型注釈の補強（`run()` 内ローカルや戻り値）。
- [ ] フレーム書き込み失敗率（ドロップ率）のメトリクス化（performance ログ連携）。

## メモ / 申し送り

- ✅ カメラソースは `camera.source`（キー名確定）で設定キー化。型解釈は**ルールB**（int / 数字文字列→int / それ以外→パスURL）で確定（R-CAM-13a〜d）。
- ✅ open 失敗は GUI へ専用エラー通知（R-CAM-14、gui R-GUI-44 と共通・ステータス Queue 推奨、最終形は実装時確定）。
- ✅ grab 連続失敗は無限リトライのまま（R-CAM-07、仕様確定）。
- ✅ チャンネル不一致は error ログ＋ドロップ（R-CAM-15）。
- 🔎 両プールは GUI が同一 `frame_shape` で生成するため、`tracking_pool.shape` 基準のリサイズで GUI 用にも適合する（前提が崩れると GUI 用がドロップする）。
- 🔎 `frame_id` はプロセス生存中のみ単調増加。停止・再開で 0 にリセット（GUI の frame_id 突合に影響＝gui-controller spec で扱う）。
- 🔎 FPS ペーシングは `cap.read()` 依存（追加 sleep 無し）。
- 専用テストが皆無。`cv2.VideoCapture` モックで open 失敗（R-CAM-04）と書き込み経路（R-CAM-09/10）を優先整備するのが有効。
