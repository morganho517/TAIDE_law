import os
import re
import pypandoc


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


# ===== Main =====

def convert_all_docx_to_md(folder_path: str):
    output_folder = './processed_data'  # New output folder
    os.makedirs(output_folder, exist_ok=True)  # Ensure the output folder exists

    for filename in os.listdir(folder_path):
        if not filename.lower().endswith(".docx"):
            continue

        input_path = os.path.join(folder_path, filename)
        output_path = os.path.join(output_folder, filename.replace(".docx", ".md"))  # Updated to use output folder

        md_text = pypandoc.convert_file(
            input_path,
            "gfm",
            extra_args=[
                "--wrap=none",
                # reduce weird artifacts
                "--markdown-headings=atx",
            ],
        )

        md_text = clean_markdown(md_text)
        md_text = beautify_structure(md_text)
        final_text = add_metadata(filename, md_text)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(final_text)

        print(f"Done: {filename} -> {os.path.basename(output_path)}")


if __name__ == "__main__":
    convert_all_docx_to_md("./rawdata")