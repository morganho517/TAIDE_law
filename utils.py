"""
utils.py - 掃描 rawdata 目錄，回傳檔案路徑 List
"""

from pathlib import Path

RAWDATA_DIR = Path(__file__).parent / "rawdata"

SUPPORTED_EXTENSIONS = {".doc", ".docx", ".pdf", ".xlsx", ".7z"}


def get_all_file_paths(
    root: Path = RAWDATA_DIR,
    extensions: set[str] | None = None,
) -> list[Path]:
    """
    遞迴掃描 root 目錄，回傳所有符合副檔名的檔案路徑 List。
    自動排除 Word 暫存鎖定檔（檔名以 ~$ 開頭）。

    Args:
        root:       掃描根目錄，預設為 rawdata/
        extensions: 要篩選的副檔名集合（含點號，如 {".docx", ".doc"}）；
                    傳入 None 表示回傳所有檔案。

    Returns:
        排序後的 Path 物件 List
    """
    paths = [
        p for p in root.rglob("*")
        if p.is_file()
        and not p.name.startswith("~$")
        and (extensions is None or p.suffix.lower() in extensions)
    ]
    return sorted(paths)


def get_main_process_paths(extensions: set[str] | None = {".doc", ".docx"}) -> list[Path]:
    """回傳「主流程法規」目錄下的檔案路徑 List。"""
    return get_all_file_paths(RAWDATA_DIR / "主流程法規", extensions)


def get_sub_process_paths(extensions: set[str] | None = {".doc", ".docx"}) -> list[Path]:
    """回傳「副流程文件」目錄下的檔案路徑 List。"""
    return get_all_file_paths(RAWDATA_DIR / "副流程文件", extensions)


if __name__ == "__main__":
    main_paths = get_main_process_paths()
    sub_paths = get_sub_process_paths()

    print(f"=== 主流程法規 ({len(main_paths)} 個檔案) ===")
    for p in main_paths:
        print(p)

    print(f"\n=== 副流程文件 ({len(sub_paths)} 個檔案) ===")
    for p in sub_paths:
        print(p)

    print(f"\n合計：{len(main_paths) + len(sub_paths)} 個檔案")
