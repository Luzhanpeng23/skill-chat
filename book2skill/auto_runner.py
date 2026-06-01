"""
book2skill 全自动执行器
用于在 Claude agent 之外独立运行整个流程

使用方法:
1. 在下方配置区域设置书籍路径和其他参数
2. 运行 python auto_runner.py
"""

import json
import os
import re
from pathlib import Path
from datetime import datetime

# ============================================================
# 配置区域（直接在代码中配置，不依赖环境变量或命令行参数）
# ============================================================

BOOK_PATH = ""  # 书籍文件路径 (PDF/EPUB/TXT)
OUTPUT_DIR = "books"  # 输出目录
AUTO_MODE = True  # True=全自动, False=交互模式
MAX_RETRIES = 3  # 阶段 4 最大回炉次数

# ============================================================
# 元数据提取模块
# ============================================================

def extract_metadata_from_filename(filepath: str) -> dict:
    """从文件名提取书名、作者
    
    支持格式:
    - 书名 (作者) (来源).ext
    - 书名 (作者).ext
    - 书名.ext
    """
    filename = Path(filepath).stem
    
    # 尝试匹配 "书名 (作者) (来源)" 格式
    pattern1 = r'^(.+?)\s*\(([^)]+)\)\s*\(.*\)$'
    match1 = re.match(pattern1, filename)
    if match1:
        return {
            "title": match1.group(1).strip(),
            "author": match1.group(2).strip(),
            "year": "",
            "source_file": filepath
        }
    
    # 尝试匹配 "书名 (作者)" 格式
    pattern2 = r'^(.+?)\s*\(([^)]+)\)$'
    match2 = re.match(pattern2, filename)
    if match2:
        return {
            "title": match2.group(1).strip(),
            "author": match2.group(2).strip(),
            "year": "",
            "source_file": filepath
        }
    
    # 兜底: 只有书名
    return {
        "title": filename.strip(),
        "author": "未知",
        "year": "",
        "source_file": filepath
    }

def extract_metadata_from_epub(filepath: str) -> dict:
    """从 EPUB 元数据提取"""
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
            "year": date[0][0][:4] if date else "",
            "source_file": filepath
        }
    except Exception:
        return {}

def extract_metadata_from_pdf(filepath: str) -> dict:
    """从 PDF 元数据提取"""
    try:
        import PyPDF2
        
        with open(filepath, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            info = reader.metadata
            
            return {
                "title": info.title if info else "",
                "author": info.author if info else "",
                "year": str(info.creation_date.year) if info and info.creation_date else "",
                "source_file": filepath
            }
    except Exception:
        return {}

def extract_metadata(filepath: str) -> dict:
    """提取书籍元数据，按优先级尝试多种方式"""
    metadata = {}
    
    # 1. 尝试从文件格式特定的元数据提取
    ext = Path(filepath).suffix.lower()
    if ext == '.epub':
        metadata = extract_metadata_from_epub(filepath)
    elif ext == '.pdf':
        metadata = extract_metadata_from_pdf(filepath)
    
    # 2. 如果提取失败或为空，从文件名提取
    if not metadata.get('title'):
        metadata = extract_metadata_from_filename(filepath)
    
    # 3. 确保所有必要字段存在
    metadata.setdefault('title', '未知书名')
    metadata.setdefault('author', '未知作者')
    metadata.setdefault('year', '')
    metadata.setdefault('source_file', filepath)
    
    return metadata

def generate_slug(title: str) -> str:
    """从书名生成目录标识"""
    # 移除特殊字符，转换为小写，用连字符连接
    slug = re.sub(r'[^\w\s-]', '', title.lower())
    slug = re.sub(r'[-\s]+', '-', slug).strip('-')
    return slug[:50]  # 限制长度

# ============================================================
# 书籍读取模块
# ============================================================

def read_book(filepath: str) -> str:
    """读取书籍文件，返回纯文本"""
    ext = Path(filepath).suffix.lower()
    
    if ext == '.epub':
        return read_epub(filepath)
    elif ext == '.pdf':
        return read_pdf(filepath)
    elif ext == '.txt':
        return read_txt(filepath)
    else:
        raise ValueError(f"不支持的文件格式: {ext}")

def read_epub(filepath: str) -> str:
    """读取 EPUB 文件"""
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
        print("需要安装 ebooklib 和 beautifulsoup4: pip install ebooklib beautifulsoup4")
        raise

def read_pdf(filepath: str) -> str:
    """读取 PDF 文件"""
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
        print("需要安装 PyPDF2: pip install PyPDF2")
        raise

def read_txt(filepath: str) -> str:
    """读取 TXT 文件"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()

# ============================================================
# 流程控制模块
# ============================================================

def create_output_structure(output_dir: str, slug: str) -> str:
    """创建输出目录结构"""
    book_dir = Path(output_dir) / slug
    book_dir.mkdir(parents=True, exist_ok=True)
    
    # 创建子目录
    (book_dir / "candidates").mkdir(exist_ok=True)
    (book_dir / "rejected").mkdir(exist_ok=True)
    
    return str(book_dir)

def save_metadata(book_dir: str, metadata: dict):
    """保存元数据到文件"""
    metadata_path = Path(book_dir) / "metadata.json"
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

def generate_book_overview(book_dir: str, metadata: dict, book_text: str):
    """生成 BOOK_OVERVIEW.md (占位函数，实际需要调用 AI)"""
    # TODO: 这里需要调用 AI 来执行 Adler 分析
    # 目前生成一个占位文件
    
    overview_path = Path(book_dir) / "BOOK_OVERVIEW.md"
    
    content = f"""# {metadata['title']} — 整书理解 (阶段 0 产出)

> 本文档是 book2skill 流水线的阶段 0 产出, 后续所有 extractor 和 skill 都以此为全局上下文。

## 基本信息

- **书名**: {metadata['title']}
- **作者**: {metadata['author']}
- **出版年**: {metadata['year'] or '未知'}
- **版本来源**: {metadata['source_file']}
- **处理时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 1. 结构 (Structural)

### 类型
{{ 待分析 }}

### 一句话主旨
{{ 待分析 }}

### 骨架 (主要论点及其关系)

{{ 待分析 }}

### 作者要解决的核心问题
{{ 待分析 }}

---

## 2. 解释 (Interpretive)

### 关键术语 (作者本人的用法)

{{ 待分析 }}

### 核心命题 (用自己的话)

{{ 待分析 }}

### 论证链
{{ 待分析 }}

---

## 3. 批判 (Critical) ★

### 作者的时代局限
{{ 待分析 }}

### 作者的立场盲点
{{ 待分析 }}

### 未被证明的假设
{{ 待分析 }}

### 最强反对意见
{{ 待分析 }}

---

## 4. 应用潜力 (Applicability)

### 可 skill 化的内容
{{ 待分析 }}

### 不适合 skill 化的内容
{{ 待分析 }}

### 预估 skill 数量
**约 {{N}} 个**

### 优先级排序
{{ 待分析 }}

---

## ✅ 质量门检查

- [ ] 主旨能用一句话说清
- [ ] 骨架列出 3–7 个一级论点
- [ ] 关键术语词典 ≥5 条
- [ ] 批判阶段列出 ≥3 条作者局限
- [ ] 已向用户展示并得到确认
"""
    
    with open(overview_path, 'w', encoding='utf-8') as f:
        f.write(content)

def log_progress(book_dir: str, stage: str, message: str):
    """记录进度日志"""
    log_path = Path(book_dir) / "progress.log"
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] [{stage}] {message}\n")

# ============================================================
# 主流程
# ============================================================

def main():
    """主流程"""
    print("=" * 60)
    print("book2skill 全自动执行器")
    print("=" * 60)
    
    # 检查配置
    if not BOOK_PATH:
        print("错误: 请在配置区域设置 BOOK_PATH")
        return
    
    if not Path(BOOK_PATH).exists():
        print(f"错误: 文件不存在: {BOOK_PATH}")
        return
    
    print(f"\n书籍路径: {BOOK_PATH}")
    print(f"输出目录: {OUTPUT_DIR}")
    print(f"执行模式: {'全自动' if AUTO_MODE else '交互'}")
    print(f"最大重试: {MAX_RETRIES} 次")
    print()
    
    # 1. 提取元数据
    print("步骤 1: 提取书籍元数据...")
    metadata = extract_metadata(BOOK_PATH)
    slug = generate_slug(metadata['title'])
    
    print(f"  书名: {metadata['title']}")
    print(f"  作者: {metadata['author']}")
    print(f"  标识: {slug}")
    
    # 2. 创建输出目录
    print("\n步骤 2: 创建输出目录结构...")
    book_dir = create_output_structure(OUTPUT_DIR, slug)
    save_metadata(book_dir, metadata)
    print(f"  输出目录: {book_dir}")
    
    # 3. 读取书籍
    print("\n步骤 3: 读取书籍内容...")
    book_text = read_book(BOOK_PATH)
    print(f"  文本长度: {len(book_text)} 字符")
    
    # 4. 阶段 0: Adler 分析
    print("\n步骤 4: 执行阶段 0 - Adler 分析...")
    log_progress(book_dir, "阶段 0", "开始 Adler 分析")
    generate_book_overview(book_dir, metadata, book_text)
    log_progress(book_dir, "阶段 0", "生成 BOOK_OVERVIEW.md (占位)")
    
    if not AUTO_MODE:
        # 交互模式: 等待用户确认
        print("\n  请查看 BOOK_OVERVIEW.md 并确认骨架理解是否正确。")
        input("  按 Enter 继续...")
    
    # 5. 阶段 1: 并行提取
    print("\n步骤 5: 执行阶段 1 - 并行提取...")
    log_progress(book_dir, "阶段 1", "开始并行提取")
    # TODO: 调用 5 个 extractor sub-agent
    print("  (待实现: 调用 5 个 extractor sub-agent)")
    
    # 6. 阶段 1.5: 三重验证
    print("\n步骤 6: 执行阶段 1.5 - 三重验证...")
    log_progress(book_dir, "阶段 1.5", "开始三重验证")
    # TODO: 执行 V1/V2/V3 验证
    print("  (待实现: 执行三重验证)")
    
    # 7. 阶段 1.75: 真实场景映射
    print("\n步骤 7: 执行阶段 1.75 - 真实场景映射...")
    log_progress(book_dir, "阶段 1.75", "开始真实场景映射")
    # TODO: 映射到现代生活场景
    print("  (待实现: 真实场景映射)")
    
    # 8. 阶段 2: RIA++ 构造
    print("\n步骤 8: 执行阶段 2 - RIA++ 构造...")
    log_progress(book_dir, "阶段 2", "开始 RIA++ 构造")
    # TODO: 生成 SKILL.md
    print("  (待实现: 生成 SKILL.md)")
    
    # 9. 阶段 3: Zettelkasten 链接
    print("\n步骤 9: 执行阶段 3 - Zettelkasten 链接...")
    log_progress(book_dir, "阶段 3", "开始 Zettelkasten 链接")
    # TODO: 建立 skill 之间的关系
    print("  (待实现: 建立 skill 关系)")
    
    # 10. 阶段 4: 压力测试
    print("\n步骤 10: 执行阶段 4 - 压力测试...")
    log_progress(book_dir, "阶段 4", "开始压力测试")
    # TODO: 生成测试用例并执行
    print("  (待实现: 压力测试)")
    
    # 完成
    print("\n" + "=" * 60)
    print("执行完成!")
    print("=" * 60)
    print(f"\n输出目录: {book_dir}")
    print("\n后续步骤:")
    print("1. 查看 BOOK_OVERVIEW.md 确认骨架理解")
    print("2. 查看 candidates/ 目录中的候选单元")
    print("3. 查看各 skill 目录中的 SKILL.md")
    print("4. 如需持续进化, 可喂给 darwin-skill:")
    print(f"   darwin evolve {book_dir}/")
    
    log_progress(book_dir, "完成", "全流程执行完成")

if __name__ == "__main__":
    main()
