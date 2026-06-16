#!/usr/bin/env python3
"""微信兼容自动检查：扫描排版输出 HTML 的复制内容区，核对 wechat-compat.md 的硬规则。

用法: python3 verify-wechat-compat.py <输出.html>
通过: 退出码 0
失败: 退出码 1，并列出违规项

只检查会被复制进公众号的内容区（#wechat-content 内，或 body 去掉 script/style），
预览外壳本身的 flex/script 不算违规。HTML 注释里出现的关键词（如风格注释里写了
"渐变"）也不算违规——CSS 规则在去掉注释后的文本上检查。
"""
import re
import sys
from html.parser import HTMLParser
from pathlib import Path


class ContentExtractor(HTMLParser):
    """提取 id=wechat-content 的 div 内部 HTML（深度跟踪嵌套 div）。"""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.depth = None
        self.parts = []
        self.found = False
        self.done = False

    def handle_starttag(self, tag, attrs):
        if self.done:
            return
        if self.depth is None:
            if tag == 'div' and ('id', 'wechat-content') in attrs:
                self.depth = 1
                self.found = True
            return
        if tag == 'div':
            self.depth += 1
        self.parts.append(self.get_starttag_text())

    def handle_startendtag(self, tag, attrs):
        if self.depth is not None and not self.done:
            self.parts.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        if self.depth is None or self.done:
            return
        if tag == 'div':
            self.depth -= 1
            if self.depth == 0:
                self.done = True
                return
        self.parts.append(f'</{tag}>')

    def handle_data(self, data):
        if self.depth is not None and not self.done:
            self.parts.append(data)

    def handle_comment(self, comment):
        if self.depth is not None and not self.done:
            self.parts.append(f'<!--{comment}-->')


def extract_content(html: str) -> str:
    """复制进公众号的内容区：优先 #wechat-content，否则 body 去掉 script/style。"""
    if 'id="wechat-content"' in html:
        parser = ContentExtractor()
        parser.feed(html)
        if parser.found and parser.parts:
            return ''.join(parser.parts)
    body = re.search(r'<body[^>]*>(.*)</body>', html, re.S)
    segment = body.group(1) if body else html
    segment = re.sub(r'<script.*?</script>', '', segment, flags=re.S | re.I)
    segment = re.sub(r'<style.*?</style>', '', segment, flags=re.S | re.I)
    return segment


def run_checks(html: str, content: str, name: str):
    # CSS/标签规则在去掉 HTML 注释后的文本上检查（注释里的词不算违规）
    css = re.sub(r'<!--.*?-->', '', content, flags=re.S)
    checks = []

    def add(text, ok, evidence):
        checks.append((text, bool(ok), str(evidence)))

    add('内容区含中文', re.search(r'[一-鿿]', content), f'{name}，内容区 {len(content)} 字符')

    n = content.count('style=')
    add('全内联样式（style= ≥ 20 处）', n >= 20, f'style= 出现 {n} 次')

    m = re.search(r'display\s*:\s*(flex|grid)', css)
    add('无 flex/grid 布局（微信粘贴后会塌，多列用 table）', not m, m.group(0) if m else '未检出')

    m = re.search(r'(position\s*:|float\s*:|transform\s*:|animation\s*:|transition\s*:)', css)
    add('无 position/float/transform/animation/transition', not m, m.group(0) if m else '未检出')

    m = re.search(r'gradient', css, re.I)
    add('无渐变（微信不渲染，用实色）', not m, '检出 gradient' if m else '未检出')

    m = re.search(r'background(-color)?\s*:\s*rgba', css)
    add('背景色无 rgba()（微信不渲染 rgba 背景；文字色 rgba 安全）', not m, m.group(0) if m else '未检出')

    m = re.search(r'background(-color)?\s*:\s*#fff(?:fff)?\s*[;"\s]', css, re.I)
    add('无纯白 #fff/#ffffff 背景（会被过滤，纯白用 #fefefe）', not m, m.group(0) if m else '未检出')

    m = re.search(r'<(ul|ol|li)[\s>]', css)
    add('无裸 ul/ol/li（部分端样式丢失，列表用 p+span）', not m, m.group(0) if m else '未检出')

    m = re.search(r'<h[1-6][\s>]', css)
    add('无 h1-h6 标签（编辑器默认样式会干扰）', not m, m.group(0) if m else '未检出')

    m = re.search(r'<script', css, re.I)
    add('复制内容区无 <script>', not m, '检出 script' if m else '未检出')

    m = re.search(r'<(video|iframe|audio)[\s>]', css, re.I)
    add('无 video/iframe/audio（粘贴会被剥掉，视频用占位块）', not m, m.group(0) if m else '未检出')

    # 整页深色 → 须用 table 骨架（粗略判断：内容区 outer 用了深底色但没 table）
    outer = re.search(r'data-role="outer"[^>]*background-color:\s*(#[0-9a-fA-F]{6})', content)
    if outer:
        hexv = outer.group(1).lstrip('#')
        dark = sum(int(hexv[i:i+2], 16) for i in (0, 2, 4)) / 3 < 80
        if dark:
            add('深色整页用了 table 骨架（防 section 间白缝）', '<table' in css, '深底 outer 但未见 table' if '<table' not in css else 'table 在场')

    # 技能输出约定（非兼容硬规则，但本技能产物应满足）
    sc = re.search(r'<!--\s*风格方向[:：]', content)
    add('含机器可读风格注释（<!-- 风格方向: … -->）', sc, '在场' if sc else '未找到')

    return checks


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    path = Path(sys.argv[1])
    if not path.is_file():
        print(f'✗ 文件不存在: {path}')
        sys.exit(2)
    html = path.read_text(encoding='utf-8', errors='replace')
    content = extract_content(html)
    checks = run_checks(html, content, path.name)

    fails = [c for c in checks if not c[1]]
    print(f'微信兼容检查：{len(checks) - len(fails)}/{len(checks)} 通过　（{path.name}）')
    for text, ok, ev in checks:
        if not ok:
            print(f'  ✗ {text}　←　{ev}')
    if fails:
        print(f'\n✗ 未通过 {len(fails)} 项，修复后重跑')
        sys.exit(1)
    print('✓ 全部通过')
    sys.exit(0)


if __name__ == '__main__':
    main()
