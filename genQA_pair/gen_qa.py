#!/usr/bin/env python3
"""
genQA_pair/gen_qa.py

Generate QA pairs from legal regulation Markdown files using Gemini API.
Utilises Context Caching to avoid re-uploading the system prompt + full
document on every run, saving input token costs significantly.

Usage:
  python genQA_pair/gen_qa.py --list
  python genQA_pair/gen_qa.py --md_file <filename.md>
  python genQA_pair/gen_qa.py --md_file <filename.md> --runs 5
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

# ─── Paths ────────────────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = ROOT_DIR / "processed_data"
OUTPUT_DIR = ROOT_DIR / "genQA_pair"

# ─── Gemini Model ─────────────────────────────────────────────────────────────
MODEL = "gemini-2.5-flash-lite"

# ─── System Instruction (Design Matrix) ───────────────────────────────────────
SYSTEM_INSTRUCTION = """你是一位專業的法規 QA 資料集生成助理，專門為 TAIDE 大型語言模型的微調訓練產製高品質的法規問答對（QA Pairs）。

## 核心設計標準矩陣

### 任務一：法規草擬（Drafting）

**Input 變異規則（三種型態輪流使用，避免重複）：**

1. **白話文口述型**：模擬長官口頭交辦的語氣。
   - 範例格式：「幫我寫一段 [主題] 的條文，說明 [需求細節]。」

2. **條列重點型**：模擬承辦人整理的業務分工草稿。
   - 範例格式：「[單位A] 負責 [職能1]。[單位B] 負責 [職能2]。請據此草擬條文。」

3. **局部擴寫型**：給定名詞或概念，要求擴寫成標準條文。
   - 範例格式：「請將以下名詞擴寫為本規定的名詞定義條文：[名詞]」

**Output 標準（必須嚴格遵守）：**
- 100% 還原法規原文的層級符號：編（篇）→ 條（一、二、三…）→ 款（（一）（二）…）→ 目（1. 2. 3.…）
- 精準使用來源文件的專屬機關名稱、術語，不得自行替換（例如：「公共關係室（員協中心）」不可寫成「公關部」）
- output 必須是完整的法規條文格式

---

### 任務二：法規審查（Review）

**錯誤注入（Error Injection）規則（必須在 input 中故意植入下列一種或多種錯誤）：**

1. **層級符號錯誤**：將「（一）」寫成「1.」；將「一、」寫成「第一條」；將「第X編」寫成「第X章」
2. **單位名稱錯誤**：將正確的機關或單位名稱故意替換成錯誤名稱
   - 例如：「公共關係室（員協中心）」→「公關部」；「人力資源處」→「人事室」；「工安衛生室」→「安衛科」
3. **專業術語／數值竄改**：將量表分數、法定門檻值、時間期限等關鍵數值故意改錯
4. **體例架構遺漏**：故意刪除某段落中的「目的」、「名詞定義」或「適用對象」等必要條目

**Output 標準（必須嚴格遵守）：**
- 【直接建議】：列點說明每處具體修正建議（原文→應改為）
- 【原因說明】：逐點解釋錯誤原因
- 【法規依據】：指出違反的體例規定或實質規定

---

## 輸出格式（嚴格遵守）

回傳一個合法的 JSON 物件，不得有任何 markdown code fence（不要有 ```json）、不得有前導說明文字，直接以 `{` 開頭，結構如下：

{
  "qa_pairs": [
    {
      "task_type": "drafting",
      "meta_info": {
        "source_document": "<來源文件檔名>",
        "source_article": "<對應的條次或標題，例如：五、權責區分>",
        "generation_strategy": "<說明本題如何設計 input，使用了哪種變異型態>"
      },
      "training_data": {
        "instruction": "<給 TAIDE 的角色扮演指令>",
        "input": "<草擬任務的使用者輸入，模擬口述／條列／擴寫的業務需求>",
        "output": "<符合法制體例的完整標準條文>"
      }
    },
    {
      "task_type": "review",
      "meta_info": {
        "source_document": "<來源文件檔名>",
        "source_article": "<對應的條次或標題>",
        "error_injected": "<條列說明植入了哪些錯誤，以及正確答案>"
      },
      "training_data": {
        "instruction": "<給 TAIDE 的角色扮演指令>",
        "input": "<含有故意錯誤的法規草案片段>",
        "output": "<含【直接建議】【原因說明】【法規依據】三段的標準審查意見>"
      }
    }
  ]
}
"""

# ─── Few-shot Example ─────────────────────────────────────────────────────────
FEW_SHOT_EXAMPLE = """以下是兩筆標準範例，供你對照輸出格式與品質標準：

=== 範例 1：drafting ===
{
  "task_type": "drafting",
  "meta_info": {
    "source_document": "國家中山科學研究院員工心理健康作業規定草案.md",
    "source_article": "五、權責區分",
    "generation_strategy": "條列重點型：提供四個單位的業務分工重點，要求草擬完整的權責區分條文，測試單位名稱與法制作業用語（如：副知、協處）。"
  },
  "training_data": {
    "instruction": "你是一位中科院的法規草擬助理。請根據使用者提供的業務需求，依據本院法規體例格式草擬對應的法規條文。",
    "input": "我們現在要律定員工心理健康的權責區分。總共分四個單位：人資處要在甄試時掌握員工身心狀況；工安衛生室要在巡查時注意員工狀態；醫務所遇到有需求的員工要幫忙轉介；各一級單位主管要主動關懷員工並視需要轉介給公關室。請幫我草擬這部分的條文。",
    "output": "五、權責區分：\n結合人資、工安衛生、醫療、輔導等資源平台，輔導個案或轉介至專業心理諮商或精神醫療之機構，以協助同仁適應生活、維護身心健康，營造互動良好之友善職場。\n（一）人力資源處：於甄試作業及人員試用階段，依本院相關規定選、訓、用、汰、留等作法，訂定誠實條款，掌握員工身心狀況欠佳者，副知用人管理單位並協助完成訓練、任用、考核、汰留等機制。\n（二）工安衛生室：藉平日定期工安巡查時機，協助掌握、發掘員工身心健康狀態，查察員工是否影響工安之心理健康因素，確維職場安全。\n（三）醫務所：協助就診員工評估心理狀況後，有心理輔導需求時，應徵得當事人同意後藉由院內機制，協請單位或轉介專業心輔人員協處。\n（四）各一級單位：\n1. 單位主管應指導所屬二級主管從事初級預防工作之推展，並視員工議題需求轉介公共關係室(員協中心)協處。\n2. 對單位內員工有身心困擾或家庭有重大變故影響工作遂行時，應主動瞭解及穩定員工心緒，予以關懷妥處，並視需要轉介公共關係室(員協中心)輔導。"
  }
}

=== 範例 2：review ===
{
  "task_type": "review",
  "meta_info": {
    "source_document": "國家中山科學研究院員工心理健康作業規定草案.md",
    "source_article": "十二、執行作法（個案分類及輔導權責）",
    "error_injected": "1. 條次編排錯誤（「十二、」寫成「第十二條」）。2. BSRS-5量表C級個案分數寫錯（應為「十至十五分」，誤植為「五至十分」）。3. 單位名稱錯誤（「公共關係室(員協中心)」寫成「公關部」）。"
  },
  "training_data": {
    "instruction": "你是一位中科院的法規審查助理。請檢視以下法規草案片段，標註錯漏之處，並提供符合本院體例的修正建議。",
    "input": "請幫我審查這段輔導權責的草案：\n\n第十二條\n(二) 個案分類及輔導權責：\n1. 個案分類:\n(3)C級：新進適應不佳、生活困擾、家庭及感情困擾、BSRS-5量表五至十分之一般個案。\n2. 輔導權責：\n(3)C級個案由各單位自行輔導管理，並視需求或個案意願轉介公關部輔導。",
    "output": "【直接建議】：\n1. 建議將「第十二條」修正為「十二、執行作法：」。\n2. 建議將個案分類C級之內容修正為「BSRS-5量表十至十五分之一般個案」。\n3. 建議將輔導權責之轉介單位修正為「公共關係室(員協中心)」。\n\n【原因說明】：\n1. 原草案使用「第十二條」不符本院阿拉伯數字加頓號之條次編排體例，且漏列條文標題「執行作法：」。\n2. 關於C級個案之BSRS-5量表分數定義有誤，依標準應為十至十五分。\n3. 本院建制單位名稱為「公共關係室」，無「公關部」之編制。\n\n【法規依據】：違反本院法規體例格式中關於條文編號體例、專有名詞（組織編裝名稱）及心理健康作業規定之實質內容定義。"
  }
}
"""

# ─── Helpers ──────────────────────────────────────────────────────────────────

def list_md_files() -> list[Path]:
    """Return all .md files under processed_data/."""
    return sorted(PROCESSED_DIR.glob("*.md"))


def load_document(md_file: str) -> tuple[str, Path]:
    """Load document text and return (text, path). Exits if file not found."""
    path = PROCESSED_DIR / md_file
    if not path.exists():
        print(f"❌ 找不到檔案：{path}")
        print("可用的檔案：")
        for f in list_md_files():
            print(f"  - {f.name}")
        sys.exit(1)
    text = path.read_text(encoding="utf-8")
    return text, path


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~1.5 Chinese chars per token."""
    return int(len(text) / 1.5)


def get_or_create_cache(
    client: genai.Client,
    display_name: str,
    document_text: str,
) -> tuple[object | None, bool]:
    """
    Try to find an unexpired cache with the given display_name.
    If found, return (cache, True). If not, create a new one and return (cache, False).
    Returns (None, False) if caching fails (e.g. document too short).
    """
    # Check existing caches
    try:
        for cache in client.caches.list():
            if cache.display_name == display_name:
                print(f"♻️  找到既有 cache：{cache.name}（複用，節省 token）")
                return cache, True
    except Exception as e:
        print(f"⚠️  列舉 cache 時發生錯誤：{e}")

    # Build cache contents
    cache_contents = [
        types.Content(
            role="user",
            parts=[
                types.Part(text=FEW_SHOT_EXAMPLE),
                types.Part(text=f"以下是完整的法規文本，請仔細閱讀，後續生成 QA Pairs 時以此為唯一依據：\n\n{document_text}"),
            ],
        ),
        types.Content(
            role="model",
            parts=[types.Part(text="已完整閱讀法規文本與範例，準備好依設計標準生成 QA Pairs。")],
        ),
    ]

    try:
        cache = client.caches.create(
            model=MODEL,
            config=types.CreateCachedContentConfig(
                display_name=display_name,
                system_instruction=SYSTEM_INSTRUCTION,
                contents=cache_contents,
                ttl="3600s",
            ),
        )
        print(f"✅ 已建立新 cache：{cache.name}")
        return cache, False
    except Exception as e:
        print(f"⚠️  建立 cache 失敗（{e}），改用非快取模式")
        return None, False


def build_user_turn(doc_name: str, run_index: int, document_text: str, use_cache: bool) -> str:
    """Build the dynamic user message for each generation run."""
    base = (
        f"請根據以上法規文本（{doc_name}），生成 10 筆 QA Pairs：\n"
        f"- 5 筆 task_type = \"drafting\"（三種 input 變異型態均勻分布）\n"
        f"- 5 筆 task_type = \"review\"（四種錯誤注入樣態均勻分布）\n"
        f"- 每筆的 source_article 必須指向文件中**不同**的條次或款次（避免重複）\n"
        f"- 本輪编號 {run_index}，請從文件中**尚未使用**的條文取材，確保多樣性\n"
        f"- 直接輸出純 JSON，以 {{ 開頭，不得有任何前導文字或 markdown code fence"
    )
    if not use_cache:
        # Non-cached mode: prepend full context
        return (
            f"{FEW_SHOT_EXAMPLE}\n\n"
            f"以下是完整的法規文本：\n\n{document_text}\n\n"
            f"{base}"
        )
    return base


def parse_json_response(raw: str) -> dict:
    """Parse JSON from model response, with fallback regex extraction."""
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Fallback: extract outermost {...}
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"無法解析模型回傳的 JSON，原始內容前 200 字：\n{raw[:200]}")


def append_to_output(output_path: Path, new_pairs: list[dict]) -> int:
    """Append new QA pairs to output JSON file. Returns total count."""
    if output_path.exists():
        existing = json.loads(output_path.read_text(encoding="utf-8"))
        existing_pairs = existing.get("qa_pairs", [])
    else:
        existing_pairs = []

    merged = existing_pairs + new_pairs
    output_path.write_text(
        json.dumps({"qa_pairs": merged}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return len(merged)


def inject_source_document(pairs: list[dict], doc_name: str) -> list[dict]:
    """Ensure every pair has source_document set correctly."""
    for pair in pairs:
        meta = pair.setdefault("meta_info", {})
        meta["source_document"] = doc_name
    return pairs


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    load_dotenv(ROOT_DIR / ".env")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ 找不到 GEMINI_API_KEY，請在專案根目錄建立 .env 檔並設定此變數")
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="從法規 Markdown 生成 QA Pairs（使用 Gemini Context Caching）"
    )
    parser.add_argument(
        "--md_file",
        type=str,
        help="processed_data/ 下的 .md 檔名",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        help="對同一份文件連續生成幾輪（每輪 10 筆），預設 1",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="列出所有可用的 .md 檔後退出",
    )
    args = parser.parse_args()

    # ── --list ────────────────────────────────────────────────────────────────
    if args.list:
        files = list_md_files()
        if not files:
            print("processed_data/ 下沒有任何 .md 檔")
        else:
            print(f"找到 {len(files)} 個可用法規文件：")
            for f in files:
                print(f"  - {f.name}")
        sys.exit(0)

    # ── --md_file required ────────────────────────────────────────────────────
    if not args.md_file:
        files = list_md_files()
        if not files:
            print("processed_data/ 下沒有任何 .md 檔，請先轉換文件")
            sys.exit(1)
        print("請以 --md_file 指定要處理的檔案，可用選項如下：")
        for f in files:
            print(f"  - {f.name}")
        sys.exit(0)

    # ── Load document ─────────────────────────────────────────────────────────
    doc_text, doc_path = load_document(args.md_file)
    doc_name = doc_path.name
    stem = doc_path.stem
    output_path = OUTPUT_DIR / f"{stem}_qa.json"
    OUTPUT_DIR.mkdir(exist_ok=True)

    token_est = estimate_tokens(doc_text)
    print(f"📄 文件：{doc_name}")
    print(f"   字元數：{len(doc_text):,}　預估 token：{token_est:,}")
    print(f"   輸出：{output_path.relative_to(ROOT_DIR)}")
    print(f"   執行輪數：{args.runs} 輪（預計生成 {args.runs * 10} 筆）")
    print()

    # ── Init Gemini client ────────────────────────────────────────────────────
    client = genai.Client(api_key=api_key)

    # ── Context Cache ─────────────────────────────────────────────────────────
    cache_display_name = stem
    cache, cache_reused = get_or_create_cache(client, cache_display_name, doc_text)
    use_cache = cache is not None

    if not use_cache:
        print("📝 將在每次呼叫中直接附上完整文本（非快取模式）")
    print()

    # ── Generation loop ───────────────────────────────────────────────────────
    total_new = 0
    for run in range(1, args.runs + 1):
        print(f"🔄 第 {run}/{args.runs} 輪生成中…")
        user_msg = build_user_turn(doc_name, run, doc_text, use_cache)

        contents = [types.Content(role="user", parts=[types.Part(text=user_msg)])]

        gen_config = types.GenerateContentConfig(
            temperature=0.7,
            response_mime_type="text/plain",
        )
        if use_cache:
            gen_config.cached_content = cache.name

        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=contents,
                config=gen_config,
            )
        except Exception as e:
            print(f"❌ API 呼叫失敗：{e}")
            sys.exit(1)

        # Token usage
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            u = response.usage_metadata
            cached_count = getattr(u, "cached_content_token_count", 0) or 0
            prompt_count = getattr(u, "prompt_token_count", 0) or 0
            output_count = getattr(u, "candidates_token_count", 0) or 0
            print(
                f"   Token 用量 → prompt: {prompt_count}  "
                f"cached: {cached_count}  output: {output_count}"
            )

        # Parse response
        raw_text = response.text or ""
        try:
            result = parse_json_response(raw_text)
        except ValueError as e:
            print(f"❌ {e}")
            sys.exit(1)

        new_pairs = result.get("qa_pairs", [])
        if not new_pairs:
            print("⚠️  模型回傳的 qa_pairs 為空，跳過本輪")
            continue

        new_pairs = inject_source_document(new_pairs, doc_name)
        total = append_to_output(output_path, new_pairs)
        total_new += len(new_pairs)
        print(f"   ✅ 新增 {len(new_pairs)} 筆，累計 {total} 筆")

        if run < args.runs:
            time.sleep(1)  # 避免過快觸發 rate limit

    print()
    print(f"🎉 完成！本次共新增 {total_new} 筆，輸出檔案：{output_path.relative_to(ROOT_DIR)}")


if __name__ == "__main__":
    main()
