---
name: spec-driven-change
description: 新しい機能追加や変更を仕様駆動（requirements→design→tasks→実装）で進める。「この機能を spec 駆動で追加して」「変更前に仕様を起こして実装」「SDD で進めたい」等の依頼で使う。1変更にスコープを絞る incremental 方式。
---

# spec-driven-change

新規変更を、実装前に仕様を固めてから進めるための前進フロー。ブラウンフィールドでは **1つの変更にスコープを絞る**（incremental）のが原則。

## 前提

- [`docs/steering/conventions.md`](../../../docs/steering/conventions.md) と [`docs/steering/structure.md`](../../../docs/steering/structure.md) を読む。
- 既存挙動を変える場合、まず該当機能の spec が `docs/specs/<feature>/` にあるか確認。無ければ [`reverse-engineer-spec`](../reverse-engineer-spec/SKILL.md) で先に現状を文書化してから差分を設計する。

## 手順

1. **スコープを1変更に絞る**
   - 何を・なぜ変えるかを1〜2文で確定。大きければ分割する。

2. **requirements.md（差分）**
   - 追加/変更する受入基準を EARS で書く。既存要求との衝突がないか確認。各要求に ID を付ける。

3. **design.md（差分）**
   - 触る構成要素・公開IF・データ構造・**不変条件**への影響、IPC/設定への波及を記す。
   - IPC メッセージ変更なら `data_models.py`、設定変更なら `config_manager.py` + `config/default.yaml` + README 設定表への影響を明記。

4. **tasks.md**
   - 実装・テスト・ドキュメント更新をチェックボックスで分解。テストは要求 ID に紐づける。

5. **実装する**
   - tasks に沿って実装。既存コードのスタイルに合わせる。テストを追加/更新する。

6. **同期を確認する**
   - `python -m pytest tests/` を実行。
   - spec とコード、README・steering の記述/リンクを同期する。実装で判明した差異は spec に反映する。

## 完了の目安

- spec（3点セットの差分）が実装と一致し、テストが green。
- 関連ドキュメント（README・steering・他 spec）が更新済み。
