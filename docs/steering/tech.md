# Tech — 技術スタック・実行・テスト

> 出典: [`pyproject.toml`](../../pyproject.toml)、[`requirements.txt`](../../requirements.txt)、[`config/default.yaml`](../../config/default.yaml)、[`.vscode/launch.json`](../../.vscode/launch.json)、`src/`。
> バージョン等が食い違う場合はこれらのファイルが正。

## 言語・ランタイム

- **Python `>=3.12`**（[`.python-version`](../../.python-version) は 3.12 系）。
- パッケージ管理は **uv**（[`uv.lock`](../../uv.lock) を同梱）。`requirements.txt` は簡易版で `torch`/`torchvision` を含まないため、再現性のある環境構築は `pyproject.toml` / uv を基準とする。

## 主要依存

| ライブラリ | 用途 | 備考 |
|:--|:--|:--|
| `opencv-python` (cv2) | カメラキャプチャ・リサイズ・色変換 | |
| `onnxruntime` | YOLOX-S ONNX 推論 | `providers` を設定で指定（既定 `CPUExecutionProvider`） |
| `supervision` | ByteTrack による多物体追跡・`Detections` | |
| `numpy==1.26.4` | 配列操作（推論前後処理・共有メモリ view） | バージョン固定 |
| `Pillow` (PIL) | GUI 表示用の画像変換（Tk PhotoImage） | |
| `loguru` | ロギング（独自 `PERFORMANCE` レベル） | |
| `PyYAML` | 設定ファイル読み込み | |
| `torch`, `torchvision` | 依存に記載（直接利用は限定的） | `pyproject.toml` のみ |
| `tkinter` | GUI（標準ライブラリ） | OS の Tk に依存 |

## 環境構築

```bash
# uv を利用（推奨）
uv sync

# もしくは pip（torch/torchvision は別途必要な場合あり）
pip install -r requirements.txt
```

> **実環境では仮想環境(`.venv`)の有効化が前提**。以降の `python` / `pytest` コマンドは有効化済みの venv で実行する。
> - 有効化: `.\.venv\Scripts\Activate.ps1`（PowerShell）
> - 有効化しない場合は venv の Python を直接指定する: `.\.venv\Scripts\python.exe -m pytest tests/`

## 実行

```bash
# リポジトリルートから
python src/main.py --config config/default.yaml
```

- エントリは [`src/main.py`](../../src/main.py)。`--config` で YAML 設定パスを渡す（既定は `../config/default.yaml`）。
- 起動後は GUI の「追跡開始」でワーカープロセス（撮像・推論/追跡）が起動し、「追跡終了」で安全に停止する。
- `src/` 内モジュールは相対 import 前提（`sys.path` に `src` を追加して動かす構成）。

### デバッグ（VSCode）

- [`.vscode/launch.json`](../../.vscode/launch.json) に debugpy 構成あり（config パスは固定指定）。

## 設定

- 設定は [`config/default.yaml`](../../config/default.yaml)。スキーマは [`src/config_manager.py`](../../src/config_manager.py) の dataclass 階層（`AppConfig` → camera/detection/tracking/gui/logging）。
- 各設定キーの意味は [`README.md`](../../README.md) の設定表を参照。

## モデル

- 検出モデル: `models/yolox_s.onnx`（既定パスは設定 `detection.model_path`）。

## テスト

```bash
# venv 有効化済みの場合
python -m pytest tests/

# venv を有効化しない場合は venv の Python を直接指定
.\.venv\Scripts\python.exe -m pytest tests/
```

- テストは `unittest` ベース（`tests/` 配下、`pytest` で実行可）。`pytest` は venv にインストールされているため、上記いずれも venv 前提。
- 既存テスト: [`tests/test_shared_frame_pool.py`](../../tests/test_shared_frame_pool.py)（共有メモリプールの読み書き・退避・リトライ）、[`tests/test_gui_controller.py`](../../tests/test_gui_controller.py)（GUI ロジックの単体）。
- テストは `sys.path.insert(0, .../src)` で `src` を import path に追加している。

## ロギング

- `loguru` ラッパ（[`src/logger.py`](../../src/logger.py)）。独自レベル `PERFORMANCE`（level no. 38）でフレームレート・処理時間を一定間隔（既定 100 フレーム、`logging.performance_interval`）に集約出力する。
