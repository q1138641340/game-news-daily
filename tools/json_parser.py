"""
安全的 JSON 解析工具
处理 LLM 返回的各种格式问题
"""

import json
import re
from typing import Any
from pydantic import BaseModel, ValidationError
from typing import List, Optional


def parse_json(text: str) -> dict | list:
    """
    安全解析 LLM 返回的 JSON

    处理情况：
    - 代码块包裹（```json ... ```）
    - 普通代码块（``` ... ```）
    - 尾部逗号
    - 中文引号
    - 格式错误

    Args:
        text: LLM 返回的文本

    Returns:
        解析后的 JSON 对象（dict 或 list）

    Raises:
        ValueError: 无法解析时抛出
    """
    if not text:
        raise ValueError("Empty input")

    # 去除首尾空白
    text = text.strip()

    # 去除代码块包裹
    text = re.sub(r'^```json\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^```\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*```$', '', text, flags=re.IGNORECASE)

    # 去除首尾空白（去代码块后可能产生）
    text = text.strip()

    # 修复常见格式问题
    # 1. 尾部逗号
    text = re.sub(r',(\s*[}\]])', r'\1', text)

    # 2. 中文引号
    text = text.replace('"', '"').replace('"', '"')

    # 3. 移除多余空白行
    text = re.sub(r'\n\s*\n', '\n', text)

    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试修复更多问题
    # 4. 单引号转双引号（简单场景）
    #    需要先转义已存在的双引号
    def quote_replacer(match):
        inner = match.group(1)
        # 确保内部的双引号被转义
        inner = inner.replace('"', '\\"')
        return f'"{inner}"'

    # 只在 JSON 外层对象/数组明显损坏时尝试修复
    # 移除所有换行符后的文本
    compact = re.sub(r'\s+', ' ', text)

    try:
        return json.loads(compact)
    except json.JSONDecodeError:
        pass

    # 最后尝试：去除所有非JSON字符
    # 找到第一个 { 或 [ 和最后一个 } 或 ]
    start = text.find('{')
    if start == -1:
        start = text.find('[')

    end = text.rfind('}')
    if end == -1:
        end = text.rfind(']')

    if start != -1 and end != -1 and end > start:
        cleaned = text[start:end+1]
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

    # 尝试提取 <think> 标签后的 JSON（MiniMax 等模型的思考过程会包裹 JSON）
    think_match = re.search(r'<think>\s*(.+?)\s*</think>', text, re.DOTALL)
    if think_match:
        think_content = think_match.group(1)
        # 递归尝试解析思考内容中的 JSON
        try:
            return parse_json(think_content)
        except ValueError:
            pass

    raise ValueError(f"Cannot parse JSON from: {text[:200]}...")


def parse_json_with_model(text: str, model: type[BaseModel]) -> List[BaseModel]:
    """
    解析 JSON 并用 Pydantic 模型验证

    Args:
        text: LLM 返回的文本
        model: Pydantic 模型类

    Returns:
        验证后的模型实例列表
    """
    raw = parse_json(text)

    # 确保是列表
    if isinstance(raw, dict):
        raw = [raw]

    results = []
    for item in raw:
        try:
            results.append(model(**item))
        except ValidationError as e:
            print(f"Validation error: {e}")
            continue

    return results


# 常用数据模型
class NewsItem(BaseModel):
    """新闻条目"""
    title: str
    summary: str
    source: str
    url: str
    date: str
    category: Optional[str] = None
    tags: Optional[List[str]] = []


class PaperItem(BaseModel):
    """学术论文条目"""
    title: str
    authors: str
    abstract: str
    url: str
    doi: Optional[str] = None
    published_date: Optional[str] = None
    venue: Optional[str] = None  # 期刊/会议名称
    pdf_url: Optional[str] = None


class ReviewResult(BaseModel):
    """审查结果"""
    url: str
    approved: bool
    quality_score: Optional[float] = None
    relevance_score: Optional[float] = None
    reason: str
    priority: Optional[str] = None  # high/medium/low