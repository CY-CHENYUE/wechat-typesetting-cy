#!/usr/bin/env python3
"""完整性校验：原文内容必须完整出现在排版输出里（排版不是编辑）。

用法: python3 verify-completeness.py <原文.md/.txt> <输出.html>
通过: 退出码 0
失败: 退出码 1，并列出输出里找不到的原文子句（说明被删改/改写）

校验粒度是"子句"（按 。！？；：换行 切分）：
- 对排版重组（拆段、枚举句拆成多行、标签去尾冒号）天然鲁棒
- 对删句、改字、换词、改句内标点零容忍
被跳过的内容（属于排版转化，不算正文）：媒体标记行（【图/【视频/![]()）、
Markdown 语法记号（#、-、>、**、`）、枚举词前缀（"步骤一："）、长度 < 4 的碎片。
"""
import html as html_mod
import re
import sys
from pathlib import Path


def normalize(text):
    """去掉所有空白——排版会任意重排空格与换行。"""
    return re.sub(r'\s+', '', text)


def is_media_line(line):
    s = line.strip()
    if re.match(r'^!\[[^\]]*\]\([^)]*\)\s*$', s):
        return True
    if re.match(r'^[【\[（(]\s*(图|视频|音频|配图|封面)\s*[\d一二三四五六七八九十]*\s*[：:、]', s):
        return True
    if re.match(r'^（?此处(放|配|插)(图|视频)', s):
        return True
    if re.match(r'^https?://\S+$', s):
        return True
    return False


def strip_markdown(line):
    s = line.strip()
    s = re.sub(r'^#{1,6}\s*', '', s)          # 标题记号
    s = re.sub(r'^>\s*', '', s)               # 引用记号
    s = re.sub(r'^[-*+]\s+', '', s)           # 无序列表
    s = re.sub(r'^\d+[.、)]\s*', '', s)       # 有序列表
    s = re.sub(r'\*\*([^*]+)\*\*', r'\1', s)  # 粗体
    s = re.sub(r'\*([^*]+)\*', r'\1', s)      # 斜体
    s = re.sub(r'`([^`]+)`', r'\1', s)        # 行内代码
    s = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', s)        # 行内图片
    s = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', s)    # 链接 → 链接文字
    # 枚举词前缀（转为版式编号属于排版）
    s = re.sub(r'^(步骤|第)\s*[\d一二三四五六七八九十]+\s*[步章节条款]?\s*[：:.、]\s*', '', s)
    return s


def source_clauses(text):
    """原文 → 需逐一核验的子句列表 [(行号, 子句)]。"""
    clauses = []
    for idx, raw in enumerate(text.splitlines(), 1):
        if not raw.strip() or is_media_line(raw):
            continue
        line = strip_markdown(raw)
        for piece in re.split(r'[。！？；：!?;\n]', line):
            piece = piece.strip().strip('"""\'「」『』')
            if len(normalize(piece)) >= 4:
                clauses.append((idx, piece))
    return clauses


def output_text(html):
    """输出 HTML → 纯文本（去注释/脚本/样式/标签，解实体）。"""
    s = re.sub(r'<!--.*?-->', '', html, flags=re.S)
    s = re.sub(r'<script.*?</script>', '', s, flags=re.S | re.I)
    s = re.sub(r'<style.*?</style>', '', s, flags=re.S | re.I)
    s = re.sub(r'<[^>]+>', '', s)
    return normalize(html_mod.unescape(s))


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    src = Path(sys.argv[1]).read_text(encoding='utf-8', errors='replace')
    out = output_text(Path(sys.argv[2]).read_text(encoding='utf-8', errors='replace'))

    clauses = source_clauses(src)
    missing = [(ln, c) for ln, c in clauses if normalize(c) not in out]

    print(f'完整性校验：原文子句 {len(clauses)} 条，命中 {len(clauses) - len(missing)} 条')
    if missing:
        print(f'\n✗ 未通过：{len(missing)} 条原文内容在输出中找不到（被删改/改写）——')
        for ln, c in missing:
            print(f'  原文第 {ln} 行: {c[:60]}')
        sys.exit(1)
    print('✓ 通过：原文内容完整在场，未发现删改')
    sys.exit(0)


if __name__ == '__main__':
    main()
