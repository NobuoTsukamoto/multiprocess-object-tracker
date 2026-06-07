---
name: reverse-engineer-spec
description: 既存のソースコードから仕様書（requirements/design/tasks）を逆生成する。「このモジュールの仕様を起こして」「コードから spec を作って」「リバースエンジニアリングで文書化」等の依頼で使う。multiprocess-object-tracker のブラウンフィールド SDD 用。
---

# reverse-engineer-spec

既存コードを source of truth として、機能単位の仕様（requirements / design / tasks）を逆生成する手順。

## 前提（必ず最初に読む）

- [`docs/steering/conventions.md`](../../../docs/steering/conventions.md) — EARS 記法・レビュー基準・言語ルール。
- [`docs/steering/structure.md`](../../../docs/steering/structure.md) — モジュール境界・IPC 規約。
- 原則: **コードが正**。仕様は日本語、識別子は英語。逆生成は「それらしいが間違う」ため、各要求に出典 `file:line` を付け、最後に人手レビューを依頼する。

## 手順

1. **対象を確定する**
   - 対象モジュール（例 `src/shared_frame_pool.py`）と feature 名（kebab-case, 例 `shared-frame-pool`）を決める。

2. **精読する**
   - 対象のソース・docstring・コメントを読む。
   - 既存テスト（`tests/test_<...>.py`）を読み、テストが保証している挙動＝確定仕様として拾う。
   - 依存する `data_models.py` / `config_manager.py` 等も必要な範囲で確認する。

3. **雛形をコピーする**
   - [`docs/specs/_template/`](../../../docs/specs/_template/) の 3 ファイルを `docs/specs/<feature>/` にコピーして埋める。

4. **requirements.md を書く**
   - 挙動を **EARS** で記述。各要求に一意 ID（`R-<略称>-NN`）・出典 `file:line`・対応テストを付ける。
   - 分岐・境界・異常系（空/満杯/競合/タイムアウト等）を必ず洗い出す。
   - 呼び出し側の前提条件・不変条件を「前提条件」節に明記する。

5. **design.md を書く**
   - 責務と構成要素、公開インターフェース、データ構造/状態、データフロー、**不変条件/前提条件**、エッジケース、トレードオフを埋める。
   - コードから読み取れない設計意図は「推測」と明記し、断定しない。

6. **tasks.md を書く**
   - 要求 ID とテストの対応表で **カバー済み/未カバー**を可視化。
   - 未文書化の挙動・テスト不足・将来の改善（型注釈、例外方針の明文化など）をタスク化する。

7. **整合とレビュー依頼で締める**
   - README・他 steering とのリンク/記述を同期する。
   - 各 EARS 項目を出典コード行と突き合わせて自己検証し、**ユーザーに人手レビューを依頼**する（特に境界・異常系・前提条件）。

## 完了の目安

- `docs/specs/<feature>/` に 3 ファイルが揃い、全要求に出典 `file:line` が付いている。
- テストカバレッジ状況が tasks.md に整理されている。
- レビューしてほしい論点（推測した意図・未確定事項）が明示されている。
