# Design — logger

> 逆生成 spec。`src/logger.py` が「どう実現されているか」を記す。コードが正。
> 関連: [`structure.md`](../../steering/structure.md)（Logger は横断ユーティリティ）、[`config-manager`](../config-manager/)（`LoggingConfig`）。

## 概要

`logger` は `loguru` をラップし、アプリ全体のログ出力を一元設定する薄いユーティリティである。`Logger(config)` を生成すると、`loguru` のプロセスグローバルロガーを「既存ハンドラ全削除 → 設定済みシンクを1つ追加」で再構成し、加えてカスタムレベル `PERFORMANCE`（🚀, `no=38`）を登録する。各プロセス（メイン/camera/object_tracking）は自プロセス内で `Logger` を生成し、`get_logger()` で同じグローバル `logger` を取得して使う。出典 `src/logger.py:12-33`。

設計の要点は、① **設定の集約**（出力先・レベル・フォーマット・カスタムレベルを1箇所で決める）、② **プロセスごとの再構成**（マルチプロセスで各子プロセスが独立した `loguru` を持つため）、③ **冪等なカスタムレベル登録**（再登録の `ValueError` を握りつぶす）の3点である。

## 責務と構成要素

| 要素 | 役割 | 出典 |
|:--|:--|:--|
| `Logger.__init__` | `LoggingConfig` を保持し `_configure_logger` を呼ぶ | `src/logger.py:13-15` |
| `Logger._configure_logger` | `remove()`→`add(sink, level, format)`、`PERFORMANCE` 登録 | `src/logger.py:17-30` |
| `Logger.get_logger` | 設定済みグローバル `logger` を返す | `src/logger.py:32-33` |

## 公開インターフェース

```
Logger(config: LoggingConfig)        # 生成時にグローバルロガーを再構成（src/logger.py:13-15）
Logger.get_logger() -> loguru.Logger # プロセス共有の logger を返す（src/logger.py:32-33）

# 消費側の典型
log = Logger(logging_config).get_logger()
log.info(...) / log.warning(...) / log.error(...) / log.debug(...)
log.log("PERFORMANCE", "...")        # カスタムレベル（src/object_tracking_controller.py:245）
```

## データ構造 / 状態

- `Logger` の状態は `self.config: LoggingConfig` のみ。実体の状態は `loguru` のグローバル `logger`（プロセス共有 singleton）に存在する。出典 `src/logger.py:14`。
- 消費するキー: `config.output`（`"console"` or パス）、`config.level`（`upper()` でレベル名）。出典 `src/logger.py:20-21`。

## データフロー / 制御フロー

```mermaid
flowchart TD
    A[各プロセス: Logger config] --> B[_configure_logger]
    B --> C[logger.remove 全ハンドラ削除]
    C --> D{output == console?}
    D -->|yes| E[sink = sys.stdout]
    D -->|no| F[sink = output パス]
    E --> G[logger.add sink, level.upper, format]
    F --> G
    G --> H[logger.level PERFORMANCE no=38]
    H -->|既存なら ValueError| I[except: 無視]
    A2[get_logger] --> J[グローバル logger を返す]
```

- メイン: `main.py:32` が `logging` 設定で `Logger` 生成。
- ワーカー: `camera_controller.py:79` / `object_tracking_controller.py:125` が **子プロセス内 `run()`** で生成（spawn 対策）。
- 出力: `info`/`warning`/`error`/`debug` は各所、`PERFORMANCE` は `object_tracking_controller.py:260-268` から `performance_interval` フレームごと。

## 不変条件 / 前提条件

- **後勝ち再構成（蓄積しない）**: `remove()`（全削除）→`add()`（1個）のため、同一プロセスで複数 `Logger` を生成してもハンドラは常に1個で重複しない。ガードは不要。出典 `src/logger.py:18-19`。
- **プロセス分離（fork/spawn 両対応）**: spawn では子の `loguru` がまっさら、fork では親の構成を継承。いずれも子の `remove()`→`add()` 再構成で正しく動く。「構成済みスキップ」型ガードは fork でフラグ継承により再構成を飛ばし危険なため**入れない**。出典 `src/logger.py:17-23`、`src/camera_controller.py:79`、`src/object_tracking_controller.py:125`。
- **`PERFORMANCE=38`**: `WARNING(30)`〜`ERROR(40)` の間。`INFO`/`DEBUG` で可視、`ERROR` で抑制。出典 `src/logger.py:27`。
- **冪等登録**: `logger.level("PERFORMANCE", ...)` の再呼び出しは `ValueError`。try/except で握りつぶし冪等化。出典 `src/logger.py:26-30`。

## エッジケース / 異常系

- **不正レベル文字列**: `config.level` が未知レベルだと現状 `logger.add(level=...)` が `ValueError`（未ハンドル）。**改修予定**: 許容レベルを検証し明示エラーを送出（R-LOG-09）。出典 `src/logger.py:21`。
- **`output` がファイルパス**: `"console"` 以外は `loguru` がその文字列をファイルシンクとして扱い、ファイルへ出力する。**公式機能として正式化**（README を更新）。出典 `src/logger.py:20`。
- **同一プロセス多重生成**: `remove()`→`add()` でハンドラは常に1個に保たれ、重複しない。ガード不要（R-LOG-10）。出典 `src/logger.py:18-19`。

## トレードオフ / 設計判断

- **`loguru` グローバルに乗る**: インスタンスごとに分離せず、プロセス共有の `logger` を再構成して使う。「1プロセス1ロガー、プロセスごとに必ず再構成」が正式な前提（R-LOG-10）。`remove()`→`add()` で蓄積しないため多重生成にも頑健。
- **カスタムレベルの冪等化**: `ValueError` を握りつぶすことで、再構成や再生成が起きても安全に通す。
- **出力先の柔軟性（確定）**: console + 任意ファイルパスを公式サポート。README を実態へ更新する（コードを console 固定に寄せる案は不採用）。

## 関連コードパス

- `src/logger.py:12-33` — `Logger` 本体
- `src/main.py:32` — メインプロセスでの生成
- `src/camera_controller.py:79` / `src/object_tracking_controller.py:125` — ワーカーでの生成
- `src/object_tracking_controller.py:253,260-268` — `PERFORMANCE` ログの発火
- `src/config_manager.py:53-57` — `LoggingConfig`（level/output/performance_interval）
