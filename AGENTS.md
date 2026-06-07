# AGENTS.md

> AI エージェント（Claude Code / Codex / Cursor / Gemini CLI など）と開発者が、このリポジトリで作業を始めるためのエントリポイント。
> まずこのファイルと [`docs/steering/`](docs/steering/) を読んでから作業すること。

## このプロジェクトについて

`multiprocess-object-tracker` は、カメラ映像の物体検出・追跡を **multiprocessing** で並列化したリアルタイム GUI アプリ（Python）。
エンドユーザー向けの概要は [`README.md`](README.md)、開発・設計の文脈は `docs/steering/` を参照。

## ドキュメントの地図

| 場所 | 役割 |
|:--|:--|
| [`README.md`](README.md) | エンドユーザー／導入者向けの概要・設定表・モジュール構成図 |
| [`docs/steering/product.md`](docs/steering/product.md) | 何を・なぜ作るか（ビジョン、ユースケース、非機能要求） |
| [`docs/steering/tech.md`](docs/steering/tech.md) | 技術スタック・依存・実行/デバッグ/テスト手順 |
| [`docs/steering/structure.md`](docs/steering/structure.md) | ディレクトリ構成・命名規約・IPC/プロセス境界の規約 |
| [`docs/steering/conventions.md`](docs/steering/conventions.md) | コーディング規約・spec 記述規約(EARS)・レビュー基準 |
| [`docs/specs/`](docs/specs/) | 機能単位の仕様（requirements / design / tasks） |
| [`docs/specs/_template/`](docs/specs/_template/) | spec の雛形（新規 spec はここをコピー） |
| [`.claude/skills/`](.claude/skills/) | 再利用可能な作業手順（Agent Skills / SKILL.md オープン標準） |

## 最重要ルール

1. **コードが正（source of truth）**。本リポジトリはブラウンフィールド（既存コードから仕様を逆生成）。
   spec とコードが食い違う場合は、まずコードを確認し、spec 側を直すか、意図の不一致として明示する。
2. **逆生成した spec は人手レビュー必須**。LLM が起こした仕様は「それらしいが間違っている」ことがある。
   各 requirements 項目には出典 `file:line` を必ず添え、レビューで突き合わせられるようにする。
3. **記述言語**: 本文・説明は **日本語**。ファイル名・skill の `name`・見出しキー等の**識別子は英語**。
4. spec/steering を更新したら、関連する相互リンクと `README.md` の整合も確認する。

## 開発フロー

- **既存の挙動を文書化したい** → skill [`reverse-engineer-spec`](.claude/skills/reverse-engineer-spec/SKILL.md) を使い、対象モジュールから `docs/specs/<feature>/` を逆生成する。
- **新しい変更を加えたい** → skill [`spec-driven-change`](.claude/skills/spec-driven-change/SKILL.md) を使い、requirements → design → tasks → 実装の順で進める（1変更にスコープを絞る）。
- **steering を整備/更新したい** → skill [`write-steering`](.claude/skills/write-steering/SKILL.md) を使う。

> 他ツール（Codex/Cursor 等）で skill が自動ロードされない場合も、上記 SKILL.md を手順書として直接読めば同じフローを再現できる。

## 主要コマンド

```bash
# 実行（リポジトリルートから）
python src/main.py --config config/default.yaml

# テスト
python -m pytest tests/

# 依存（uv を利用）
uv sync
```

詳細は [`docs/steering/tech.md`](docs/steering/tech.md) を参照。
