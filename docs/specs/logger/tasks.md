# Tasks — logger

> 逆生成 spec。`src/logger.py` のテストカバレッジ状況と、未文書化挙動・テスト不足・将来改善を列挙する。

## テストカバレッジ状況（逆生成時）

`logger` 専用テストは**存在しない**（`tests/test_logger.py` 無し）。全要求が未カバー。

| 要求 ID | 対応テスト | 状態 |
|:--|:--|:--|
| R-LOG-01（生成→再構成） | — | ⬜ 未カバー |
| R-LOG-02（console→stdout） | — | ⬜ 未カバー |
| R-LOG-03（その他→ファイルシンク） | — | ⬜ 未カバー |
| R-LOG-04（level.upper） | — | ⬜ 未カバー |
| R-LOG-05（統一フォーマット） | — | ⬜ 未カバー |
| R-LOG-06（PERFORMANCE 登録） | — | ⬜ 未カバー |
| R-LOG-07（再登録 ValueError 無視） | — | ⬜ 未カバー |
| R-LOG-08（get_logger） | — | ⬜ 未カバー |
| R-LOG-09（不正レベル→明示エラー） | — | ⬜ 未カバー（改修予定） |
| R-LOG-10（再構成を維持・ガード無し） | — | ⬜ 未カバー |

## タスク

### 文書化 / 整合
- [ ] **README の output 記述を実態へ同期**（`README.md:112`）: 「console固定」→ console もしくは任意のファイルパスを指定可、と修正（またはコードを console 固定に寄せる方針なら別途判断）。
- [ ] `PERFORMANCE`（`no=38`）の重大度（WARNING〜ERROR の間、INFO/DEBUG で可視）を README ロギング節（`README.md:72-82`）に明記。
- [ ] 「1プロセス1 Logger」前提（グローバル singleton 再構成）を design に基づき README/steering へ補足。

### テスト
- [ ] `tests/test_logger.py` を新設。
  - [ ] `output="console"` で stdout シンクになること（R-LOG-02）。
  - [ ] `output=<path>` でファイルシンクが作られること（R-LOG-03）。
  - [ ] `level` が小文字でも `upper()` で適用されること（R-LOG-04）。
  - [ ] `PERFORMANCE` レベルが登録され、二重生成でも例外が漏れないこと（R-LOG-06/07）。
  - [ ] `get_logger()` がグローバル logger を返すこと（R-LOG-08）。

### 実装（✅確定）
- [ ] **不正レベルの検証追加**（R-LOG-09）: `config.level.upper()` が `loguru` 既知レベルかを検証し、不正なら明示メッセージ付きエラーを送出（`src/logger.py:21` 前後）。config-manager 側のレベル検証（[`config-manager`](../config-manager/) tasks）と整合。テスト追加。
- [ ] **再構成維持を明文化**（R-LOG-10）: 「構成済みスキップ」型ガードを入れないこと、毎回 `remove()`→`add()` する理由（fork/spawn 両対応）を `_configure_logger` の docstring に記載。

### 実装 / 改善（将来）
- [ ] 戻り値型注釈（`get_logger() -> "loguru.Logger"`）など型情報の付与。
- [ ] ファイル出力時のローテーション/保持期間（`loguru` の `rotation`/`retention`）を設定可能にするか検討（ファイル出力を公式化したため有力）。
- [ ] 共有ファイルへ複数プロセスから書く構成にする場合、`enqueue=True`（プロセス安全な書き込み）を検討。

## メモ / 申し送り

- ✅ ファイル出力は **公式機能**として正式化（README を実態へ更新）。
- ✅ 不正レベルは **検証を追加**（明示エラー、R-LOG-09）。
- ✅ 多重生成ガードは **入れない**（再構成を維持、R-LOG-10）。「構成済みスキップ」型は fork でフラグ継承により再構成を飛ばし危険。`remove()`→`add()` は蓄積しないため現状で頑健。
- 🔎 `PERFORMANCE=38` は WARNING(30)とERROR(40)の間。`level=ERROR` だと PERFORMANCE ログは出ない点に注意。
- 🔎 カスタムレベル再登録の `ValueError` は意図的に握りつぶし（冪等化）。
- 専用テストが皆無。シンク選択（R-LOG-02/03）とカスタムレベル冪等性（R-LOG-06/07）を優先して整備するのが有効。
