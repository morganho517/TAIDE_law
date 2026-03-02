# TAIDE Law Converters

將法規文件（`.doc` / `.docx`）批次轉換成 Markdown 或結構化 JSON，供後續 QA pair 生成使用。

---

## 目錄結構

```
.
├── rawdata/                # 原始 .doc / .docx 法規文件（主流程法規 / 副流程文件）
├── processed_data/         # 轉換輸出（.md 或 .json，保留子目錄結構）
├── logs/                   # 轉換失敗紀錄（convert_fail_<timestamp>.log）
├── converters/
│   ├── dock_to_md.py       # 轉換為 Markdown
│   └── docx_to_json.py     # 轉換為 JSON
├── genQA_pair/
│   └── gen_qa.py           # QA pair 生成
├── utils.py                # 掃描 rawdata 並回傳路徑 List
└── requirements.txt
```

---

## 安裝環境

### 1. Python 套件

```bash
pip install -r requirements.txt
```

### 2. Pandoc

```bash
# Ubuntu / Debian
sudo apt install -y pandoc

# macOS
brew install pandoc
```

### 3. LibreOffice（用於將舊版 `.doc` 轉換成 `.docx`）

> **必要元件**：`libreoffice-writer`。
> 僅安裝 `libreoffice-common` 或 `libreoffice-core` 不夠，需明確安裝 `libreoffice-writer`。

```bash
# Ubuntu / Debian
sudo apt install -y libreoffice-writer

# macOS（使用 Homebrew Cask）
brew install --cask libreoffice

# 驗證安裝
soffice --version
```

---

## 使用方式

將原始文件放入 `rawdata/` 下對應子目錄後執行：

```bash
# 轉換為 Markdown
python converters/dock_to_md.py

# 轉換為 JSON
python converters/docx_to_json.py
```

- 輸出會寫入 `processed_data/`，並保留 `rawdata/` 底下的子目錄結構。
- 轉換失敗的檔案會記錄於 `logs/convert_fail_<timestamp>.log`。
- 全部成功時 log 檔自動刪除。

### `.doc` 轉換流程

`dock_to_md.py` 會自動偵測 `.doc` 檔案並呼叫 `soffice` 先將其轉為 `.docx`，再交給 pandoc 處理，無需手動預先轉換。

```
.doc  ──►  soffice  ──►  .docx  ──►  pandoc  ──►  .md
```

---

## 注意事項

- `~$*.docx`（Word 暫存鎖定檔）已自動排除，不會被處理。
- 若 log 中出現 `soffice FileNotFoundError`，請確認已安裝 `libreoffice-writer`（非僅 `libreoffice-common`）。
