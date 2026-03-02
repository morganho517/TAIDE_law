import os
import re
import sys
import logging
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
import pypandoc

sys.path.insert(0, str(Path(__file__).parent.parent))
from utils import get_all_file_paths, RAWDATA_DIR


# ===== Helpers =====

CH_NUM = "一二三四五六七八九十百千〇○"


def clean_markdown(text: str) -> str:
    # 1) remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    # 2) remove blockquote markers
    text = re.sub(r"^>\s?", "", text, flags=re.MULTILINE)

    # 3) normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 4) trim trailing spaces on each line
    text = "\n".join(line.rstrip() for line in text.splitlines())

    # 5) collapse excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def beautify_structure(text: str) -> str:
    lines = text.splitlines()
    out = []
    prev_was_heading = False

    # patterns
    p_part = re.compile(rf"^\s*第([{CH_NUM}]+)編\s*(.+)?\s*$")
    p_article = re.compile(rf"^\s*([{CH_NUM}]+)、\s*(.+?)\s*$")  # 一、xxx
    p_sub = re.compile(rf"^\s*[\(（]([{CH_NUM}]+)[\)）]\s*(.+?)?\s*$")  # (一) xxx / （一）xxx
    p_num_item = re.compile(r"^\s*(\d+)\.\s*(.+?)\s*$")  # 1. xxx

    for i, raw in enumerate(lines):
        line = raw.strip()

        if not line:
            # keep at most one blank line
            if out and out[-1] != "":
                out.append("")
            prev_was_heading = False
            continue

        # # 第X編
        m = p_part.match(line)
        if m:
            num, title = m.group(1), (m.group(2) or "").strip()
            heading = f"# 第{num}編 {title}".rstrip()
            # ensure blank line before headings (except start)
            if out and out[-1] != "":
                out.append("")
            out.append(heading)
            out.append("")
            prev_was_heading = True
            continue

        # ## 一、（點/條）
        m = p_article.match(line)
        if m:
            num, title = m.group(1), m.group(2).strip()
            heading = f"## {num}、{title}"
            if out and out[-1] != "":
                out.append("")
            out.append(heading)
            out.append("")
            prev_was_heading = True
            continue

        # ### （一）
        m = p_sub.match(line)
        if m:
            num, title = m.group(1), (m.group(2) or "").strip()
            # normalize to fullwidth parentheses
            heading = f"### （{num}）{title}".rstrip()
            if out and out[-1] != "":
                out.append("")
            out.append(heading)
            out.append("")
            prev_was_heading = True
            continue

        # numbered list: 1. xxx -> "1. xxx" and ensure blank line before list starts
        m = p_num_item.match(line)
        if m:
            idx, body = m.group(1), m.group(2).strip()
            # If previous line is not blank and not a heading, add a blank line to make list stable in markdown parsers
            if out and out[-1] != "" and not prev_was_heading and not re.match(r"^\d+\.\s", out[-1]):
                out.append("")
            out.append(f"{idx}. {body}")
            prev_was_heading = False
            continue

        # default: keep as paragraph line
        # if previous is a list item and current is normal text, add blank line (avoid accidental list continuation)
        if out and re.match(r"^\d+\.\s", out[-1]) and not re.match(r"^\s", raw):
            # paragraph after list
            out.append("")
        out.append(line)
        prev_was_heading = False

    # final cleanup: collapse too many blanks again
    final = "\n".join(out)
    final = re.sub(r"\n{3,}", "\n\n", final).strip()
    return final


def add_metadata(filename: str, body: str) -> str:
    title = os.path.splitext(filename)[0]
    header = f"""---
source: {filename}
title: {title}
type: regulation
---

"""
    return header + body.strip() + "\n"


# ===== Helpers =====

def _doc_to_docx(doc_path: Path, out_dir: Path) -> Path:
    """用 soffice 將 .doc 轉為 .docx，輸出至 out_dir，回傳轉換後的 Path。
    先複製成 ASCII 臨時檔名再轉，避免 soffice 不支援非 ASCII 路徑。"""
    import uuid
    tmp_src = out_dir / f"_src_{uuid.uuid4().hex}.doc"
    shutil.copy2(doc_path, tmp_src)
    try:
        result = subprocess.run(
            [
                "soffice", "--headless",
                "--convert-to", "docx",
                "--outdir", str(out_dir),
                str(tmp_src),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"soffice failed: {result.stderr.strip() or result.stdout.strip()}")
        converted = out_dir / (tmp_src.stem + ".docx")
        if not converted.exists():
            raise FileNotFoundError(
                f"soffice 執行成功但找不到輸出檔：{converted}\n"
                f"stdout: {result.stdout.strip()}\nstderr: {result.stderr.strip()}"
            )
        return converted
    finally:
        tmp_src.unlink(missing_ok=True)


# ===== Main =====

OUTPUT_DIR = Path(__file__).parent.parent / "processed_data"
LOG_DIR = Path(__file__).parent.parent / "logs"


def _setup_fail_logger() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"convert_fail_{timestamp}.log"

    logger = logging.getLogger("convert_fail")
    logger.setLevel(logging.ERROR)
    logger.handlers.clear()

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(fh)

    return logger, log_path


def convert_all_docx_to_md(
    root: Path = RAWDATA_DIR,
    extensions: set[str] = {".doc", ".docx"},
):
    """掃描 root 目錄下所有 doc/docx，轉換為 Markdown 並輸出至 processed_data/，
    保留相對於 root 的子目錄結構。失敗項目寫入 logs/convert_fail_<timestamp>.log。"""
    file_paths = get_all_file_paths(root, extensions)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    logger, log_path = _setup_fail_logger()
    fail_count = 0

    tmp_dir = Path(tempfile.mkdtemp(prefix="doc2docx_"))

    for input_path in file_paths:
        rel = input_path.relative_to(root)          # e.g. 主流程法規/10.人資處/xxx.docx
        output_path = OUTPUT_DIR / rel.with_suffix(".md")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # .doc → 先用 soffice 轉成 .docx
        pandoc_input = input_path
        if input_path.suffix.lower() == ".doc":
            try:
                pandoc_input = _doc_to_docx(input_path, tmp_dir)
            except Exception as e:
                msg = f"{rel} | soffice {e.__class__.__name__}: {e}"
                print(f"SKIP: {msg}")
                logger.error(msg)
                fail_count += 1
                continue

        try:
            md_text = pypandoc.convert_file(
                str(pandoc_input),
                "gfm",
                extra_args=[
                    "--wrap=none",
                    "--markdown-headings=atx",
                ],
            )
        except Exception as e:
            msg = f"{rel} | pandoc {e.__class__.__name__}: {e}"
            print(f"SKIP: {msg}")
            logger.error(msg)
            fail_count += 1
            continue

        try:
            md_text = clean_markdown(md_text)
            md_text = beautify_structure(md_text)
            final_text = add_metadata(input_path.name, md_text)
            output_path.write_text(final_text, encoding="utf-8")
            print(f"Done: {rel} -> {output_path.relative_to(OUTPUT_DIR.parent)}")
        except Exception as e:
            msg = f"{rel} | post-process {e.__class__.__name__}: {e}"
            print(f"SKIP: {msg}")
            logger.error(msg)
            fail_count += 1

    shutil.rmtree(tmp_dir, ignore_errors=True)

    if fail_count:
        print(f"\n⚠️  共 {fail_count} 個檔案轉換失敗，詳見 {log_path}")
    else:
        print("\n✅ 全部轉換完成，無失敗項目")
        log_path.unlink(missing_ok=True)  # 無失敗就刪除空 log


if __name__ == "__main__":
    convert_all_docx_to_md()