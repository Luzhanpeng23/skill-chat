"""
书籍读取模块

支持读取多种格式的书籍文件:
- EPUB
- PDF
- TXT
"""

from pathlib import Path
from typing import Optional


def read_epub(filepath: str) -> str:
    """读取 EPUB 文件

    Args:
        filepath: EPUB 文件路径

    Returns:
        书籍的纯文本内容
    """
    try:
        import ebooklib
        from ebooklib import epub
        from bs4 import BeautifulSoup

        book = epub.read_epub(filepath)
        text_parts = []

        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            soup = BeautifulSoup(item.get_body_content(), 'html.parser')
            text = soup.get_text(separator='\n', strip=True)
            if text:
                text_parts.append(text)

        return '\n\n'.join(text_parts)
    except ImportError:
        print("错误: 需要安装 ebooklib 和 beautifulsoup4")
        print("运行: pip install ebooklib beautifulsoup4")
        raise
    except Exception as e:
        print(f"错误: 读取 EPUB 文件失败: {e}")
        raise


def read_pdf(filepath: str) -> str:
    """读取 PDF 文件

    Args:
        filepath: PDF 文件路径

    Returns:
        书籍的纯文本内容
    """
    try:
        import PyPDF2

        with open(filepath, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            text_parts = []

            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)

            return '\n\n'.join(text_parts)
    except ImportError:
        print("错误: 需要安装 PyPDF2")
        print("运行: pip install PyPDF2")
        raise
    except Exception as e:
        print(f"错误: 读取 PDF 文件失败: {e}")
        raise


def read_txt(filepath: str) -> str:
    """读取 TXT 文件

    Args:
        filepath: TXT 文件路径

    Returns:
        书籍的纯文本内容
    """
    try:
        # 尝试多种编码
        encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1']

        for encoding in encodings:
            try:
                with open(filepath, 'r', encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue

        # 如果所有编码都失败，使用 utf-8 并忽略错误
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception as e:
        print(f"错误: 读取 TXT 文件失败: {e}")
        raise


def read_book(filepath: str) -> str:
    """读取书籍文件，返回纯文本

    Args:
        filepath: 书籍文件路径

    Returns:
        书籍的纯文本内容

    Raises:
        ValueError: 不支持的文件格式
        FileNotFoundError: 文件不存在
    """
    path = Path(filepath)

    # 检查文件是否存在
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {filepath}")

    # 根据文件扩展名选择读取方式
    ext = path.suffix.lower()

    if ext == '.epub':
        return read_epub(filepath)
    elif ext == '.pdf':
        return read_pdf(filepath)
    elif ext == '.txt':
        return read_txt(filepath)
    else:
        raise ValueError(f"不支持的文件格式: {ext}")


def get_book_stats(text: str) -> dict:
    """获取书籍文本的统计信息

    Args:
        text: 书籍文本

    Returns:
        包含统计信息的字典
    """
    lines = text.split('\n')
    words = text.split()

    # 估算中文字符数
    chinese_chars = sum(1 for char in text if '一' <= char <= '鿿')

    return {
        "total_chars": len(text),
        "chinese_chars": chinese_chars,
        "total_lines": len(lines),
        "non_empty_lines": sum(1 for line in lines if line.strip()),
        "estimated_words": len(words)
    }


def split_text_into_chunks(text: str, chunk_size: int = 50000) -> list:
    """将文本分割成块

    用于处理大文件，避免一次性加载到内存

    Args:
        text: 书籍文本
        chunk_size: 每块的字符数

    Returns:
        文本块列表
    """
    chunks = []
    current_pos = 0

    while current_pos < len(text):
        # 找到合适的分割点（在段落边界）
        end_pos = current_pos + chunk_size

        if end_pos < len(text):
            # 尝试在段落边界分割
            while end_pos > current_pos and text[end_pos] != '\n':
                end_pos -= 1

            # 如果找不到段落边界，强制在 chunk_size 处分割
            if end_pos == current_pos:
                end_pos = current_pos + chunk_size

        chunks.append(text[current_pos:end_pos])
        current_pos = end_pos

    return chunks


# 测试代码
if __name__ == "__main__":
    # 测试统计功能
    test_text = """
    这是一段测试文本。
    这是第二行。

    这是新的段落。
    """

    stats = get_book_stats(test_text)
    print("文本统计:")
    print(f"  总字符数: {stats['total_chars']}")
    print(f"  中文字符: {stats['chinese_chars']}")
    print(f"  总行数: {stats['total_lines']}")
    print(f"  非空行数: {stats['non_empty_lines']}")
