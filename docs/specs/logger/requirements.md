# Requirements — logger

> 逆生成 spec。出典は [`src/logger.py`](../../../src/logger.py)。コードが正。
> 記法は [`../../steering/conventions.md`](../../steering/conventions.md) の EARS 節に従う。
> **各要求に出典 `file:line` を付与済み。人手レビューで突き合わせること。**

## 対象 / スコープ

- **対象モジュール/機能**: [`src/logger.py`](../../../src/logger.py)（`loguru` をラップし、全プロセスのログ出力・フォーマット・カスタムレベルを一元設定する）。
- **スコープ内**: `Logger` クラスの初期化・`loguru` グローバルロガーの再構成（`_configure_logger`）・シンク選択（console / その他）・レベル設定・統一フォーマット・カスタムレベル `PERFORMANCE` 登録・`get_logger` 提供。
- **スコープ外**:
  - 各コントローラでの**ログ呼び出し内容**（何を info/warning/error で出すか）。`PERFORMANCE` ログの中身は [`object_tracking_controller.py:245-253`](../../../src/object_tracking_controller.py) が決める。
  - `LoggingConfig` のスキーマ定義（[`config-manager`](../config-manager/) を参照）。

## 用語集

| 用語 | 定義 |
|:--|:--|
| シンク（sink） | `loguru` の出力先。`sys.stdout` やファイルパス文字列を指定できる |
| グローバルロガー | `from loguru import logger` で得られるプロセス共有の singleton |
| `PERFORMANCE` | 本モジュールが追加するカスタムレベル（重大度 `no=38`） |
| 統一フォーマット | `time | level | name:function:line - message` のログ整形文字列 |

## 要求一覧（EARS）

各要求は一意 ID・EARS 文・出典・対応テストを記す。ID 接頭辞は `R-LOG`。専用テストは**存在しない**（`tests/test_logger.py` 無し）。

| ID | 種別 | 要求（EARS） | 出典 | 対応テスト |
|:--|:--|:--|:--|:--|
| R-LOG-01 | イベント駆動 | `Logger(config)` が生成されたとき、システムは `LoggingConfig` を保持し、グローバルロガーを再構成すること（既存ハンドラを全削除してから新規シンクを追加）。 | `src/logger.py:13-23`（`logger.remove()`→`logger.add()`） | — |
| R-LOG-02 | イベント駆動 | `output` が `"console"` のとき、システムは `sys.stdout` をシンクにすること。 | `src/logger.py:20` | — |
| R-LOG-03 | イベント駆動 | `output` が `"console"` 以外のとき、システムはその値をシンク（ファイルパス等）として使うこと。 | `src/logger.py:20` | — |
| R-LOG-04 | ユビキタス | システムはログレベルを `config.level.upper()`（大文字化）で設定すること。 | `src/logger.py:21` | — |
| R-LOG-05 | ユビキタス | システムは統一フォーマット（`{time} | {level} | {name}:{function}:{line} - {message}`、色付き）を適用すること。 | `src/logger.py:22` | — |
| R-LOG-06 | ユビキタス | システムはカスタムレベル `PERFORMANCE`（`no=38`、色 `<yellow>`、アイコン 🚀）を登録すること。 | `src/logger.py:27` | — |
| R-LOG-07 | 異常系 | `PERFORMANCE` が既に登録済みで `logger.level(...)` が `ValueError` を送出したとき、システムはそれを無視して継続すること（再登録に冪等）。 | `src/logger.py:26-30` | — |
| R-LOG-08 | イベント駆動 | `get_logger()` が呼ばれたとき、システムは設定済みのグローバル `logger` を返すこと。 | `src/logger.py:32-33` | — |
| R-LOG-09 | 異常系 | `config.level` が許容ログレベルでないとき、システムは明示的なメッセージ付きエラーを送出すること（**改修予定**。現状は `logger.add` 由来の `ValueError`）。 | `src/logger.py:21` | — |
| R-LOG-10 | ユビキタス | システムはプロセスごとに必ずロガーを再構成し、「構成済みならスキップ」する状態を持たないこと（fork/spawn 両対応のため）。 | `src/logger.py:17-23` | — |

## 前提条件 / 不変条件

- **グローバル singleton の再構成**: `loguru.logger` はプロセス共有の singleton。`Logger.__init__` はそれを `remove()`→`add()` で**再構成**する。したがって同一プロセスで複数 `Logger` を生成すると、後の生成が前のハンドラを消して**後勝ち**になる。出典 `src/logger.py:18-23`。
- **プロセスごとの生成（fork/spawn 両対応）**: 各ワーカーは子プロセス内（`run()`）で自前の `Logger` を生成する。`set_start_method` 未指定のため起動方式はプラットフォーム既定（Windows/macOS=spawn、Linux=fork）。
  - **spawn**: 子は再 import で `loguru` がまっさら → 子での再構成が必須。
  - **fork**: 子は親の構成済み `loguru`（親のハンドラ）を継承 → 子の `remove()`→`add()` で継承状態をリセットでき安全。
  - したがって「毎回再構成」は両方式で正しい。出典 `src/camera_controller.py:79`、`src/object_tracking_controller.py:125`、`src/main.py:32`、`src/gui_controller.py:49`。
- **再構成は冪等（蓄積しない）**: `remove()`（全削除）→`add()`（1個）のため、同一プロセスで複数生成してもハンドラは常に1個。重複ログは起きない。出典 `src/logger.py:18-19`。
- **`PERFORMANCE` の重大度**: `no=38` は `WARNING(30)` と `ERROR(40)` の間。レベル `INFO(20)`/`DEBUG(10)` 設定時は表示され、`ERROR(40)` 設定時は抑制される。出典 `src/logger.py:27`。
- **`PERFORMANCE` の発火**: 実際の出力は消費側が `logger.log("PERFORMANCE", ...)` で行う（`performance_interval` フレームごと）。出典 `src/object_tracking_controller.py:253,260-268`。
- **`get_logger` は同一 singleton を返す**: インスタンス固有のロガーではなく、プロセスのグローバル `logger` を返す。出典 `src/logger.py:32-33`。

## 確定事項（レビュー反映済み）

- ✅ **ファイル出力を公式機能として残す**: `output` に `"console"` 以外（ファイルパス）を指定するとファイルへ出力する挙動（`logger.py:20`）を正式仕様とする。README の「console固定」（`README.md:112`）を「console もしくは任意のファイルパス」へ更新する。同期タスクは tasks.md。
- ✅ **不正レベルの検証を追加**: `config.level` が `loguru` の既知レベルでない場合、現状は `logger.add(level=...)` が不親切な `ValueError`（未ハンドル）。許容レベルを検証し、明示的なメッセージ付きエラーを送出する。検証は config-manager 側のバリデーションとも整合させる（[`config-manager`](../config-manager/) tasks 参照）。実装タスクは tasks.md。
- ✅ **多重生成ガードは入れない（再構成を維持）**: `_configure_logger` は `remove()`→`add()` で常にハンドラ1個へ再構成するため、同一プロセスで複数生成してもハンドラは蓄積せず害がない。「構成済みならスキップ」型ガードは **Linux fork で子が構成済みフラグを継承して再構成をスキップし、親から継承した fork 非安全なハンドラのまま動く**ため逆に危険。よって**毎回再構成する現状を維持**し、設計意図を明記する。出典 `src/logger.py:18-23`。
- ✅ **`get_logger` はプロセスグローバルを返す（仕様）**: 「1プロセス1ロガー、プロセスごとに必ず再構成」を正式な前提として明記する。

## 未確定 / 要レビュー事項

- （現時点で未確定の論点なし。上記すべてレビューで確定済み。）
