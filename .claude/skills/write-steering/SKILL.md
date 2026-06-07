---
name: write-steering
description: コードベースから steering ドキュメント（product/tech/structure/conventions）を生成・更新する。「steering を整備して」「プロジェクトの前提ドキュメントを更新」「product.md/tech.md を作り直して」等の依頼で使う。
---

# write-steering

`docs/steering/` の永続ドキュメントを、コード・設定・README から生成または最新化する手順。

## 対象ファイル

- `docs/steering/product.md` — 何を・なぜ（ビジョン、ユースケース、非機能要求）。
- `docs/steering/tech.md` — 技術スタック・依存・実行/デバッグ/テスト手順。
- `docs/steering/structure.md` — ディレクトリ構成・命名規約・IPC/プロセス境界。
- `docs/steering/conventions.md` — コーディング規約・spec 記述規約(EARS)・レビュー基準。

## 手順

1. **出典を集める**
   - `product` → `README.md`、`src/` 各モジュールの責務。
   - `tech` → `pyproject.toml` / `requirements.txt` / `uv.lock` / `config/default.yaml` / `.vscode/launch.json` / `.python-version`。
   - `structure` → `src/` のディレクトリ構成、`data_models.py`、IPC（`shared_frame_pool.py` の所有権・Queue・stop_event）。
   - `conventions` → 既存コードのスタイル、`docs/specs/_template/` の構成。

2. **書く / 更新する**
   - 本文は日本語、識別子は英語。各記述に出典ファイル（必要なら `file:line`）を添える。
   - 「コードが正」。実装と矛盾する記述は実装に合わせて直す。
   - 既存ファイルがある場合は全書き換えせず、変わった箇所だけ最小差分で更新する。

3. **相互リンクを保つ**
   - `AGENTS.md` の地図、`README.md`、`docs/specs/` への参照が切れていないか確認する。

## 完了の目安

- 4 ファイルが現状のコード/設定と一致し、出典が辿れる。
- AGENTS.md ↔ steering ↔ specs のリンクが解決する。
