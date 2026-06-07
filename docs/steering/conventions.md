# Conventions — コーディング規約・spec 記述規約・レビュー基準

> spec を書く/直す前に必ず読むこと。skill はこのファイルを参照する。

## 言語・表記

- ドキュメント本文・説明は **日本語**。
- 識別子（ファイル名、型/関数名、skill の `name`、spec ディレクトリ名、見出しキー）は **英語**（kebab-case / snake_case / PascalCase は対象に従う）。
- 仕様内でコードを指す時は必ず **出典 `file:line`**（例: `src/shared_frame_pool.py:179`）を添える。

## コーディング規約

- Python: `snake_case`（関数/変数）、`PascalCase`（クラス）、`@dataclass` で IPC/設定の構造体を表現。
- IPC データ構造は [`../../src/data_models.py`](../../src/data_models.py) に集約。設定スキーマは [`../../src/config_manager.py`](../../src/config_manager.py) に集約。
- 既存コードのスタイル（型注釈の付け方、docstring の粒度）に合わせる。新規追加時に周囲と乖離させない。

## spec の構成（3点セット）

各 feature は `docs/specs/<feature>/` に以下を置く。雛形は [`../specs/_template/`](../specs/_template/) をコピーする。

- `requirements.md` — **何を満たすべきか**。EARS 形式で受入基準を書く（下記）。
- `design.md` — **どう実現しているか/するか**。責務・公開IF・データ構造・**不変条件/前提条件**・トレードオフ・関連コードパス。
- `tasks.md` — **やること**。チェックボックスで実装/テスト/ドキュメントのタスク分解。

## EARS（requirements の書き方）

要求は EARS（Easy Approach to Requirements Syntax）で記述する。基本パターン:

- **ユビキタス（常時）**: `システムは <振る舞い> すること。`
- **イベント駆動**: `<トリガ> したとき、システムは <振る舞い> すること。`（When …, the system shall …）
- **状態駆動**: `<状態> の間、システムは <振る舞い> すること。`（While …, …）
- **オプション**: `<機能/条件> がある場合、システムは <振る舞い> すること。`（Where …, …）
- **望ましくない振る舞い**: `<望ましくない条件> のとき、システムは <振る舞い> すること。`（If …, then …）

各要求は **一意 ID**（例 `R-SFP-01`）を付け、対応する出典コード `file:line` と、可能なら対応テストを併記する。

## レビュー基準（逆生成 spec は人手レビュー必須）

逆生成した spec は「それらしいが間違っている」リスクがある。レビュー時に最低限チェックする:

1. **コードと矛盾しないか** — 各 EARS 項目を出典 `file:line` と突き合わせ、実際の分岐・例外・境界条件と一致するか。
2. **推測した意図は明示したか** — コードから読み取れない設計意図は「推測」と明記し、断定しない。
3. **境界・異常系を網羅したか** — 空/満杯/競合/タイムアウト等のエッジケースが要求に現れているか。
4. **同期確認** — spec を変えたら README・他 steering・関連 spec のリンクと記述を更新したか。

## 変更時の同期

- IPC メッセージを追加/変更 → `data_models.py` と [`structure.md`](structure.md) の IPC 節を更新。
- 設定キーを追加/変更 → `config_manager.py`・`config/default.yaml`・README 設定表を同期。
