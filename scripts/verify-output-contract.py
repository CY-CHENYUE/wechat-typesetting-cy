#!/usr/bin/env python3
"""检查 wechat-typesetting-cy 的完整预览交付契约。

本脚本不判断微信 CSS 兼容；兼容性由 ``verify-wechat-compat.py`` 负责。
通过返回 0，契约缺失返回 1，参数或文件错误返回 2。
"""

import argparse
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

from wechat_html import (
    NON_ORDINARY_COPY_ROOT_ANCESTORS,
    VOID_ELEMENTS,
    attrs_explicitly_hidden,
    attrs_first_wins,
    count_copy_root_ids,
    find_copy_root_tags,
    find_copy_roots,
    get_copy_html,
)


STYLE_COMMENT = re.compile(
    r"^\s*<!--\s*风格方向\s*[:：]\s*(?P<primary>.*?)"
    r"\s*\|\s*备选\s*[:：]\s*(?P<alternatives>.*?)\s*-->",
    flags=re.S,
)


class DocumentInspector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = {}
        self.has_viewport = False
        self.has_title = False
        self.duplicate_attrs = []
        self.copy_button_actions = []
        self.copy_button_disabled = []
        self.copy_button_attributes = []
        self.copy_button_hidden_ancestor = []
        self.copy_button_nonordinary_ancestor = []
        self.copy_button_inherited_unavailable = []
        self.element_stack = []
        self.script_depth = 0
        self.script_parts = []
        self.script_types = []
        self.script_attributes = []

    def handle_starttag(self, tag, attrs):
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
        element_id = attrs_dict.get("id")
        parent_hidden = bool(
            self.element_stack and self.element_stack[-1][2]
        )
        explicitly_hidden = attrs_explicitly_hidden(attrs_dict)
        if element_id:
            self.ids.setdefault(element_id, []).append(tag.lower())
        if tag.lower() == "button" and element_id == "copy-btn":
            self.copy_button_actions.append(attrs_dict.get("onclick", ""))
            self.copy_button_disabled.append("disabled" in attrs_dict)
            self.copy_button_attributes.append(sorted(attrs_dict))
            self.copy_button_hidden_ancestor.append(parent_hidden)
            self.copy_button_nonordinary_ancestor.append(
                any(
                    ancestor_tag in NON_ORDINARY_COPY_ROOT_ANCESTORS
                    for ancestor_tag, _, _ in self.element_stack
                )
            )
            self.copy_button_inherited_unavailable.append(
                any(
                    "inert" in ancestor_attrs
                    or (
                        ancestor_tag == "fieldset"
                        and "disabled" in ancestor_attrs
                    )
                    for ancestor_tag, ancestor_attrs, _ in self.element_stack
                )
            )
        if tag.lower() == "meta" and attrs_dict.get("name", "").lower() == "viewport":
            self.has_viewport = bool(attrs_dict.get("content", "").strip())
        if tag.lower() == "title":
            self.has_title = True
        if tag.lower() == "script":
            self.script_types.append(
                attrs_dict.get("type", "").strip().lower()
            )
            self.script_attributes.append(sorted(attrs_dict))
            self.script_depth += 1
        if tag.lower() not in VOID_ELEMENTS:
            self.element_stack.append(
                (tag.lower(), attrs_dict, parent_hidden or explicitly_hidden)
            )

    def handle_endtag(self, tag):
        if tag.lower() == "script" and self.script_depth:
            self.script_depth -= 1
        tag = tag.lower()
        for offset in range(len(self.element_stack) - 1, -1, -1):
            if self.element_stack[offset][0] == tag:
                del self.element_stack[offset:]
                break

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, data):
        if self.script_depth:
            self.script_parts.append(data)


def strip_javascript_comments(source):
    """Remove JS comments while preserving quoted strings used by the checks."""

    output = []
    index = 0
    quote = None
    escaped = False
    while index < len(source):
        char = source[index]
        following = source[index + 1] if index + 1 < len(source) else ""
        if quote:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue
        if char in {"'", '"', "`"}:
            quote = char
            output.append(char)
            index += 1
            continue
        if char == "/" and following == "/":
            index += 2
            while index < len(source) and source[index] not in "\r\n":
                index += 1
            output.append("\n")
            continue
        if char == "/" and following == "*":
            index += 2
            while index + 1 < len(source) and source[index : index + 2] != "*/":
                index += 1
            index = min(len(source), index + 2)
            output.append(" ")
            continue
        output.append(char)
        index += 1
    return "".join(output)


def mask_javascript_strings(source, kept_literals=None):
    """Blank string contents so code-shaped text cannot satisfy code checks.

    A few literal arguments that are part of the contract remain visible.
    The returned text has the same length and line breaks as ``source`` so
    brace matching and diagnostics keep their positions.
    """

    kept_literals = set(kept_literals or ())
    output = list(source)
    index = 0
    while index < len(source):
        quote = source[index]
        if quote not in {"'", '"', "`"}:
            index += 1
            continue
        start = index
        index += 1
        escaped = False
        while index < len(source):
            char = source[index]
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                break
            index += 1
        end = index if index < len(source) else len(source) - 1
        literal = source[start + 1 : end]
        keep = quote != "`" and literal in kept_literals
        if not keep:
            for position in range(start + 1, end):
                if output[position] not in "\r\n":
                    output[position] = " "
        index = min(len(source), end + 1)
    return "".join(output)


def extract_named_function_bodies(source, name):
    """Return masked bodies of plain JS function declarations named ``name``."""

    masked = mask_javascript_strings(
        source,
        kept_literals={"wechat-content", "text/html", "copy"},
    )
    declaration = re.compile(
        rf"(?:async\s+)?function\s+{re.escape(name)}\s*\([^)]*\)\s*\{{"
    )
    bodies = []
    cursor = 0
    while True:
        match = declaration.search(masked, cursor)
        if not match:
            break
        opening = match.end() - 1
        depth = 0
        closing = None
        for position in range(opening, len(masked)):
            char = masked[position]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    closing = position
                    break
        if closing is None:
            break
        bodies.append(masked[opening + 1 : closing])
        cursor = closing + 1
    return bodies


def normalized_javascript_structure(body):
    return re.sub(r"\s+", "", body)


def canonical_copy_fingerprint():
    shell_path = Path(__file__).resolve().parents[1] / "assets" / "preview-shell.html"
    shell = shell_path.read_text(encoding="utf-8")
    inspector = DocumentInspector()
    inspector.feed(shell)
    source = strip_javascript_comments("\n".join(inspector.script_parts))
    bodies = extract_named_function_bodies(source, "copyContent")
    if len(bodies) != 1:
        raise ValueError("preview-shell.html 缺少唯一 copyContent 函数")
    return normalized_javascript_structure(bodies[0])


def canonical_script_fingerprint():
    shell_path = Path(__file__).resolve().parents[1] / "assets" / "preview-shell.html"
    shell = shell_path.read_text(encoding="utf-8")
    inspector = DocumentInspector()
    inspector.feed(shell)
    source = strip_javascript_comments("\n".join(inspector.script_parts))
    return normalized_javascript_structure(mask_javascript_strings(source))


def _split_alternatives(text):
    return [
        item.strip()
        for item in re.split(r"\s*(?:/|／|、|，|,)\s*", text)
        if item.strip()
    ]


def run_checks(document, name):
    inspector = DocumentInspector()
    inspector.feed(document)
    roots = find_copy_roots(document)
    root_tags = find_copy_root_tags(document)
    root_id_count = count_copy_root_ids(document)
    content = roots[0] if len(roots) == 1 and root_id_count == 1 else ""
    checks = []

    def add(label, ok, evidence):
        checks.append((label, bool(ok), str(evidence)))

    add(
        "复制区 #wechat-content 唯一",
        len(roots) == 1 and root_id_count == 1,
        f"找到 {root_id_count} 个",
    )
    add(
        "复制根使用浏览器安全的 <div>",
        root_tags == ["div"],
        f"实际：<{root_tags[0]}>"
        if len(root_tags) == 1
        else f"可解析根标签 {len(root_tags)} 个",
    )
    add(
        "完整预览无重复 HTML 属性",
        not inspector.duplicate_attrs,
        "未检出"
        if not inspector.duplicate_attrs
        else "；".join(inspector.duplicate_attrs[:4]),
    )
    add(
        "复制区含中文正文",
        bool(content and re.search(r"[\u3400-\u9fff]", content)),
        f"{name}，复制区 {len(content)} 字符" if content else "复制区不可用",
    )

    style_match = STYLE_COMMENT.match(content) if content else None
    primary = style_match.group("primary").strip() if style_match else ""
    alternatives = (
        _split_alternatives(style_match.group("alternatives"))
        if style_match
        else []
    )
    add(
        "复制区首个有效节点是机器可读风格注释",
        bool(style_match and primary),
        f"方向：{primary}" if primary else "未找到约定格式",
    )
    add(
        "风格注释给出两个备选方向",
        len(alternatives) >= 2,
        " / ".join(alternatives) if alternatives else "备选不足",
    )

    add(
        "存在唯一、未显式隐藏且未禁用的一键复制按钮 #copy-btn",
        len(inspector.ids.get("copy-btn", [])) == 1
        and inspector.ids["copy-btn"][0] == "button"
        and inspector.copy_button_disabled == [False]
        and inspector.copy_button_attributes == [["id", "onclick"]]
        and inspector.copy_button_hidden_ancestor == [False]
        and inspector.copy_button_nonordinary_ancestor == [False]
        and inspector.copy_button_inherited_unavailable == [False],
        (
            f"找到 {len(inspector.ids.get('copy-btn', []))} 个；"
            f"属性 {inspector.copy_button_attributes or ['缺失']}"
        ),
    )
    add(
        "存在唯一手机宽度切换按钮 #width-btn",
        len(inspector.ids.get("width-btn", [])) == 1
        and inspector.ids["width-btn"][0] == "button",
        f"找到 {len(inspector.ids.get('width-btn', []))} 个",
    )
    script_source = strip_javascript_comments("\n".join(inspector.script_parts))
    executable_script = bool(
        len(inspector.script_types) == 1
        and inspector.script_attributes == [[]]
    )
    add(
        "复制基础设施位于唯一可执行脚本",
        executable_script,
        "唯一普通 JavaScript"
        if executable_script
        else (
            f"script 属性：{inspector.script_attributes or ['缺失']}"
        ),
    )
    function_bodies = extract_named_function_bodies(script_source, "copyContent")
    try:
        expected_copy_fingerprint = canonical_copy_fingerprint()
        expected_script_fingerprint = canonical_script_fingerprint()
    except (OSError, ValueError) as error:
        expected_copy_fingerprint = None
        expected_script_fingerprint = None
        canonical_error = str(error)
    else:
        canonical_error = ""
    actual_copy_fingerprint = (
        normalized_javascript_structure(function_bodies[0])
        if len(function_bodies) == 1
        else None
    )
    copy_implementation_matches = bool(
        expected_copy_fingerprint
        and actual_copy_fingerprint == expected_copy_fingerprint
    )
    script_implementation_matches = bool(
        expected_script_fingerprint
        and normalized_javascript_structure(
            mask_javascript_strings(script_source)
        )
        == expected_script_fingerprint
    )
    masked_script = mask_javascript_strings(script_source)
    copy_overridden = bool(
        re.search(
            r"\b(?:(?:window|globalThis|self)\s*\.\s*)?"
            r"copyContent\s*=",
            masked_script,
        )
    )
    button_calls_copy = bool(
        len(inspector.copy_button_actions) == 1
        and re.fullmatch(
            r"\s*copyContent\s*\(\s*\)\s*;?\s*",
            strip_javascript_comments(inspector.copy_button_actions[0]),
        )
    )
    function_copy_logic = False
    for function_body in function_bodies:
        root_bindings = re.findall(
            r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*"
            r"document\.getElementById\s*\(\s*['\"]wechat-content['\"]\s*\)",
            function_body,
        )
        for binding in root_bindings:
            variable = re.escape(binding)
            clipboard_write = re.search(
                r"navigator\.clipboard\.write\s*\(",
                function_body,
            )
            exec_copy = re.search(
                r"execCommand\s*\(\s*['\"]copy['\"]",
                function_body,
            )
            rich_clipboard = bool(
                clipboard_write
                and re.search(r"\bnew\s+ClipboardItem\s*\(", function_body)
                and re.search(r"['\"]text/html['\"]", function_body)
                and re.search(
                    rf"\bnew\s+Blob\s*\(\s*\[\s*{variable}\.innerHTML\b",
                    function_body,
                )
            )
            range_copy = bool(
                re.search(
                    rf"selectNodeContents\s*\(\s*{variable}\s*\)",
                    function_body,
                )
                and exec_copy
            )
            copy_positions = [
                match.start()
                for match in (clipboard_write, exec_copy)
                if match is not None
            ]
            first_copy_position = min(copy_positions) if copy_positions else 0
            premature_exit = bool(
                first_copy_position
                and re.search(
                    r"\b(?:return|throw)\b",
                    function_body[:first_copy_position],
                )
            )
            function_copy_logic = function_copy_logic or bool(
                (rich_clipboard or range_copy) and not premature_exit
            )
    copy_logic_ok = bool(
        len(function_bodies) == 1
        and executable_script
        and button_calls_copy
        and function_copy_logic
        and copy_implementation_matches
        and script_implementation_matches
        and not copy_overridden
    )
    add(
        "预览脚本使用已审计的富文本复制实现",
        copy_logic_ok,
        "唯一脚本与 preview-shell.html 的复制基础设施一致"
        if copy_logic_ok
        else (
            canonical_error
            or f"实现结构不一致；找到 {len(function_bodies)} 个同名函数"
        ),
    )
    add(
        "包含移动端 viewport",
        inspector.has_viewport,
        "在场" if inspector.has_viewport else "缺失",
    )
    add(
        "包含页面标题",
        inspector.has_title,
        "在场" if inspector.has_title else "缺失",
    )

    unresolved = sorted(set(re.findall(r"\{\{[^{}]+\}\}", document)))
    add(
        "预览产物无未替换占位符",
        not unresolved,
        "未检出" if not unresolved else "、".join(unresolved[:6]),
    )
    return checks


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path, help="待检查的完整预览 HTML")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])
    if not args.html.is_file():
        print(f"✗ 文件不存在: {args.html}")
        return 2
    document = args.html.read_text(encoding="utf-8", errors="replace")
    if count_copy_root_ids(document) == 1:
        try:
            get_copy_html(document)
        except ValueError as error:
            print(f"✗ 复制边界错误: {error}")
            return 2
    checks = run_checks(document, args.html.name)
    failures = [item for item in checks if not item[1]]
    print(
        f"输出契约检查：{len(checks) - len(failures)}/{len(checks)} 通过"
        f"　（{args.html.name}）"
    )
    for label, ok, evidence in checks:
        if not ok:
            print(f"  ✗ {label}　←　{evidence}")
    if failures:
        print(f"\n✗ 未通过 {len(failures)} 项交付契约，修复后重跑")
        return 1
    print("✓ 完整预览交付契约通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
