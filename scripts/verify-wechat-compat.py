#!/usr/bin/env python3
"""检查复制区的微信兼容硬规则。

默认只检查唯一的 ``#wechat-content``。检查裸 HTML 片段时显式使用：

    python3 verify-wechat-compat.py --fragment fragment.html

通过返回 0；兼容硬伤返回 1；参数、文件或复制边界错误返回 2。
预览外壳中的 CSS、脚本和交互控件不属于复制内容，不参与检查。
"""

import argparse
import re
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from wechat_html import (
    VOID_ELEMENTS,
    attrs_first_wins,
    get_copy_html,
    parse_inline_style,
)


FORBIDDEN_TAGS = {
    "style",
    "script",
    "link",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "ul",
    "ol",
    "li",
    "pre",
    "code",
    "video",
    "iframe",
    "audio",
    "svg",
    "canvas",
    "form",
    "input",
}
FORBIDDEN_LAYOUT_PROPERTIES = {
    "position",
    "float",
    "transform",
    "-webkit-transform",
    "-moz-transform",
    "-ms-transform",
    "z-index",
}
BLOCK_TAGS = {"section", "p", "div", "table"}


@dataclass
class Node:
    tag: str
    attrs: dict
    style: dict
    line: int
    parent: Optional[int]
    text: str = ""
    direct_text: str = ""


class ContentInspector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.nodes = []
        self.stack = []
        self.text = []
        self.duplicate_attrs = []

    def _add_node(self, tag, attrs):
        tag = tag.lower()
        raw_attrs, duplicates = attrs_first_wins(attrs)
        attrs_dict = {
            key: "" if value is None else str(value)
            for key, value in raw_attrs.items()
        }
        if duplicates:
            self.duplicate_attrs.append(
                f"第 {self.getpos()[0]} 行 <{tag}>："
                + ", ".join(sorted(set(duplicates)))
            )
        node = Node(
            tag=tag,
            attrs=attrs_dict,
            style=parse_inline_style(attrs_dict.get("style", "")),
            line=self.getpos()[0],
            parent=self.stack[-1] if self.stack else None,
        )
        self.nodes.append(node)
        return len(self.nodes) - 1

    def handle_starttag(self, tag, attrs):
        index = self._add_node(tag, attrs)
        if tag.lower() not in VOID_ELEMENTS:
            self.stack.append(index)

    def handle_startendtag(self, tag, attrs):
        self._add_node(tag, attrs)

    def handle_endtag(self, tag):
        tag = tag.lower()
        for offset in range(len(self.stack) - 1, -1, -1):
            if self.nodes[self.stack[offset]].tag == tag:
                del self.stack[offset:]
                return

    def handle_data(self, data):
        self.text.append(data)
        if self.stack:
            self.nodes[self.stack[-1]].direct_text += data
        for index in self.stack:
            self.nodes[index].text += data


def _clean_value(value):
    return re.sub(r"\s*!\s*important\s*$", "", value.strip(), flags=re.I).lower()


def _describe(items, limit=4):
    if not items:
        return "未检出"
    shown = []
    for item in items[:limit]:
        if isinstance(item, Node):
            shown.append(f"第 {item.line} 行 <{item.tag}>")
        else:
            shown.append(str(item))
    if len(items) > limit:
        shown.append(f"另 {len(items) - limit} 处")
    return "；".join(shown)


def _uses_alpha_color(value):
    clean = _clean_value(value)
    return bool(
        clean == "transparent"
        or re.search(r"\b(?:rgba|hsla)\s*\(", clean)
        or re.search(r"\b(?:rgb|hsl)\s*\([^)]*/", clean)
        or re.search(
            r"(?<![0-9a-f])#(?:[0-9a-f]{4}|[0-9a-f]{8})(?![0-9a-f])",
            clean,
        )
    )


def _is_fully_transparent_color(value):
    clean = _clean_value(value)
    return bool(
        clean == "transparent"
        or re.fullmatch(
            r"rgba\([^,]+,[^,]+,[^,]+,\s*0(?:\.0+)?\s*\)",
            clean,
        )
        or re.fullmatch(
            r"(?:rgb|hsl)\([^)]*/\s*0(?:\.0+)?%?\s*\)",
            clean,
        )
        or re.fullmatch(r"#[0-9a-f]{6}00", clean)
        or re.fullmatch(r"#[0-9a-f]{3}0", clean)
    )


def _is_descendant(nodes, node_index, ancestor_index):
    parent = nodes[node_index].parent
    while parent is not None:
        if parent == ancestor_index:
            return True
        parent = nodes[parent].parent
    return False


def _parse_hex_color(value):
    match = re.fullmatch(r"\s*#([0-9a-fA-F]{6})\s*", value or "")
    if not match:
        return None
    raw = match.group(1)
    return tuple(int(raw[index : index + 2], 16) for index in (0, 2, 4))


def run_checks(content, name):
    inspector = ContentInspector()
    inspector.feed(content)
    nodes = inspector.nodes
    checks = []
    warnings = []

    def add(label, violations):
        checks.append((label, not violations, _describe(violations)))

    forbidden_tags = [node for node in nodes if node.tag in FORBIDDEN_TAGS]
    add("无微信会剥离或干扰的禁用标签", forbidden_tags)
    add("复制区元素无重复属性", inspector.duplicate_attrs)

    event_attrs = [
        f"第 {node.line} 行 <{node.tag}> 的 {attr}"
        for node in nodes
        for attr in node.attrs
        if attr.startswith("on")
    ]
    add("复制区无事件属性", event_attrs)

    forbidden_layout = []
    flex_or_gap = []
    background_shorthand = []
    image_or_gradient = []
    unsafe_background = []
    negative_margins = []
    percent_geometry = []
    concealed_content = []
    dynamic_css = []
    advanced_color_syntax = []
    css_escapes = []
    negative_text_indent = []

    for node in nodes:
        raw_style = node.attrs.get("style", "")
        if "\\" in raw_style:
            css_escapes.append(
                f"第 {node.line} 行 <{node.tag}> style 含 CSS 转义"
            )
        for prop, value in node.style.items():
            clean = _clean_value(value)
            if prop.startswith("--") or re.search(r"\b(?:var|calc)\s*\(", value, re.I):
                dynamic_css.append(
                    f"第 {node.line} 行 <{node.tag}> {prop}: {value}"
                )
            if re.search(
                r"\b(?:color|color-mix|contrast-color|device-cmyk|hwb|"
                r"lab|lch|light-dark|oklab|oklch)\s*\(",
                value,
                re.I,
            ):
                advanced_color_syntax.append(
                    f"第 {node.line} 行 <{node.tag}> {prop}: {value}"
                )
            if (
                prop in FORBIDDEN_LAYOUT_PROPERTIES
                or prop
                in {
                    "clip",
                    "clip-path",
                    "content-visibility",
                    "filter",
                    "mask",
                    "-webkit-mask",
                    "opacity",
                }
                or prop.startswith("animation")
                or prop.startswith("-webkit-animation")
                or prop.startswith("transition")
                or prop.startswith("-webkit-transition")
            ):
                forbidden_layout.append(
                    f"第 {node.line} 行 <{node.tag}> {prop}: {value}"
                )
            if prop == "display" and clean in {
                "flex",
                "inline-flex",
                "grid",
                "inline-grid",
            }:
                flex_or_gap.append(
                    f"第 {node.line} 行 <{node.tag}> display: {value}"
                )
            if prop in {"gap", "row-gap", "column-gap"}:
                flex_or_gap.append(
                    f"第 {node.line} 行 <{node.tag}> {prop}: {value}"
                )
            if prop == "background":
                background_shorthand.append(
                    f"第 {node.line} 行 <{node.tag}> background: {value}"
                )
            if prop in {"background-image", "border-image"} or re.search(
                r"(?:repeating-)?(?:linear|radial|conic)-gradient\s*\(",
                value,
                flags=re.I,
            ):
                image_or_gradient.append(
                    f"第 {node.line} 行 <{node.tag}> {prop}: {value}"
                )
            if prop == "background-color":
                if _uses_alpha_color(value):
                    unsafe_background.append(
                        f"第 {node.line} 行 <{node.tag}> 背景使用 alpha 颜色"
                    )
                if re.search(
                    r"(?<![0-9a-f])#(?:fff|ffffff)(?![0-9a-f])",
                    value,
                    flags=re.I,
                ):
                    unsafe_background.append(
                        f"第 {node.line} 行 <{node.tag}> 背景使用 {value}"
                    )
            if prop == "margin" or prop.startswith("margin-"):
                if re.search(r"(^|[\s,(])-+(?:\d|\.)", value) or re.search(
                    r"\bcalc\s*\(", value, flags=re.I
                ):
                    negative_margins.append(
                        f"第 {node.line} 行 <{node.tag}> {prop}: {value}"
                    )
                if "%" in value:
                    percent_geometry.append(
                        f"第 {node.line} 行 <{node.tag}> {prop}: {value}"
                    )
            if prop == "height" and "%" in value:
                percent_geometry.append(
                    f"第 {node.line} 行 <{node.tag}> height: {value}"
                )
            if prop == "text-indent" and (
                re.search(r"(^|[\s,(])-+(?:\d|\.)", value)
                or re.search(r"\b(?:var|calc)\s*\(", value, flags=re.I)
            ):
                negative_text_indent.append(
                    f"第 {node.line} 行 <{node.tag}> text-indent: {value}"
                )
        style = {key: _clean_value(value) for key, value in node.style.items()}
        opacity_zero = bool(re.fullmatch(r"0(?:\.0+)?", style.get("opacity", "")))
        transparent_text = (
            _is_fully_transparent_color(style.get("color", ""))
            or _is_fully_transparent_color(
                style.get("-webkit-text-fill-color", "")
            )
        )
        hidden_box = (
            style.get("display") == "none"
            or style.get("visibility") in {"hidden", "collapse"}
            or opacity_zero
            or transparent_text
            or "hidden" in node.attrs
        )
        font_size_match = re.fullmatch(
            r"(\d+(?:\.\d+)?|\.\d+)px",
            style.get("font-size", ""),
        )
        tiny_text = bool(
            (
                style.get("font-size") == "0"
                or (
                    font_size_match
                    and float(font_size_match.group(1)) < 4
                )
            )
            and re.search(r"\S", node.direct_text.replace("\xa0", ""))
        )
        clipped_text = (
            style.get("overflow") == "hidden"
            and style.get("height") in {"0", "0px"}
            and bool(re.search(r"\S", node.text.replace("\xa0", "")))
        )
        if hidden_box or tiny_text or clipped_text:
            concealed_content.append(
                f"第 {node.line} 行 <{node.tag}> 含不可见文字或隐藏盒"
            )

    add(
        "无 position/float/transform/animation/transition/z-index",
        forbidden_layout,
    )
    add("无 flex/grid/gap 布局", flex_or_gap)
    add("背景不用 background 简写", background_shorthand)
    add("无渐变、background-image 或 border-image", image_or_gradient)
    add("背景色无 rgba/hsla，纯白用 #fefefe", unsafe_background)
    add("无负 margin 或不可判定的 calc margin", negative_margins)
    add("margin/height 不用百分比", percent_geometry)
    add("无 display:none/透明/零字号等隐藏内容", concealed_content)
    add("无负 text-indent 等移出屏幕的文字", negative_text_indent)
    add("内联 CSS 不使用自定义变量、var() 或 calc()", dynamic_css)
    add("颜色不使用现代高级颜色函数", advanced_color_syntax)
    add("内联 CSS 不使用反斜线转义", css_escapes)

    unsafe_images = []
    for node in (item for item in nodes if item.tag == "img"):
        src = node.attrs.get("src", "")
        parsed = urlparse(src)
        style = {key: _clean_value(value) for key, value in node.style.items()}
        reasons = []
        if parsed.scheme.lower() != "https":
            reasons.append("src 不是 https")
        if style.get("width") != "100%":
            reasons.append("缺 width:100%")
        if style.get("height") != "auto":
            reasons.append("缺 height:auto")
        if style.get("display") != "block":
            reasons.append("缺 display:block")
        if reasons:
            unsafe_images.append(
                f"第 {node.line} 行 <img>（{'、'.join(reasons)}）"
            )
    add("图片为 https 且含 width:100%/height:auto/display:block", unsafe_images)

    unsafe_links = []
    for node in (item for item in nodes if item.tag == "a"):
        href = node.attrs.get("href", "").strip()
        if href and not href.startswith("https://mp.weixin.qq.com/"):
            unsafe_links.append(
                f"第 {node.line} 行外链 {href[:60]}（应转文末纯文本参考资料）"
            )
    add("正文仅保留 mp.weixin.qq.com 可点击链接", unsafe_links)

    bad_table_clipping = [
        node
        for node in nodes
        if node.tag in {"table", "td"}
        and _clean_value(node.style.get("overflow", "")) == "hidden"
    ]
    add("table/td 不承担 overflow:hidden 圆角裁切", bad_table_clipping)

    outer_indexes = [
        index
        for index, node in enumerate(nodes)
        if node.tag == "section"
        and node.attrs.get("data-role", "").lower() == "outer"
    ]
    skeleton_errors = []
    td_border_errors = []
    divider_errors = []
    for outer_index in outer_indexes:
        outer = nodes[outer_index]
        direct_tables = [
            node
            for node in nodes
            if node.tag == "table" and node.parent == outer_index
        ]
        if len(direct_tables) != 1:
            skeleton_errors.append(
                f"第 {outer.line} 行 outer 需要且只能有一个直接子 table"
            )
            continue
        table = direct_tables[0]
        table_style = {
            key: _clean_value(value) for key, value in table.style.items()
        }
        expected = {
            "width": table.attrs.get("width", "").strip() == "100%",
            "cellspacing": table.attrs.get("cellspacing", "").strip() == "0",
            "cellpadding": table.attrs.get("cellpadding", "").strip() == "0",
            "border": table.attrs.get("border", "").strip() == "0",
            "border-collapse": table_style.get("border-collapse") == "collapse",
            "border-spacing": table_style.get("border-spacing") in {"0", "0px"},
            "style border": table_style.get("border") in {"none", "0", "0px"},
        }
        missing = [key for key, ok in expected.items() if not ok]
        if missing:
            skeleton_errors.append(
                f"第 {table.line} 行主骨架 table 缺少：{', '.join(missing)}"
            )

        for index, node in enumerate(nodes):
            if node.tag != "td" or not _is_descendant(nodes, index, outer_index):
                continue
            if _clean_value(node.style.get("border", "")) not in {
                "none",
                "0",
                "0px",
            }:
                td_border_errors.append(node)

        divider_indexes = [
            index
            for index, node in enumerate(nodes)
            if node.attrs.get("data-role", "").lower() == "divider"
            and (index == outer_index or _is_descendant(nodes, index, outer_index))
        ]
        for divider_index in divider_indexes:
            divider = nodes[divider_index]
            candidates = (
                [divider]
                if divider.tag == "td"
                else [
                    node
                    for index, node in enumerate(nodes)
                    if node.tag == "td"
                    and (
                        node.parent == divider_index
                        or _is_descendant(nodes, index, divider_index)
                    )
                ]
            )
            for cell in candidates:
                style = {
                    key: _clean_value(value) for key, value in cell.style.items()
                }
                if style.get("font-size") not in {"0", "0px"} or style.get(
                    "line-height"
                ) not in {"0", "0px"}:
                    divider_errors.append(cell)

    if outer_indexes:
        add("整页底色 outer 使用直接 table 主骨架", skeleton_errors)
        add("整页底色 outer 内所有 td 显式 border:none", td_border_errors)
    if any(
        node.attrs.get("data-role", "").lower() == "divider" for node in nodes
    ):
        add("标记为 divider 的单元格压平行高", divider_errors)

    fixed_widths = []
    oversized_fixed_widths = []
    for node in nodes:
        if node.tag not in BLOCK_TAGS:
            continue
        value = node.style.get("width", "")
        match = re.fullmatch(
            r"\s*(\d+(?:\.\d+)?)px\s*(?:!\s*important)?\s*",
            value,
            re.I,
        )
        if match:
            width = float(match.group(1))
            evidence = (
                f"第 {node.line} 行 <{node.tag}> width: {value}，"
                "请由手机渲染确认"
            )
            if width > 390:
                oversized_fixed_widths.append(evidence)
                continue
            fixed_widths.append(
                evidence
            )
    add("块元素无超过 390px 的固定宽度", oversized_fixed_widths)
    if fixed_widths:
        warnings.append(("块元素使用固定 px 宽度", _describe(fixed_widths)))

    selector_attrs = [
        f"第 {node.line} 行 <{node.tag}> 的 {attr}"
        for node in nodes
        for attr in ("class", "id")
        if node.attrs.get(attr)
    ]
    if selector_attrs:
        warnings.append(
            ("复制区含 class/id；不得依赖它们呈现样式", _describe(selector_attrs))
        )

    has_chinese = bool(re.search(r"[\u3400-\u9fff]", "".join(inspector.text)))
    checks.insert(
        0,
        (
            "复制区含中文正文",
            has_chinese,
            f"{name}，解析到 {len(nodes)} 个元素" if has_chinese else "未检出中文",
        ),
    )
    return checks, warnings


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path, help="待检查的 HTML")
    parser.add_argument(
        "--fragment",
        action="store_true",
        help="把整个文件当作待粘贴的裸片段；完整预览页不要使用",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])
    if not args.html.is_file():
        print(f"✗ 文件不存在: {args.html}")
        return 2
    document = args.html.read_text(encoding="utf-8", errors="replace")
    try:
        content = get_copy_html(document, allow_fragment=args.fragment)
    except ValueError as error:
        print(f"✗ 复制边界错误: {error}")
        return 2

    checks, warnings = run_checks(content, args.html.name)
    failures = [item for item in checks if not item[1]]
    print(
        f"微信兼容检查：{len(checks) - len(failures)}/{len(checks)} 通过"
        f"　（{args.html.name}）"
    )
    for label, ok, evidence in checks:
        if not ok:
            print(f"  ✗ {label}　←　{evidence}")
    for label, evidence in warnings:
        print(f"  ⚠ {label}　←　{evidence}")
    if failures:
        print(f"\n✗ 未通过 {len(failures)} 项兼容硬规则，修复后重跑")
        return 1
    print("✓ 兼容硬规则全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
