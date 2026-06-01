"""
书籍元数据提取模块

支持从多种来源提取书籍元数据:
- 文件名解析
- EPUB 元数据
- PDF 元数据
"""

import re
from pathlib import Path
from typing import Optional


def extract_from_filename(filepath: str) -> dict:
    """从文件名提取书名、作者

    支持格式:
    - 书名 (作者) (来源).ext
    - 书名 (作者).ext
    - 书名.ext

    Args:
        filepath: 文件路径

    Returns:
        包含 title, author 的字典
    """
    filename = Path(filepath).stem

    # 尝试匹配 "书名 (作者) (来源)" 格式
    pattern1 = r'^(.+?)\s*\(([^)]+)\)\s*\(.*\)$'
    match1 = re.match(pattern1, filename)
    if match1:
        return {
            "title": match1.group(1).strip(),
            "author": match1.group(2).strip()
        }

    # 尝试匹配 "书名 (作者)" 格式
    pattern2 = r'^(.+?)\s*\(([^)]+)\)$'
    match2 = re.match(pattern2, filename)
    if match2:
        return {
            "title": match2.group(1).strip(),
            "author": match2.group(2).strip()
        }

    # 兜底: 只有书名
    return {
        "title": filename.strip(),
        "author": ""
    }


def extract_from_epub(filepath: str) -> dict:
    """从 EPUB 元数据提取

    Args:
        filepath: EPUB 文件路径

    Returns:
        包含 title, author, year 的字典
    """
    try:
        import ebooklib
        from ebooklib import epub

        book = epub.read_epub(filepath)

        title = book.get_metadata('DC', 'title')
        creator = book.get_metadata('DC', 'creator')
        date = book.get_metadata('DC', 'date')

        return {
            "title": title[0][0] if title else "",
            "author": creator[0][0] if creator else "",
            "year": date[0][0][:4] if date else ""
        }
    except ImportError:
        print("警告: 需要安装 ebooklib 才能读取 EPUB 元数据")
        print("运行: pip install ebooklib")
        return {}
    except Exception as e:
        print(f"警告: 读取 EPUB 元数据失败: {e}")
        return {}


def extract_from_pdf(filepath: str) -> dict:
    """从 PDF 元数据提取

    Args:
        filepath: PDF 文件路径

    Returns:
        包含 title, author, year 的字典
    """
    try:
        import PyPDF2

        with open(filepath, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            info = reader.metadata

            if info:
                year = ""
                if info.creation_date:
                    year = str(info.creation_date.year)

                return {
                    "title": info.title or "",
                    "author": info.author or "",
                    "year": year
                }
            return {}
    except ImportError:
        print("警告: 需要安装 PyPDF2 才能读取 PDF 元数据")
        print("运行: pip install PyPDF2")
        return {}
    except Exception as e:
        print(f"警告: 读取 PDF 元数据失败: {e}")
        return {}


def extract_metadata(filepath: str) -> dict:
    """提取书籍元数据，按优先级尝试多种方式

    优先级:
    1. 文件格式特定的元数据 (EPUB/PDF)
    2. 文件名解析
    3. 兜底默认值

    Args:
        filepath: 文件路径

    Returns:
        包含 title, author, year, source_file 的字典
    """
    metadata = {}

    # 1. 尝试从文件格式特定的元数据提取
    ext = Path(filepath).suffix.lower()
    if ext == '.epub':
        metadata = extract_from_epub(filepath)
    elif ext == '.pdf':
        metadata = extract_from_pdf(filepath)

    # 2. 如果提取失败或为空，从文件名提取
    if not metadata.get('title'):
        filename_metadata = extract_from_filename(filepath)
        metadata.update(filename_metadata)

    # 3. 确保所有必要字段存在
    metadata.setdefault('title', '未知书名')
    metadata.setdefault('author', '未知作者')
    metadata.setdefault('year', '')
    metadata.setdefault('source_file', filepath)

    return metadata


def generate_slug(title: str) -> str:
    """从书名生成目录标识

    Args:
        title: 书名

    Returns:
        适合用作目录名的标识符
    """
    # 移除特殊字符，转换为小写，用连字符连接
    slug = re.sub(r'[^\w\s-]', '', title.lower())
    slug = re.sub(r'[-\s]+', '-', slug).strip('-')
    return slug[:50]  # 限制长度


# 测试代码
if __name__ == "__main__":
    # 测试文件名解析
    test_cases = [
        "孙子兵法·三十六计谋略全本 (【春秋】孙武) (z-library.sk, 1lib.sk, z-lib.sk).epub",
        "穷查理宝典 (查理·芒格).pdf",
        "如何阅读一本书.txt",
        "思考，快与慢 (丹尼尔·卡尼曼) (Kindle).epub"
    ]

    print("测试文件名解析:")
    print("-" * 60)
    for test_case in test_cases:
        result = extract_from_filename(test_case)
        print(f"文件名: {test_case}")
        print(f"提取结果: {result}")
        print()
