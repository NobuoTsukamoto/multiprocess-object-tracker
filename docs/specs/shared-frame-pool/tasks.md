# Tasks — shared-frame-pool

> 逆生成 spec の付随タスク。テストは [`tests/test_shared_frame_pool.py`](../../../tests/test_shared_frame_pool.py)。

## テストカバレッジ状況

| 要求 ID | 対応テスト | 状態 |
|:--|:--|:--|
| R-SFP-05, R-SFP-06, R-SFP-15 | `test_write_retries_before_dropping_when_evict_queue_looks_empty` | ✅ |
| R-SFP-07 | `test_write_still_drops_after_queue_retry_budget_is_exhausted` | ✅ |
| R-SFP-11, R-SFP-12 | `test_read_latest_returns_skipped_count_and_drains_to_newest` | ✅ |
| R-SFP-14 | `test_read_latest_can_bound_skipped_frames` | ✅ |
| R-SFP-13 | `test_read_latest_treats_negative_max_skip_as_fifo_read` | ⚠️ 部分（負値 `-1` のみ。`max_skip=0` 境界は未カバー） |
| R-SFP-15（reader 側） | `test_read_latest_retries_when_drain_queue_temporarily_looks_empty` | ✅ |
| R-SFP-16, R-SFP-17 | `test_reset_free_slots_is_guarded_while_pool_is_active` | ✅ |
| R-SFP-04（shape 不一致） | — | ⬜ 未カバー |
| R-SFP-08（publish Full で slot 返却） | — | ⬜ 未カバー |
| R-SFP-09, R-SFP-10（read のブロック/timeout/コピー） | — | ⬜ 未カバー |
| R-SFP-18, R-SFP-19（cleanup/close） | — | ⬜ 未カバー |

## タスク

### 文書化 / 整合
- [x] requirements/design を逆生成（出典 `file:line` 付き）
- [x] 人手レビュー: evict-oldest（`:179-201`）/ read_latest の max_skip 分岐（`:246-264`）/ reset 前提（`:125-129`）をコードと突合
  - 反映: 単一 writer 前提（evict-oldest）と `_active` の管理責任を design「不変条件 / 前提条件」に追記
- [ ] `read_nowait()`（`:220-227`）を要求として spec 化するか判断

### テスト（未カバー要求の補完）
- [ ] R-SFP-04: shape 不一致で `write` が False を返すことのテスト
- [ ] R-SFP-08: data_queue Full で slot が free_queue に戻ることのテスト
- [ ] R-SFP-09/R-SFP-10: `read` の timeout で `Empty`、返却フレームが view から独立コピーであることのテスト
- [ ] R-SFP-13: `max_skip=0` を直接渡したとき 0 スキップ（FIFO, 先頭を返す）となることのテスト（現状は負値 `-1` のみ検証）

### 実装 / 改善（将来）
- [ ] リトライ予算（`_QUEUE_GET_RETRIES`/`_QUEUE_GET_RETRY_DELAY_SEC`, `:37-38`）を設定化するか検討（運用 FPS に応じた調整余地）
- [ ] `cleanup()` の例外握りつぶし（`:143-149`）方針をログ出力するか検討

## メモ / 申し送り

- 本 spec は逆生成の「型」確立用の代表サンプル。残りモジュール（gui/camera/object_tracking/config/logger/data_models）は `reverse-engineer-spec` skill で同形式に展開する（各々レビュー必須）。
