#!/usr/bin/env python3
"""严格核对原文与复制区的可见原文流。

用法：

    python3 verify-completeness.py source.md output.html
    python3 verify-completeness.py --fragment source.md fragment.html

比较前只做三类 SKILL 明确允许的结构转换：去 Markdown 记号、去媒体标记、
去可被版式编号替代的枚举前缀。输出中不属于原文的可见版式文字必须放进
``data-layout-text="true"`` 元素；这些元素会被排除。其余可见文字按原顺序
精确比较，因而能发现缺字、改标点、重排、重复和未标记的新增文字。

通过返回 0；内容不一致返回 1；参数、文件或复制边界错误返回 2。
"""

import argparse
import difflib
import html as html_mod
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

from wechat_html import (
    VOID_ELEMENTS,
    attrs_first_wins,
    get_copy_html,
    parse_inline_style,
)


LAYOUT_TRUE = {"true", "1", "yes"}
TEXT_BLOCK_TAGS = {"address", "blockquote", "div", "p", "section", "table", "td", "tr"}


def normalize(text):
    """Ignore layout whitespace while preserving English word boundaries.

    Chinese layout routinely changes line breaks and indentation. English
    spaces, however, can distinguish ``Use GPT 5`` from ``UseGPT5``. Keep a
    single space only when it separates ASCII letters or digits.
    """

    value = html_mod.unescape(text)
    output = []
    cursor = 0
    for match in re.finditer(r"\s+", value):
        output.append(value[cursor : match.start()])
        previous = value[match.start() - 1] if match.start() else ""
        following = value[match.end()] if match.end() < len(value) else ""
        if previous.isascii() and previous.isalnum() and following.isascii() and following.isalnum():
            output.append(" ")
        cursor = match.end()
    output.append(value[cursor:])
    return "".join(output)


def is_media_line(line):
    value = line.strip()
    if re.match(r"^!\[[^\]]*\]\([^)]*\)\s*$", value):
        return True
    if re.match(
        r"^[【\[（(]\s*(图|视频|音频|配图|封面)\s*"
        r"[\d一二三四五六七八九十]*\s*[：:、]",
        value,
    ):
        return True
    if re.match(r"^（?此处(放|配|插)(图|视频)", value):
        return True
    if re.match(r"^https?://\S+$", value):
        return True
    return False


def strip_markdown(line):
    value = line.strip()
    if re.fullmatch(r"`{3,}.*", value) or re.fullmatch(r"~{3,}.*", value):
        return ""
    if re.fullmatch(r"(?:-{3,}|\*{3,}|_{3,})", value):
        return ""
    value = re.sub(r"^#{1,6}\s*", "", value)
    value = re.sub(r"^(?:>\s*)+", "", value)
    value = re.sub(r"^[-*+]\s+", "", value)
    value = re.sub(r"^\d+[.、)]\s*", "", value)
    value = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", value)
    value = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", value)
    value = re.sub(r"<https?://[^>]+>", "", value)
    code_spans = []

    def stash_code(match):
        code_spans.append(match.group(1))
        return f"\ue000{len(code_spans) - 1}\ue001"

    value = re.sub(r"`([^`]+)`", stash_code, value)
    value = re.sub(r"\*\*([^*]+)\*\*", r"\1", value)
    value = re.sub(r"(?<!\w)__([^_]+)__(?!\w)", r"\1", value)
    value = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\1", value)
    value = re.sub(r"(?<!\w)_([^_]+)_(?!\w)", r"\1", value)
    value = re.sub(r"~~([^~]+)~~", r"\1", value)
    value = re.sub(
        r"^(步骤|第)\s*[\d一二三四五六七八九十]+\s*"
        r"[步章节条款]?\s*[：:.、]\s*",
        "",
        value,
    )
    value = re.sub(r"\\([\\`*_{}\[\]()#+\-.!>])", r"\1", value)
    for index, code in enumerate(code_spans):
        value = value.replace(f"\ue000{index}\ue001", code)
    return value


def iter_source_lines(text):
    in_fence = False
    fence_character = None
    fence_length = 0
    for line_number, line in enumerate(text.splitlines(), 1):
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker:
            token = marker.group(1)
            if not in_fence:
                in_fence = True
                fence_character = token[0]
                fence_length = len(token)
            elif token[0] == fence_character and len(token) >= fence_length:
                in_fence = False
                fence_character = None
                fence_length = 0
            continue
        if not line.strip():
            continue
        if in_fence:
            yield line_number, line
            continue
        if is_media_line(line):
            continue
        stripped = strip_markdown(line)
        if stripped:
            yield line_number, stripped


def canonical_source(text):
    return normalize("\n".join(line for _, line in iter_source_lines(text)))


def source_urls(text):
    """Return every HTTP(S) target that content transformations must preserve."""

    matches = re.findall(r"https?://[^\s<>\])]+", html_mod.unescape(text))
    cleaned = [
        value.rstrip(".,!?;:，。！？；：'\"")
        for value in matches
    ]
    return list(dict.fromkeys(value for value in cleaned if value))


def source_clauses(text):
    clauses = []
    for line_number, line in iter_source_lines(text):
        for piece in re.split(r"(?<=[。！？；：!?;])", line):
            normalized = normalize(piece)
            if normalized:
                clauses.append((line_number, normalized))
    return clauses


class SemanticTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.parts = []
        self.visible_parts = []
        self.layout_groups = []
        self.visible_urls = []
        self.errors = []

    def _is_skipped(self):
        return bool(self.stack and self.stack[-1][1])

    def _active_layout_group(self):
        return self.stack[-1][2] if self.stack else None

    def _is_nonvisible(self):
        return bool(self.stack and self.stack[-1][3])

    def _append_boundary(self, layout_group, nonvisible):
        if nonvisible:
            return
        if layout_group is not None:
            self.layout_groups[layout_group].append("\n")
        self.visible_parts.append("\n")
        self.parts.append("\n")

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        raw_attrs, duplicates = attrs_first_wins(attrs)
        attrs_dict = {
            key: "" if value is None else str(value)
            for key, value in raw_attrs.items()
        }
        if duplicates:
            self.errors.append(
                f"<{tag}> 含重复属性：" + ", ".join(sorted(set(duplicates)))
            )
        style = parse_inline_style(attrs_dict.get("style", ""))
        clean_style = {
            key: re.sub(r"\s*!\s*important\s*$", "", value, flags=re.I)
            .strip()
            .lower()
            for key, value in style.items()
        }
        opacity = clean_style.get("opacity", "")
        transparent_text = (
            clean_style.get("color") == "transparent"
            or clean_style.get("-webkit-text-fill-color") == "transparent"
            or bool(
                re.fullmatch(
                    r"rgba\([^,]+,[^,]+,[^,]+,\s*0(?:\.0+)?\s*\)",
                    clean_style.get("color", ""),
                )
            )
        )
        hidden = (
            "hidden" in attrs_dict
            or clean_style.get("display") == "none"
            or clean_style.get("visibility") in {"hidden", "collapse"}
            or bool(re.fullmatch(r"0(?:\.0+)?", opacity))
            or transparent_text
        )
        marked_layout = (
            attrs_dict.get("data-layout-text", "").strip().lower()
            in LAYOUT_TRUE
        )
        layout_group = self._active_layout_group()
        if marked_layout:
            self.layout_groups.append([])
            layout_group = len(self.layout_groups) - 1
        parent_nonvisible = self._is_nonvisible()
        nonvisible = parent_nonvisible or tag in {"script", "style"} or hidden
        skipped = self._is_skipped() or marked_layout or nonvisible
        if not nonvisible:
            for attr in ("href", "src"):
                value = html_mod.unescape(attrs_dict.get(attr, ""))
                if value.startswith(("http://", "https://")):
                    self.visible_urls.append(value)
        if tag == "br" or tag in TEXT_BLOCK_TAGS:
            self._append_boundary(layout_group, nonvisible)
        if tag not in VOID_ELEMENTS:
            self.stack.append((tag, skipped, layout_group, nonvisible))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag.lower() not in VOID_ELEMENTS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        tag = tag.lower()
        for offset in range(len(self.stack) - 1, -1, -1):
            if self.stack[offset][0] == tag:
                _, _, layout_group, nonvisible = self.stack[offset]
                if tag in TEXT_BLOCK_TAGS:
                    self._append_boundary(layout_group, nonvisible)
                del self.stack[offset:]
                return

    def handle_data(self, data):
        layout_group = self._active_layout_group()
        if layout_group is not None and not self._is_nonvisible():
            self.layout_groups[layout_group].append(data)
        if not self._is_nonvisible():
            self.visible_parts.append(data)
        if not self._is_skipped():
            self.parts.append(data)


def semantic_output(content):
    parser = SemanticTextExtractor()
    parser.feed(content)
    return (
        normalize("".join(parser.parts)),
        [normalize("".join(group)) for group in parser.layout_groups],
        set(source_urls("".join(parser.visible_parts))).union(
            value
            for url in parser.visible_urls
            for value in source_urls(url)
        ),
        parser.errors,
    )


def layout_text_overlaps_source(expected, layout_groups):
    """Flag marked text that appears to hide or duplicate source material."""

    def meaningful(value):
        return "".join(
            re.findall(r"[A-Za-z0-9\u3400-\u9fff]+", value)
        ).casefold()

    def overlaps_source(value_meaningful, expected_meaningful):
        if not value_meaningful or not expected_meaningful:
            return False

        def substantial(fragment):
            return (
                len(re.findall(r"[\u3400-\u9fff]", fragment)) >= 3
                or len(re.findall(r"[a-z0-9]", fragment)) >= 5
            )

        if value_meaningful == expected_meaningful:
            return True
        if (
            value_meaningful in expected_meaningful
            and substantial(value_meaningful)
        ):
            return True
        if (
            expected_meaningful in value_meaningful
            and substantial(expected_meaningful)
        ):
            return True
        for pattern in (r"[\u3400-\u9fff]", r"[a-z0-9]"):
            value_script = "".join(re.findall(pattern, value_meaningful))
            expected_script = "".join(re.findall(pattern, expected_meaningful))
            if not value_script or not expected_script:
                continue
            if value_script == expected_script:
                return True
            if (
                value_script in expected_script
                and substantial(value_script)
            ):
                return True
            if (
                expected_script in value_script
                and substantial(expected_script)
            ):
                return True
        match = difflib.SequenceMatcher(
            None,
            value_meaningful,
            expected_meaningful,
            autojunk=False,
        ).find_longest_match()
        shared = value_meaningful[match.a : match.a + match.size]
        chinese_count = len(re.findall(r"[\u3400-\u9fff]", shared))
        ascii_count = len(re.findall(r"[a-z0-9]", shared))
        return chinese_count >= 3 or ascii_count >= 5

    expected_meaningful = meaningful(expected)
    violations = []
    for value in layout_groups:
        if not value:
            continue
        value_meaningful = meaningful(value)
        if overlaps_source(value_meaningful, expected_meaningful):
            violations.append(value)
    joined = "".join(layout_groups)
    joined_meaningful = meaningful(joined)
    if (
        expected_meaningful
        and joined_meaningful
        and overlaps_source(joined_meaningful, expected_meaningful)
        and joined not in violations
    ):
        violations.append(expected)
    return violations


def first_difference(expected, actual):
    matcher = difflib.SequenceMatcher(None, expected, actual, autojunk=False)
    for tag, left_start, left_end, right_start, right_end in matcher.get_opcodes():
        if tag == "equal":
            continue
        left_context = expected[max(0, left_start - 24) : min(len(expected), left_end + 24)]
        right_context = actual[max(0, right_start - 24) : min(len(actual), right_end + 24)]
        return tag, left_start, right_start, left_context, right_context
    return None


def ordered_missing_clauses(source_text, actual):
    missing = []
    cursor = 0
    for line_number, clause in source_clauses(source_text):
        position = actual.find(clause, cursor)
        if position < 0:
            missing.append((line_number, clause))
            continue
        cursor = position + len(clause)
    return missing


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="原文 Markdown 或纯文本")
    parser.add_argument("html", type=Path, help="排版输出 HTML")
    parser.add_argument(
        "--fragment",
        action="store_true",
        help="把整个输出文件当作裸复制片段；完整预览页不要使用",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])
    for path in (args.source, args.html):
        if not path.is_file():
            print(f"✗ 文件不存在: {path}")
            return 2

    source_text = args.source.read_text(encoding="utf-8", errors="replace")
    document = args.html.read_text(encoding="utf-8", errors="replace")
    try:
        content = get_copy_html(document, allow_fragment=args.fragment)
    except ValueError as error:
        print(f"✗ 复制边界错误: {error}")
        return 2

    expected = canonical_source(source_text)
    actual, layout_groups, output_urls, structure_errors = semantic_output(content)
    if structure_errors:
        print(f"✗ 复制区 HTML 结构异常：{structure_errors[0]}")
        return 2
    layout_violations = layout_text_overlaps_source(expected, layout_groups)
    missing_urls = [
        url for url in source_urls(source_text) if url not in output_urls
    ]
    if expected == actual and not layout_violations and not missing_urls:
        print(
            f"内容完整性校验：通过（原文 {len(expected)} 个非空白字符，"
            "顺序、重数与标点一致）"
        )
        print("✓ 未发现删改、重排、重复或未标记的新增文字")
        return 0

    print(
        f"内容完整性校验：未通过（原文 {len(expected)} 字符，"
        f"输出原文流 {len(actual)} 字符）"
    )
    if layout_violations:
        print("  data-layout-text 疑似包住或复制了原文：")
        for value in layout_violations[:5]:
            print(f"    {value[:70]}")
    if missing_urls:
        print("  原文链接目标在可见文字或媒体/链接属性中缺失：")
        for value in missing_urls[:5]:
            print(f"    {value[:100]}")
    difference = first_difference(expected, actual)
    if difference:
        tag, source_pos, output_pos, source_context, output_context = difference
        labels = {
            "delete": "输出缺少原文",
            "insert": "输出含新增或重复文字",
            "replace": "输出改写了原文",
        }
        print(
            f"  首个差异：{labels.get(tag, tag)}；"
            f"原文位置 {source_pos}，输出位置 {output_pos}"
        )
        print(f"  原文附近：{source_context[:90] or '∅'}")
        print(f"  输出附近：{output_context[:90] or '∅'}")

    missing = ordered_missing_clauses(source_text, actual)
    if missing:
        print("  未按原顺序命中的原文片段：")
        for line_number, clause in missing[:6]:
            print(f"    第 {line_number} 行：{clause[:70]}")
        if len(missing) > 6:
            print(f"    另 {len(missing) - 6} 条")
    print(
        "\n提示：版式编号、英文眉题、END、媒体/作者占位等原文外文字，"
        '请只包在 data-layout-text="true" 的元素内。'
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
