import os
import re
import subprocess
from pathlib import Path


def parse_file_to_markdown(file_path: str) -> str:
    """将文件转换为 Markdown。支持 EPUB, PDF, TXT, MD"""
    ext = Path(file_path).suffix.lower()

    if ext == ".epub":
        return parse_epub_to_markdown(file_path)
    elif ext == ".pdf":
        return parse_pdf_to_markdown(file_path)
    elif ext in [".txt", ".md"]:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    else:
        raise ValueError(f"不支持的文件格式: {ext}")


def parse_epub_to_markdown(epub_path: str) -> str:
    """使用 Pandoc 将 EPUB 转换为 Markdown"""
    try:
        result = subprocess.run(
            ["pandoc", epub_path, "-t", "markdown", "--split-level=2"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Pandoc conversion failed: {e.stderr}")
        raise


def parse_pdf_to_markdown(pdf_path: str) -> str:
    """使用 Pandoc 将 PDF 转换为 Markdown"""
    try:
        result = subprocess.run(
            ["pandoc", pdf_path, "-t", "markdown"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Pandoc PDF conversion failed: {e.stderr}")
        raise


def split_markdown_by_chapters(md_content: str) -> dict:
    """根据标题将 Markdown 切分为章节"""
    chapters = {}
    current_chapter = "Preamble"
    content_lines = []

    lines = md_content.splitlines()
    for line in lines:
        # 匹配一级到三级标题
        match = re.match(r"^(#|##|###)\s+(.+)$", line)
        if match:
            if content_lines:
                chapters[current_chapter] = "\n".join(content_lines)

            current_chapter = match.group(2).strip()
            content_lines = [line]
        else:
            content_lines.append(line)

    if content_lines:
        chapters[current_chapter] = "\n".join(content_lines)

    return chapters


def get_book_metadata(file_path: str) -> dict:
    """获取书籍元数据"""
    filename = Path(file_path).stem
    return {"title": filename, "author": "Unknown", "path": file_path}
