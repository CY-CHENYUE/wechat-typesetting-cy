#!/usr/bin/env python3
"""Shared HTML helpers for the WeChat typesetting validators."""

import re
from html.parser import HTMLParser


VOID_ELEMENTS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "frame",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}

# These ancestors either keep descendants outside the live document tree
# (``template``), parse markup as text/inert fallback content, or invoke HTML
# tree-building rules that can discard/reparent a flow ``div``.  Python's
# ``HTMLParser`` reports the source tags literally, so accepting a copy root
# below one of them would make the validators inspect a node that
# ``document.getElementById`` may not be able to retrieve at runtime.
NON_ORDINARY_COPY_ROOT_ANCESTORS = {
    "audio",
    "canvas",
    "colgroup",
    "datalist",
    "details",
    "dialog",
    "frameset",
    "head",
    "iframe",
    "math",
    "noembed",
    "noframes",
    "noscript",
    "object",
    "optgroup",
    "option",
    "p",
    "picture",
    "plaintext",
    "select",
    "svg",
    "table",
    "tbody",
    "template",
    "textarea",
    "tfoot",
    "thead",
    "title",
    "tr",
    "video",
    "xmp",
}


def attrs_first_wins(attrs):
    """Match browser handling of duplicate HTML attributes and report repeats."""

    values = {}
    duplicates = []
    for key, value in attrs:
        name = str(key).lower()
        if name in values:
            duplicates.append(name)
            continue
        values[name] = value
    return values, duplicates


def attrs_explicitly_hidden(attrs):
    """Return whether attributes explicitly remove an element from rendering."""

    normalized = {
        str(key).lower(): "" if value is None else str(value)
        for key, value in attrs.items()
    }
    if "hidden" in normalized or "popover" in normalized:
        return True
    style = {
        key: re.sub(r"\s*!\s*important\s*$", "", value, flags=re.I)
        .strip()
        .lower()
        for key, value in parse_inline_style(normalized.get("style", "")).items()
    }
    return (
        style.get("display") == "none"
        or style.get("visibility") in {"hidden", "collapse"}
        or style.get("content-visibility") == "hidden"
        or bool(re.fullmatch(r"0(?:\.0+)?", style.get("opacity", "")))
    )


class CopyRootExtractor(HTMLParser):
    """Collect the inner HTML of every element whose id is ``wechat-content``."""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.roots = []
        self.root_tags = []
        self._parts = None
        self._stack = []
        self._root_tag = None
        self._ancestor_stack = []
        self.errors = []

    def _append(self, text):
        if self._parts is not None:
            self._parts.append(text)

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attrs_dict, duplicates = attrs_first_wins(attrs)
        if self._parts is None and attrs_dict.get("id") == "wechat-content":
            invalid_ancestors = [
                tag
                for tag, _ in self._ancestor_stack
                if tag in NON_ORDINARY_COPY_ROOT_ANCESTORS
            ]
            if invalid_ancestors:
                self.errors.append(
                    "复制根位于浏览器非普通文档树祖先内："
                    + " > ".join(f"<{item}>" for item in invalid_ancestors)
                )
                if tag not in VOID_ELEMENTS:
                    self._ancestor_stack.append((tag, attrs_dict))
                return
            hidden_ancestors = [
                ancestor_tag
                for ancestor_tag, ancestor_attrs in self._ancestor_stack
                if attrs_explicitly_hidden(ancestor_attrs)
            ]
            if attrs_explicitly_hidden(attrs_dict) or hidden_ancestors:
                location = (
                    "复制根自身"
                    if attrs_explicitly_hidden(attrs_dict)
                    else "复制根祖先 "
                    + " > ".join(f"<{item}>" for item in hidden_ancestors)
                )
                self.errors.append(f"{location} 被显式隐藏")
                if tag not in VOID_ELEMENTS:
                    self._ancestor_stack.append((tag, attrs_dict))
                return
            self._parts = []
            self._stack = [tag]
            self._root_tag = tag
            if duplicates:
                self.errors.append(
                    "复制根含重复属性：" + ", ".join(sorted(set(duplicates)))
                )
            return
        if self._parts is None:
            if tag not in VOID_ELEMENTS:
                self._ancestor_stack.append((tag, attrs_dict))
            return
        if duplicates:
            self.errors.append(
                f"复制区 <{tag}> 含重复属性："
                + ", ".join(sorted(set(duplicates)))
            )
        self._append(self.get_starttag_text())
        if tag not in VOID_ELEMENTS:
            self._stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        tag = tag.lower()
        attrs_dict, duplicates = attrs_first_wins(attrs)
        if self._parts is None and attrs_dict.get("id") == "wechat-content":
            invalid_ancestors = [
                ancestor_tag
                for ancestor_tag, _ in self._ancestor_stack
                if ancestor_tag in NON_ORDINARY_COPY_ROOT_ANCESTORS
            ]
            if invalid_ancestors:
                self.errors.append(
                    "复制根位于浏览器非普通文档树祖先内："
                    + " > ".join(f"<{item}>" for item in invalid_ancestors)
                )
            else:
                self.errors.append("复制根不能使用自闭合标签")
        if self._parts is not None and duplicates:
            self.errors.append(
                f"复制区 <{tag}> 含重复属性："
                + ", ".join(sorted(set(duplicates)))
            )
        self._append(self.get_starttag_text())

    def handle_endtag(self, tag):
        if self._parts is None:
            tag = tag.lower()
            for offset in range(len(self._ancestor_stack) - 1, -1, -1):
                if self._ancestor_stack[offset][0] == tag:
                    del self._ancestor_stack[offset:]
                    break
            return
        tag = tag.lower()
        if tag not in self._stack:
            self.errors.append(f"复制区内出现无匹配起始标签的 </{tag}>")
            return
        matching_offset = len(self._stack) - 1 - self._stack[::-1].index(tag)
        if matching_offset != len(self._stack) - 1:
            unclosed = ", ".join(f"<{item}>" for item in self._stack[matching_offset + 1 :])
            self.errors.append(f"</{tag}> 前存在未闭合标签：{unclosed}")
        if matching_offset == 0:
            self.roots.append("".join(self._parts))
            self.root_tags.append(self._root_tag)
            self._parts = None
            self._stack = []
            self._root_tag = None
            return
        self._append(f"</{tag}>")
        del self._stack[matching_offset:]

    def handle_data(self, data):
        self._append(data)

    def handle_comment(self, data):
        self._append(f"<!--{data}-->")

    def handle_entityref(self, name):
        self._append(f"&{name};")

    def handle_charref(self, name):
        self._append(f"&#{name};")


def find_copy_roots(document):
    parser = CopyRootExtractor()
    parser.feed(document)
    parser.close()
    return parser.roots


def find_copy_root_tags(document):
    parser = CopyRootExtractor()
    parser.feed(document)
    parser.close()
    return parser.root_tags


class CopyRootIdCounter(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.count = 0

    def handle_starttag(self, tag, attrs):
        attrs_dict, _ = attrs_first_wins(attrs)
        if attrs_dict.get("id") == "wechat-content":
            self.count += 1

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)


def count_copy_root_ids(document):
    parser = CopyRootIdCounter()
    parser.feed(document)
    return parser.count


def get_copy_html(document, allow_fragment=False):
    """Return the unique copy region, or the whole document in explicit fragment mode."""

    parser = CopyRootExtractor()
    parser.feed(document)
    parser.close()
    roots = parser.roots
    root_id_count = count_copy_root_ids(document)
    if parser._parts is not None:
        parser.errors.append("复制区起始标签没有闭合")
    if root_id_count == 1 and parser.errors:
        raise ValueError(f"复制区 HTML 结构异常：{parser.errors[0]}")
    if len(roots) == 1 and root_id_count == 1:
        if parser.root_tags != ["div"]:
            actual = parser.root_tags[0] if parser.root_tags else "未知"
            raise ValueError(
                "复制根 #wechat-content 必须使用 <div>，"
                f"不能使用 <{actual}>；块级正文会被浏览器移出非安全容器"
            )
        return roots[0]
    if allow_fragment and root_id_count == 0:
        return document
    if root_id_count == 0:
        raise ValueError("未找到唯一复制区 #wechat-content；裸片段请显式加 --fragment")
    raise ValueError(f"发现 {root_id_count} 个 #wechat-content，复制边界必须唯一")


def split_css_declarations(style):
    """Split inline CSS without breaking semicolons inside strings or functions."""

    parts = []
    current = []
    quote = None
    paren_depth = 0
    escaped = False
    for char in style or "":
        if escaped:
            current.append(char)
            escaped = False
            continue
        if char == "\\":
            current.append(char)
            escaped = True
            continue
        if quote:
            current.append(char)
            if char == quote:
                quote = None
            continue
        if char in {'"', "'"}:
            quote = char
            current.append(char)
            continue
        if char == "(":
            paren_depth += 1
            current.append(char)
            continue
        if char == ")":
            paren_depth = max(0, paren_depth - 1)
            current.append(char)
            continue
        if char == ";" and paren_depth == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(char)
    if current:
        parts.append("".join(current))
    return parts


def parse_inline_style(style):
    """Return the declarations that win the inline CSS cascade.

    A previous ``!important`` declaration beats a later non-important duplicate;
    declarations with equal priority keep normal "last declaration wins" order.
    Keeping the original value lets callers report the evidence while their own
    cleaners remove the optional priority marker.
    """

    # CSS comments are token separators, not semantic content. Removing them
    # before splitting prevents values such as ``display:/**/flex`` from
    # bypassing exact-property checks.
    style = re.sub(r"/\*.*?\*/", "", style or "", flags=re.S)
    declarations = {}
    priorities = {}
    for declaration in split_css_declarations(style):
        if ":" not in declaration:
            continue
        prop, value = declaration.split(":", 1)
        prop = prop.strip().lower()
        if not prop:
            continue
        value = value.strip()
        important = bool(re.search(r"!\s*important\s*$", value, flags=re.I))
        if prop not in declarations or important or not priorities[prop]:
            declarations[prop] = value
            priorities[prop] = important
    return declarations
