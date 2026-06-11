# Tasks — logger

> 逆生成 spec。`src/logger.py` のテストカバレッジ状況と、未文書化挙動・テスト不足・将来改善を列挙する。

## テストカバレッジ状況（逆生成時）

[`tests/test_logger.py`](../../../tests/test_logger.py) がシンク選択（モック）と実 loguru 経路（ファイル出力・冪等性・不正レベル）をカバーする（10 テスト）。

| 要求 ID | 対応テスト | 状態 |
|:--|:--|:--|
| R-LOG-01（生成→再構成） | `SinkSelectionTest::test_handlers_are_reset_before_adding` | ✅ カバー済み |
| R-LOG-02（console→stdout） | `SinkSelectionTest::test_console_output_uses_stdout_sink` | ✅ カバー済み |
| R-LOG-03（その他→ファイルシンク） | `SinkSelectionTest::test_non_console_output_is_used_as_sink_path`、`RealLoguruTest::test_file_sink_writes_log_lines` | ✅ カバー済み |
| R-LOG-04（level.upper） | `SinkSelectionTest::test_level_is_uppercased` | ✅ カバー済み |
| R-LOG-05（統一フォーマット） | — | ⬜ 未カバー |
| R-LOG-06（PERFORMANCE 登録） | `SinkSelectionTest::test_performance_level_is_registered` | ✅ カバー済み |
| R-LOG-07（再登録 ValueError 無視） | `RealLoguruTest::test_repeated_construction_is_idempotent` | ✅ カバー済み |
| R-LOG-08（get_logger） | `RealLoguruTest::test_get_logger_returns_global_loguru_logger` | ✅ カバー済み |
| R-LOG-09（不正レベル→明示エラー） | `RealLoguruTest::test_invalid_level_raises_explicit_value_error`、`::test_performance_is_accepted_as_level` | ✅ カバー済み（実装済み） |
| R-LOG-10（再構成を維持・ガード無し） | `SinkSelectionTest::test_handlers_are_reset_before_adding` | ✅ カバー済み（docstring 明記済み） |

## タスク

### 文書化 / 整合
- [x] **README の output 記述を実態へ同期**: 「console固定」→「console=標準出力。それ以外の文字列はファイルパスとして出力」に修正（ファイル出力を公式機能として記載、R-LOG-03）。
- [ ] `PERFORMANCE`（`no=38`）の重大度（WARNING〜ERROR の間、INFO/DEBUG で可視）を README ロギング節（`README.md:72-82`）に明記。
- [ ] 「1プロセス1 Logger」前提（グローバル singleton 再構成）を design に基づき README/steering へ補足。

### テスト
- [x] `tests/test_logger.py` を新設（`SinkSelectionTest` はモック、`RealLoguruTest` は実 loguru）。
  - [x] `output="console"` で stdout シンクになること（R-LOG-02）。
  - [x] `output=<path>` でファイルシンクが作られること（R-LOG-03。モック＋実ファイル書き込みの2系統）。
  - [x] `level` が小文字でも `upper()` で適用されること（R-LOG-04）。
  - [x] `PERFORMANCE` レベルが登録され、二重生成でも例外が漏れないこと（R-LOG-06/07）。
  - [x] `get_logger()` がグローバル logger を返すこと（R-LOG-08）。
  - [x] 不正レベルで明示 `ValueError`、`level: PERFORMANCE` は妥当（R-LOG-09）。

### 実装（✅完了）
- [x] **不正レベルの検証追加**（R-LOG-09）: `config.level.upper()` を `logger.level(name)` で照会し、不正なら明示メッセージ付き `ValueError` を送出（`src/logger.py:33-40`）。`PERFORMANCE` 登録を検証より前へ移動し `level: PERFORMANCE` も妥当に。ConfigManager 側のレベル検証は引き続き検討（[`config-manager`](../config-manager/) tasks）。
- [x] **再構成維持を明文化**（R-LOG-10）: 「構成済みスキップ」型ガードを入れないこと、毎回 `remove()`→`add()` する理由（fork/spawn 両対応）を `_configure_logger` の docstring に記載（`src/logger.py:18-25`）。

### 実装 / 改善（将来）
- [ ] 戻り値型注釈（`get_logger() -> "loguru.Logger"`）など型情報の付与。
- [ ] ファイル出力時のローテーション/保持期間（`loguru` の `rotation`/`retention`）を設定可能にするか検討（ファイル出力を公式化したため有力）。
- [ ] 共有ファイルへ複数プロセスから書く構成にする場合、`enqueue=True`（プロセス安全な書き込み）を検討。

## メモ / 申し送り

- ✅ ファイル出力は **公式機能**として正式化（README を実態へ更新）。
- ✅ 不正レベルは **検証を追加**（明示エラー、R-LOG-09、**実装済み**）。`PERFORMANCE` 登録が検証より先のため `level: PERFORMANCE` も指定可。
- ✅ 多重生成ガードは **入れない**（再構成を維持、R-LOG-10）。「構成済みスキップ」型は fork でフラグ継承により再構成を飛ばし危険。`remove()`→`add()` は蓄積しないため現状で頑健。
- 🔎 `PERFORMANCE=38` は WARNING(30)とERROR(40)の間。`level=ERROR` だと PERFORMANCE ログは出ない点に注意。
- 🔎 カスタムレベル再登録の `ValueError` は意図的に握りつぶし（冪等化）。
- ✅ テスト整備済み（10 テスト）。未カバーは統一フォーマット（R-LOG-05）のみ（フォーマット文字列の検証価値が低いため保留）。
