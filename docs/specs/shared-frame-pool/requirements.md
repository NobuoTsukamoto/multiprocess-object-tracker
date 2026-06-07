# Requirements — shared-frame-pool

> 逆生成 spec。source of truth は [`src/shared_frame_pool.py`](../../../src/shared_frame_pool.py)。記法は [`conventions.md`](../../steering/conventions.md) の EARS 節に従う。
> **要レビュー**: 各要求を出典コード行と突き合わせて確認すること。

## 対象 / スコープ

- **対象モジュール**: `src/shared_frame_pool.py`（プロセス間でフレームを pickle せず共有メモリで転送するリングバッファ）。
- **スコープ内**: owner 側プール（`SharedFramePool`）と accessor 側（`SharedFrameAccessor`）の書き込み/読み出し/退避/リセット/後始末、`SharedFrameSpec` 受け渡し、`FrameRef` の流通。
- **スコープ外**: 呼び出し側（camera/object_tracking controller）でのポリシー選択ロジック、`FrameRef`/`FrameData` の定義（[`data_models.py`](../../../src/data_models.py)）。

## 用語集

| 用語 | 定義 |
|:--|:--|
| owner | プールを生成するメインプロセス側の `SharedFramePool` |
| accessor | サブプロセス（writer/reader）が `SharedFrameSpec` でアタッチする `SharedFrameAccessor` |
| slot | 共有メモリ1ブロック（リングバッファの1要素）。番号で識別 |
| free_queue | 空きスロット番号を保持する Queue |
| data_queue | 書き込み済みフレームの `FrameRef`(frame_id, timestamp, slot) を保持する Queue |
| FrameRef | スロットへの軽量参照。Queue で流す唯一の本体（画像は流さない） |

## 要求一覧（EARS）

### 生成 / アタッチ

| ID | 種別 | 要求（EARS） | 出典 | 対応テスト |
|:--|:--|:--|:--|:--|
| R-SFP-01 | ユビキタス | owner はメインプロセスで N スロットの共有メモリと free_queue（全スロット番号を充填）を生成すること。data_queue は生成せず、コンストラクタ引数として呼び出し側（消費側 Queue の所有者）から受け取ること。 | `shared_frame_pool.py:70-89` | — |
| R-SFP-02 | ユビキタス | owner は `spec` プロパティで、サブプロセスがアタッチ可能な `SharedFrameSpec`（共有メモリ名・shape・dtype・両 Queue）を提供すること。 | `shared_frame_pool.py:91-99` | 間接 (`_make_spec`) |
| R-SFP-03 | ユビキタス | accessor は受け取った spec の共有メモリにアタッチし、各スロットに対する numpy view を保持すること。 | `shared_frame_pool.py:156-164` | — |

### 書き込み（writer 側 `write`）

| ID | 種別 | 要求（EARS） | 出典 | 対応テスト |
|:--|:--|:--|:--|:--|
| R-SFP-04 | 異常系 | 書き込むフレームの shape がプールの shape と一致しないとき、システムは書き込みを行わず False を返すこと。shape チェックは slot 取得（`:180`）より前に行われるため、**スロットを消費しない**（free_queue は不変）。 | `shared_frame_pool.py:175-177,180` | — |
| R-SFP-05 | イベント駆動 | 空きスロットがあるとき、システムはフレームを当該スロットへコピーし、`FrameRef` を data_queue に publish して True を返すこと。 | `shared_frame_pool.py:180,189-194` | `test_write_retries_before_dropping...` |
| R-SFP-06 | イベント駆動 | 空きスロットが無いとき、システムは data_queue 先頭（最古）の `FrameRef` を取り出してそのスロットを再利用すること（evict-oldest）。 | `shared_frame_pool.py:181-185` | `test_write_retries_before_dropping...` |
| R-SFP-07 | 異常系 | 空きスロットも退避可能な保留フレームも無いとき、システムはフレームを破棄し False を返すこと。 | `shared_frame_pool.py:186-187` | `test_write_still_drops_after_queue_retry...` |
| R-SFP-08 | 異常系 | フレームは publish 前に確保スロットへコピー済み（`:189`）であり、その後 data_queue への publish が満杯で失敗したとき、システムは確保したスロットを free_queue へ戻し False を返すこと（戻したスロットには未publishの古いデータが残るが free として再利用されるため実害なし）。 | `shared_frame_pool.py:189,195-201` | — |

### 読み出し（reader 側）

| ID | 種別 | 要求（EARS） | 出典 | 対応テスト |
|:--|:--|:--|:--|:--|
| R-SFP-09 | イベント駆動 | `read(timeout)` は最大 timeout 秒ブロックして次の `FrameRef` を取得し、フレームのコピーを返してスロットを free_queue へ戻すこと。タイムアウト時は `queue.Empty` を送出すること。 | `shared_frame_pool.py:204-218` | — |
| R-SFP-09b | イベント駆動 | `read_nowait()` は data_queue を非ブロックで取得し、データが無ければ即座に `queue.Empty` を送出すること。取得時はフレームのコピーを返し、スロットを free_queue へ戻すこと。 | `shared_frame_pool.py:220-227` | `test_read_latest_can_bound_skipped_frames`（間接利用） |
| R-SFP-10 | ユビキタス | 読み出しが返すフレームは view のコピーであり、スロットは戻り値返却前に解放されるため、呼び出し側は返却 ndarray を無期限に保持してよいこと。 | `shared_frame_pool.py:213-218` | — |
| R-SFP-11 | イベント駆動 | `read_latest(timeout)` は最初の `FrameRef` を最大 timeout 秒待ち、その後ブロックせず後続をドレインして、スキップした古いフレームのスロットを解放し、選ばれたフレームとスキップ数を返すこと。 | `shared_frame_pool.py:229-271` | `test_read_latest_returns_skipped_count...` |
| R-SFP-12 | オプション | `read_latest` の `max_skip` が None のとき、システムは保留中の全フレームをスキップし最新のみ返すこと（latest）。 | `shared_frame_pool.py:251-264` | `test_read_latest_returns_skipped_count...` |
| R-SFP-13 | オプション | `read_latest` の `max_skip` が 0 以下のとき、システムは1フレームもスキップせず先頭を返すこと（FIFO 相当）。 | `shared_frame_pool.py:246-247,252` | `test_read_latest_treats_negative_max_skip...` |
| R-SFP-14 | オプション | `read_latest` の `max_skip` が正のとき、システムは最大 `max_skip` フレームまでスキップし、選ばれたフレームのみコピーして返すこと。 | `shared_frame_pool.py:246-264` | `test_read_latest_can_bound_skipped_frames` |

### Queue feeder 遅延の許容

| ID | 種別 | 要求（EARS） | 出典 | 対応テスト |
|:--|:--|:--|:--|:--|
| R-SFP-15 | 状態駆動 | `multiprocessing.Queue` の feeder スレッド遅延で一時的に Empty が観測される間、システムは短いリトライ（既定 2 回・各 1ms）で get を再試行し、実質ブロックせずに取得を試みること。 | `shared_frame_pool.py:30-53` | `test_write_retries_before_dropping...`, `test_read_latest_retries_when_drain...` |

### リセット / 後始末

| ID | 種別 | 要求（EARS） | 出典 | 対応テスト |
|:--|:--|:--|:--|:--|
| R-SFP-16 | 異常系 | プールが active（worker 稼働中）の間に `reset_free_slots()` が呼ばれたとき、システムは `RuntimeError` を送出すること。 | `shared_frame_pool.py:125-129` | `test_reset_free_slots_is_guarded...` |
| R-SFP-17 | イベント駆動 | active でないとき `reset_free_slots()` が呼ばれたら、システムは両 Queue をドレインして free_queue に全スロット番号を再充填すること。 | `shared_frame_pool.py:131-138` | `test_reset_free_slots_is_guarded...`（正常パス） |
| R-SFP-18 | イベント駆動 | `cleanup()` 時、システムは全共有メモリを close かつ unlink し、例外は無視すること。 | `shared_frame_pool.py:140-150` | — |
| R-SFP-19 | イベント駆動 | accessor の `close()` 時、システムは保持する共有メモリ参照と view を解放すること。 | `shared_frame_pool.py:273-280` | — |

## 前提条件 / 不変条件

- **P-SFP-01**: `reset_free_slots()` は、当該プールを使う **全 worker/accessor が停止した後**にのみ呼ぶこと。稼働中に呼ぶとスロット所有権が壊れる（あるプロセスが読み書き中のスロットが free_queue に戻る）。`mark_active()`/`mark_inactive()` で状態を管理し、guard で保護される。出典 `shared_frame_pool.py:113-129`。
- **P-SFP-02**: スロットは free_queue と data_queue のいずれか一方にのみ存在する（二重所有しない）。書き込みは free→data、読み出しは data→free へ受け渡す。出典 `shared_frame_pool.py:180-200,212-218,255-270`。
- **P-SFP-03**: 共有メモリの生成・unlink は owner が一度だけ行い、accessor は close のみ（unlink しない）。出典 `shared_frame_pool.py:140-150,273-280`。

## 決定事項（レビュー済み）

- **R-SFP-15 のリトライ予算は許容**: worst-case で約 4ms/frame の追加待ち（writer が free 探索と eviction で 2 回呼ぶため）になり得るが、**設計上の上限を 30FPS**（フレーム周期 33.3ms に対し約 12%）までとし許容と判断。発生は feeder 遅延とスロット逼迫が重なる稀ケースに限られる。高 FPS（≳60）運用時はリトライ予算の設定化を検討（tasks.md「実装/改善」に既出）。出典コメント `shared_frame_pool.py:30-38`。
- **`read_nowait()` は spec 化済み**: 公開 API かつテストで実利用のため R-SFP-09b として要求一覧に追加（`shared_frame_pool.py:220-227`）。
