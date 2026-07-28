#!/usr/bin/env python3
import os
import json
import shutil
import struct
import subprocess
import tempfile
import unittest
import re
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
EXAMPLES = SKILL_ROOT / "assets" / "examples"

COPY_FUNCTION = """async function copyContent() {
  const el = document.getElementById('wechat-content');
  const btn = document.getElementById('copy-btn');
  let ok = false;
  // 首选 Clipboard API：同时写入 text/html 与 text/plain
  try {
    const item = new ClipboardItem({
      'text/html': new Blob([el.innerHTML], { type: 'text/html' }),
      'text/plain': new Blob([el.innerText], { type: 'text/plain' })
    });
    await navigator.clipboard.write([item]);
    ok = true;
  } catch (e) { /* 走兜底 */ }
  // 兜底：选区复制（与手动全选复制等效）
  if (!ok) {
    const range = document.createRange();
    range.selectNodeContents(el);
    const sel = window.getSelection();
    sel.removeAllRanges();
    sel.addRange(range);
    ok = document.execCommand('copy');
    sel.removeAllRanges();
  }
  if (ok) {
    btn.classList.add('done');
    btn.textContent = '✓ 已复制，去编辑器粘贴';
    setTimeout(() => { btn.classList.remove('done'); btn.textContent = '一键复制到公众号'; }, 3000);
  } else {
    alert('自动复制失败：请手动选中下方全部内容后复制');
  }
}"""


def preview_document(body, comment=None, shell_extra=""):
    style_comment = (
        comment
        if comment is not None
        else "<!-- 风格方向: 测试方向 | 备选: 方向甲 / 方向乙 -->"
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>测试预览</title>
{shell_extra}
</head>
<body>
<button id="copy-btn" onclick="copyContent()">一键复制</button>
<button id="width-btn" onclick="document.body.classList.toggle('phone')">手机宽度</button>
<div id="wechat-content">
{style_comment}
{body}
</div>
<script>
{COPY_FUNCTION}
</script>
</body>
</html>
"""


def basic_body(extra_style="", text="这是中文正文。"):
    return (
        '<section style="background-color: #fefefe; padding: 24px;">'
        f'<p style="margin: 0; color: #333333; font-size: 15px; {extra_style}">'
        f"{text}</p></section>"
    )


class ValidatorTestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="wechat-validator-tests-")
        self.temp_root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, text):
        path = self.temp_root / name
        path.write_text(text, encoding="utf-8")
        return path

    def run_script(self, script, *args):
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(
            ["python3", str(SCRIPTS / script), *map(str, args)],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

    def assert_passes(self, script, path):
        result = self.run_script(script, path)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def assert_fails(self, script, path, expected_code=1):
        result = self.run_script(script, path)
        self.assertEqual(
            result.returncode,
            expected_code,
            result.stdout + result.stderr,
        )
        return result

    def test_text_transform_is_allowed_but_transform_is_not(self):
        allowed = self.write(
            "allowed.html",
            preview_document(basic_body("text-transform: uppercase;")),
        )
        self.assert_passes("verify-wechat-compat.py", allowed)

        forbidden = self.write(
            "forbidden.html",
            preview_document(basic_body("transform: scale(1);")),
        )
        result = self.assert_fails("verify-wechat-compat.py", forbidden)
        self.assertIn("transform", result.stdout)

    def test_background_position_is_allowed_but_position_is_not(self):
        allowed = self.write(
            "background-position.html",
            preview_document(basic_body("background-position: center;")),
        )
        self.assert_passes("verify-wechat-compat.py", allowed)
        forbidden = self.write(
            "position.html",
            preview_document(basic_body("position: relative;")),
        )
        self.assert_fails("verify-wechat-compat.py", forbidden)

    def test_text_rgba_is_allowed_but_background_rgba_is_not(self):
        allowed = self.write(
            "text-rgba.html",
            preview_document(basic_body("color: rgba(0,0,0,0.7);")),
        )
        self.assert_passes("verify-wechat-compat.py", allowed)
        forbidden = self.write(
            "background-rgba.html",
            preview_document(
                basic_body("background-color: rgba(0,0,0,0.1);")
            ),
        )
        self.assert_fails("verify-wechat-compat.py", forbidden)

    def test_css_hard_rule_matrix(self):
        forbidden_declarations = [
            "-webkit-transform: scale(1);",
            "display: inline-flex;",
            "gap: 8px;",
            "background: #fefefe;",
            "background-image: linear-gradient(#000,#fff);",
            "background-color: #ffffff;",
            "margin-left: -1px;",
            "margin-top: 5%;",
            "height: 50%;",
            "transition: color .2s;",
            "background-color: rgb(0 0 0 / 50%);",
            "background-color: #00000080;",
            "background-color: #0008;",
            "background-color: hsl(0 0% 0% / 50%);",
            "background-color: transparent;",
            "margin-left: calc(-1px);",
            "--bg: rgba(0,0,0,.2); background-color: var(--bg);",
            "--m: calc(-20px); margin-top: var(--m);",
            "opacity: calc(0);",
            "text-indent: -9999px;",
            r"display: flex !\69mportant; display: block;",
            "color: color(srgb 0.1 0.2 0.3);",
            "color: hwb(216 8% 78%);",
            "color: color-mix(in srgb, #000 50%, #fff);",
        ]
        for index, declaration in enumerate(forbidden_declarations):
            with self.subTest(declaration=declaration):
                path = self.write(
                    f"css-{index}.html",
                    preview_document(basic_body(declaration)),
                )
                self.assert_fails("verify-wechat-compat.py", path)

        effective_safe = self.write(
            "important-effective-safe.html",
            preview_document(
                basic_body(
                    "display: block !important; display: flex; "
                    "background-color: #fefefe !important; "
                    "background-color: rgba(0,0,0,.2);"
                )
            ),
        )
        self.assert_passes("verify-wechat-compat.py", effective_safe)

    def test_important_declaration_wins_over_later_nonimportant_value(self):
        declarations = [
            "display: flex !important; display: block;",
            "background-color: rgba(0,0,0,.2) !important; background-color: #fefefe;",
            "margin-left: -10px !important; margin-left: 0;",
            "display:/**/flex!important; display:block;",
        ]
        for index, declaration in enumerate(declarations):
            with self.subTest(declaration=declaration):
                path = self.write(
                    f"important-{index}.html",
                    preview_document(basic_body(declaration)),
                )
                self.assert_fails("verify-wechat-compat.py", path)

    def test_forbidden_words_in_text_or_comment_do_not_trigger_css_rules(self):
        body = (
            "<!-- 这里讨论 transform 与 gradient -->"
            + basic_body(text="正文会讨论 position、background 与 gradient。")
        )
        path = self.write("words-only.html", preview_document(body))
        self.assert_passes("verify-wechat-compat.py", path)

    def test_preview_shell_css_and_script_are_outside_compat_scope(self):
        document = preview_document(
            basic_body(),
            shell_extra="<style>.toolbar { display:flex; position:sticky; }</style>",
        )
        path = self.write("shell.html", document)
        self.assert_passes("verify-wechat-compat.py", path)

    def test_forbidden_tag_and_event_attribute_fail(self):
        tag = self.write(
            "tag.html",
            preview_document(basic_body() + "<ul><li>禁用列表</li></ul>"),
        )
        self.assert_fails("verify-wechat-compat.py", tag)
        event = self.write(
            "event.html",
            preview_document(basic_body() + '<p onclick="x()">事件</p>'),
        )
        self.assert_fails("verify-wechat-compat.py", event)

    def test_image_and_link_contracts(self):
        good = self.write(
            "media-good.html",
            preview_document(
                basic_body()
                + '<img src="https://example.com/a.png" '
                'style="width: 100%; height: auto; display: block;">'
                + '<a href="https://mp.weixin.qq.com/s/demo" '
                'style="color: #333333;">公众号链接</a>'
            ),
        )
        self.assert_passes("verify-wechat-compat.py", good)
        bad = self.write(
            "media-bad.html",
            preview_document(
                basic_body()
                + '<img src="./a.png" style="width: 90%;">'
                + '<a href="https://example.com">外链</a>'
            ),
        )
        self.assert_fails("verify-wechat-compat.py", bad)

    def test_dark_outer_requires_direct_skeleton_and_td_border(self):
        valid_outer = """
<section data-role="outer" style="background-color: #080808; padding: 0;">
<table width="100%" cellspacing="0" cellpadding="0" border="0"
 style="border-collapse: collapse; border-spacing: 0; background-color: #080808; border: none;">
<tr><td style="border: none; background-color: #080808; padding: 24px;">
<p style="font-size: 15px; color: #fefefe; margin: 0;">深色中文正文。</p>
</td></tr></table></section>
"""
        valid = self.write("outer-valid.html", preview_document(valid_outer))
        self.assert_passes("verify-wechat-compat.py", valid)

        bad_outer = valid_outer.replace("border: none; background-color", "background-color", 1)
        bad = self.write("outer-bad.html", preview_document(bad_outer))
        self.assert_fails("verify-wechat-compat.py", bad)

        nested_only = valid_outer.replace(
            "<table width=\"100%\"",
            '<section style="padding: 0;"><table width="100%"',
            1,
        ).replace(
            "</td></tr></table></section>",
            "</td></tr></table></section></section>",
            1,
        )
        nested = self.write("outer-nested.html", preview_document(nested_only))
        self.assert_fails("verify-wechat-compat.py", nested)

    def test_marked_divider_requires_zero_font_and_line_height(self):
        body = """
<section data-role="outer" style="background-color: #080808; padding: 0;">
<table width="100%" cellspacing="0" cellpadding="0" border="0"
 style="border-collapse: collapse; border-spacing: 0; background-color: #080808; border: none;">
<tr><td data-role="divider" style="border: none; font-size: 12px; line-height: 1;">中文</td></tr>
</table></section>
"""
        path = self.write("divider.html", preview_document(body))
        self.assert_fails("verify-wechat-compat.py", path)

    def test_table_cannot_own_overflow_clipping(self):
        body = basic_body() + (
            '<table width="100%" style="border-radius: 8px; overflow: hidden;">'
            '<tr><td style="border: none;">表格</td></tr></table>'
        )
        path = self.write("table-clipping.html", preview_document(body))
        self.assert_fails("verify-wechat-compat.py", path)

    def test_missing_copy_root_is_infrastructure_error(self):
        path = self.write("no-root.html", "<section>中文</section>")
        self.assert_fails("verify-wechat-compat.py", path, expected_code=2)

    def test_copy_root_must_be_browser_safe_div(self):
        document = preview_document(basic_body()).replace(
            '<div id="wechat-content">',
            '<p id="wechat-content">',
            1,
        ).replace(
            "</div>\n<script>",
            "</p>\n<script>",
            1,
        )
        path = self.write("unsafe-copy-root.html", document)
        source = self.write("unsafe-copy-root.md", "这是中文正文。")
        checks = (
            ("verify-completeness.py", source, path),
            ("verify-wechat-compat.py", path),
            ("verify-output-contract.py", path),
        )
        for command in checks:
            with self.subTest(script=command[0]):
                result = self.run_script(*command)
                self.assertEqual(
                    result.returncode,
                    2,
                    result.stdout + result.stderr,
                )
                self.assertIn("必须使用 <div>", result.stdout)

    def test_copy_root_must_be_in_live_document_tree(self):
        source = self.write("inert-copy-root.md", "这是中文正文。")
        for ancestor in ("template", "dialog"):
            document = preview_document(basic_body()).replace(
                '<div id="wechat-content">',
                f'<{ancestor}><div id="wechat-content">',
                1,
            ).replace(
                "</div>\n<script>",
                f"</div></{ancestor}>\n<script>",
                1,
            )
            path = self.write(f"inert-copy-root-{ancestor}.html", document)
            checks = (
                ("verify-completeness.py", source, path),
                ("verify-wechat-compat.py", path),
                ("verify-output-contract.py", path),
                (
                    "verify-mobile-render.py",
                    path,
                    "--screenshot",
                    self.temp_root / f"inert-copy-root-{ancestor}.png",
                ),
            )
            for command in checks:
                with self.subTest(ancestor=ancestor, script=command[0]):
                    result = self.run_script(*command)
                    self.assertEqual(
                        result.returncode,
                        2,
                        result.stdout + result.stderr,
                    )
                    self.assertIn("非普通文档树", result.stdout)

    def test_copy_root_and_ancestors_cannot_be_explicitly_hidden(self):
        source = self.write("hidden-copy-root.md", "这是中文正文。")
        variants = (
            preview_document(basic_body()).replace(
                '<div id="wechat-content">',
                '<div id="wechat-content" hidden>',
                1,
            ),
            preview_document(basic_body()).replace(
                '<div id="wechat-content">',
                '<section style="display: none;"><div id="wechat-content">',
                1,
            ).replace(
                "</div>\n<script>",
                "</div></section>\n<script>",
                1,
            ),
        )
        for index, document in enumerate(variants):
            path = self.write(f"hidden-copy-root-{index}.html", document)
            for command in (
                ("verify-completeness.py", source, path),
                ("verify-wechat-compat.py", path),
                ("verify-output-contract.py", path),
                (
                    "verify-mobile-render.py",
                    path,
                    "--screenshot",
                    self.temp_root / f"hidden-copy-root-{index}.png",
                ),
            ):
                with self.subTest(index=index, script=command[0]):
                    result = self.run_script(*command)
                    self.assertEqual(
                        result.returncode,
                        2,
                        result.stdout + result.stderr,
                    )
                    self.assertIn("显式隐藏", result.stdout)

    def test_malformed_copy_root_cannot_truncate_checked_content(self):
        document = preview_document(basic_body()).replace(
            "</div>\n<script>",
            "</bogus><script>window.bad = true;</script></div>\n<script>",
            1,
        )
        path = self.write("malformed-root.html", document)
        for script in (
            "verify-wechat-compat.py",
            "verify-output-contract.py",
        ):
            with self.subTest(script=script):
                self.assert_fails(script, path, expected_code=2)

    def test_duplicate_html_attributes_follow_browser_semantics_and_fail(self):
        duplicate_root = self.write(
            "duplicate-root-attribute.html",
            preview_document(basic_body()).replace(
                '<div id="wechat-content">',
                '<div id="not-the-root" id="wechat-content">',
                1,
            ),
        )
        source = self.write("duplicate-root-source.md", "这是中文正文。")
        self.assert_fails(
            "verify-wechat-compat.py",
            duplicate_root,
            expected_code=2,
        )
        contract = self.assert_fails(
            "verify-output-contract.py",
            duplicate_root,
            expected_code=1,
        )
        self.assertIn("复制区", contract.stdout)
        completeness = self.run_script(
            "verify-completeness.py",
            source,
            duplicate_root,
        )
        self.assertEqual(
            completeness.returncode,
            2,
            completeness.stdout + completeness.stderr,
        )

        duplicate_inner = self.write(
            "duplicate-inner-attribute.html",
            preview_document(
                '<p style="color: #333333;" '
                'style="display: none;">这是中文正文。</p>'
            ),
        )
        self.assert_fails(
            "verify-wechat-compat.py",
            duplicate_inner,
            expected_code=2,
        )

    def test_hidden_content_is_rejected_by_static_gates(self):
        hidden_variants = [
            '<p style="display: none;">必须展示的正文。</p>',
            '<p style="visibility: hidden;">必须展示的正文。</p>',
            '<p style="opacity: 0;">必须展示的正文。</p>',
            '<p style="color: transparent;">必须展示的正文。</p>',
            '<p style="font-size: 0;">必须展示的正文。</p>',
            '<p style="font-size: 0.1px;">必须展示的正文。</p>',
            "<p hidden>必须展示的正文。</p>",
        ]
        for index, body in enumerate(hidden_variants):
            with self.subTest(body=body):
                hidden_variant = self.write(
                    f"hidden-{index}.html",
                    preview_document(body),
                )
                compat = self.assert_fails(
                    "verify-wechat-compat.py",
                    hidden_variant,
                )
                self.assertIn("隐藏内容", compat.stdout)

        hidden = self.write("hidden.html", preview_document(hidden_variants[0]))
        source = self.write("hidden-source.md", "必须展示的正文。")
        completeness = self.run_script(
            "verify-completeness.py",
            source,
            hidden,
        )
        self.assertEqual(
            completeness.returncode,
            1,
            completeness.stdout + completeness.stderr,
        )

    def test_output_contract_accepts_complete_preview(self):
        path = self.write("contract-good.html", preview_document(basic_body()))
        self.assert_passes("verify-output-contract.py", path)

    def test_output_contract_requires_copy_logic_inside_copy_function(self):
        document = preview_document(basic_body()).replace(
            "function copyContent() {",
            "function doCopy() {",
            1,
        ).replace(
            "</script>",
            "function copyContent() {}\n</script>",
            1,
        )
        path = self.write("dead-copy-function.html", document)
        result = self.assert_fails("verify-output-contract.py", path)
        self.assertIn("预览脚本使用已审计", result.stdout)

        early_return = self.write(
            "early-return-copy.html",
            preview_document(basic_body()).replace(
                "function copyContent() {",
                "function copyContent() {\n  return;",
                1,
            ),
        )
        self.assert_fails("verify-output-contract.py", early_return)

        dead_button = self.write(
            "dead-copy-button.html",
            preview_document(basic_body()).replace(
                'onclick="copyContent()"',
                'onclick="false &amp;&amp; copyContent()"',
                1,
            ),
        )
        self.assert_fails("verify-output-contract.py", dead_button)

        inert_script = self.write(
            "inert-copy-script.html",
            preview_document(basic_body()).replace(
                "<script>",
                '<script type="application/json">',
                1,
            ),
        )
        self.assert_fails("verify-output-contract.py", inert_script)
        for index, attributes in enumerate(
            ('src="data:text/javascript,"', "nomodule")
        ):
            with self.subTest(script_attributes=attributes):
                inert_variant = self.write(
                    f"inert-copy-script-{index}.html",
                    preview_document(basic_body()).replace(
                        "<script>",
                        f"<script {attributes}>",
                        1,
                    ),
                )
                self.assert_fails(
                    "verify-output-contract.py",
                    inert_variant,
                )

        overridden_handler = self.write(
            "overridden-copy-handler.html",
            preview_document(basic_body()).replace(
                "</script>",
                "document.getElementById('copy-btn').onclick = function() {};\n"
                "</script>",
                1,
            ),
        )
        self.assert_fails("verify-output-contract.py", overridden_handler)

        disabled_button = self.write(
            "disabled-copy-button.html",
            preview_document(basic_body()).replace(
                '<button id="copy-btn"',
                '<button id="copy-btn" disabled',
                1,
            ),
        )
        self.assert_fails("verify-output-contract.py", disabled_button)

        hidden_button = self.write(
            "hidden-copy-button.html",
            preview_document(basic_body()).replace(
                '<button id="copy-btn"',
                '<button hidden id="copy-btn"',
                1,
            ),
        )
        self.assert_fails("verify-output-contract.py", hidden_button)

        hidden_button_ancestor = self.write(
            "hidden-copy-button-ancestor.html",
            preview_document(basic_body()).replace(
                '<button id="copy-btn" onclick="copyContent()">'
                "一键复制</button>",
                '<div style="visibility: hidden;">'
                '<button id="copy-btn" onclick="copyContent()">'
                "一键复制</button></div>",
                1,
            ),
        )
        self.assert_fails(
            "verify-output-contract.py",
            hidden_button_ancestor,
        )

        dialog_button_ancestor = self.write(
            "dialog-copy-button-ancestor.html",
            preview_document(basic_body()).replace(
                '<button id="copy-btn" onclick="copyContent()">'
                "一键复制</button>",
                '<dialog><button id="copy-btn" onclick="copyContent()">'
                "一键复制</button></dialog>",
                1,
            ),
        )
        self.assert_fails(
            "verify-output-contract.py",
            dialog_button_ancestor,
        )

        disabled_fieldset_ancestor = self.write(
            "disabled-fieldset-copy-button.html",
            preview_document(basic_body()).replace(
                '<button id="copy-btn" onclick="copyContent()">'
                "一键复制</button>",
                '<fieldset disabled>'
                '<button id="copy-btn" onclick="copyContent()">'
                "一键复制</button></fieldset>",
                1,
            ),
        )
        self.assert_fails(
            "verify-output-contract.py",
            disabled_fieldset_ancestor,
        )

        original = preview_document(basic_body())
        function = re.search(
            r"function copyContent\(\) \{.*?\n\}",
            original,
            flags=re.S,
        )
        self.assertIsNotNone(function)
        string_only = (
            "function copyContent() {\n"
            "  const fake = `const el = "
            "document.getElementById('wechat-content'); "
            "new ClipboardItem({'text/html': "
            "new Blob([el.innerHTML])}); "
            "navigator.clipboard.write([]);`;\n"
            "}"
        )
        string_spoof = self.write(
            "string-spoof-copy.html",
            original[: function.start()]
            + string_only
            + original[function.end() :],
        )
        self.assert_fails("verify-output-contract.py", string_spoof)

    def test_output_contract_rejects_bad_style_comment_and_placeholders(self):
        one_alt = self.write(
            "one-alt.html",
            preview_document(
                basic_body(),
                comment="<!-- 风格方向: 测试 | 备选: 只有一个 -->",
            ),
        )
        self.assert_fails("verify-output-contract.py", one_alt)
        unresolved = self.write(
            "unresolved.html",
            preview_document(basic_body(text="{{文章标题}}")),
        )
        self.assert_fails("verify-output-contract.py", unresolved)
        duplicate = self.write(
            "duplicate-root.html",
            preview_document(basic_body()).replace(
                "</body>",
                '<div id="wechat-content"><p>第二复制区</p></div></body>',
            ),
        )
        self.assert_fails("verify-output-contract.py", duplicate)
        plain_text_only = self.write(
            "plain-text-copy.html",
            preview_document(basic_body()).replace(
                "await navigator.clipboard.write([item]);",
                "await navigator.clipboard.writeText(el.innerText);",
                1,
            ),
        )
        self.assert_fails("verify-output-contract.py", plain_text_only)

        real_document = preview_document(basic_body())
        function = re.search(
            r"function copyContent\(\) \{(?P<body>.*?)\n\}",
            real_document,
            flags=re.S,
        )
        self.assertIsNotNone(function)
        fake_function = (
            "function copyContent() {\n"
            "  /*"
            + function.group("body")
            + "\n  */\n"
            "}"
        )
        comment_spoof = self.write(
            "comment-spoof.html",
            real_document[: function.start()]
            + fake_function
            + real_document[function.end() :],
        )
        self.assert_fails("verify-output-contract.py", comment_spoof)

    def run_completeness(self, source_text, visible_html):
        source = self.write("source.md", source_text)
        output = self.write("output.html", preview_document(visible_html))
        return self.run_script("verify-completeness.py", source, output)

    def test_completeness_exact_match_with_layout_text(self):
        source = "# 短\n\n第一句。\n第二句！"
        visible = (
            "<p>短</p><p>第一句。</p><p>第二句！</p>"
            '<p data-layout-text="true">— END —</p>'
        )
        result = self.run_completeness(source, visible)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        shared_generic_word = self.run_completeness(
            "请保存这些资料。",
            "<p>请保存这些资料。</p>"
            '<p data-layout-text="true">参考资料</p>',
        )
        self.assertEqual(
            shared_generic_word.returncode,
            0,
            shared_generic_word.stdout + shared_generic_word.stderr,
        )

        short_generic_word = self.run_completeness(
            "整理参考资料",
            "<p>整理参考资料</p>"
            '<span data-layout-text="true">资料</span>',
        )
        self.assertEqual(
            short_generic_word.returncode,
            0,
            short_generic_word.stdout + short_generic_word.stderr,
        )

    def test_completeness_detects_reorder_duplicate_and_punctuation(self):
        source = "第一句。\n第二句！"
        cases = [
            "<p>第二句！</p><p>第一句。</p>",
            "<p>第一句。</p><p>第一句。</p><p>第二句！</p>",
            "<p>第一句，</p><p>第二句！</p>",
        ]
        for index, visible in enumerate(cases):
            with self.subTest(index=index):
                result = self.run_completeness(source, visible)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)

    def test_completeness_ignores_shell_and_preserves_source_multiplicity(self):
        shell_only = self.run_completeness("一键复制", "<p>别的正文</p>")
        self.assertEqual(shell_only.returncode, 1, shell_only.stdout)
        repeated = self.run_completeness(
            "相同一句。\n相同一句。",
            "<p>相同一句。</p>",
        )
        self.assertEqual(repeated.returncode, 1, repeated.stdout)

    def test_completeness_supports_markdown_link_reference_transform(self):
        result = self.run_completeness(
            "参考[官方文档](https://example.com)。",
            "<p>参考官方文档。</p>"
            '<p data-layout-text="true">[1] https://example.com</p>',
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_completeness_preserves_code_and_english_word_spaces(self):
        inline = self.run_completeness(
            "使用 `foo_bar`，再运行 `a*b*c`。",
            "<p>使用 foo_bar，再运行 a*b*c。</p>",
        )
        self.assertEqual(inline.returncode, 0, inline.stdout + inline.stderr)

        fenced = self.run_completeness(
            "代码如下：\n\n```text\nfoo_bar\na*b*c\n```",
            "<p>代码如下：</p><p>foo_bar<br>a*b*c</p>",
        )
        self.assertEqual(fenced.returncode, 0, fenced.stdout + fenced.stderr)

        missing_space = self.run_completeness(
            "Use GPT 5 responsibly.",
            "<p>UseGPT5 responsibly.</p>",
        )
        self.assertEqual(
            missing_space.returncode,
            1,
            missing_space.stdout + missing_space.stderr,
        )

        compact_blocks = self.run_completeness(
            "My Title\nHello world.",
            "<p>My Title</p><p>Hello world.</p>",
        )
        self.assertEqual(
            compact_blocks.returncode,
            0,
            compact_blocks.stdout + compact_blocks.stderr,
        )

    def test_completeness_rejects_layout_marker_hiding_duplicate_source(self):
        result = self.run_completeness(
            "这句话不能重复。",
            "<p>这句话不能重复。</p>"
            '<p data-layout-text="true">这句话不能重复。</p>',
        )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("data-layout-text", result.stdout)

        short = self.run_completeness(
            "好",
            '<p>好</p><span data-layout-text="true">好</span>',
        )
        self.assertEqual(short.returncode, 1, short.stdout + short.stderr)

        split = self.run_completeness(
            "今天很好。明天继续。",
            "<p>今天很好。明天继续。</p>"
            '<span data-layout-text="true">今</span>'
            '<span data-layout-text="true">天</span>'
            '<span data-layout-text="true">很</span>'
            '<span data-layout-text="true">好</span>'
            '<span data-layout-text="true">。</span>',
        )
        self.assertEqual(split.returncode, 1, split.stdout + split.stderr)

        decorated = self.run_completeness(
            "雨夜散步",
            "<p>雨夜散步</p>"
            '<span data-layout-text="true">★雨夜散步★</span>',
        )
        self.assertEqual(
            decorated.returncode,
            1,
            decorated.stdout + decorated.stderr,
        )

        word_wrapped = self.run_completeness(
            "雨夜散步。雨落在伞面上。",
            "<p>雨夜散步。</p><p>雨落在伞面上。</p>"
            '<span data-layout-text="true">TITLE雨夜散步TITLE</span>',
        )
        self.assertEqual(
            word_wrapped.returncode,
            1,
            word_wrapped.stdout + word_wrapped.stderr,
        )

        interleaved = self.run_completeness(
            "雨夜散步",
            "<p>雨夜散步</p>"
            '<span data-layout-text="true">雨1夜2散3步</span>',
        )
        self.assertEqual(
            interleaved.returncode,
            1,
            interleaved.stdout + interleaved.stderr,
        )

        case_changed = self.run_completeness(
            "Hello",
            "<p>Hello</p>"
            '<span data-layout-text="true">★HELLO★</span>',
        )
        self.assertEqual(
            case_changed.returncode,
            1,
            case_changed.stdout + case_changed.stderr,
        )

    def test_completeness_requires_original_url_target(self):
        result = self.run_completeness(
            "参考[官方文档](https://example.com/original)。",
            "<p>参考官方文档。</p>"
            '<p data-layout-text="true">[1] https://example.com/changed</p>',
        )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("https://example.com/original", result.stdout)

        prefix_spoof = self.run_completeness(
            "参考[官方文档](https://example.com/original)。",
            "<p>参考官方文档。</p>"
            '<p data-layout-text="true">'
            "[1] https://example.com/original.evil"
            "</p>",
        )
        self.assertEqual(
            prefix_spoof.returncode,
            1,
            prefix_spoof.stdout + prefix_spoof.stderr,
        )

    def test_style_showcases_are_compat_and_contract_examples(self):
        for example in sorted(EXAMPLES.glob("*.html")):
            with self.subTest(example=example.name, check="compat"):
                self.assert_passes("verify-wechat-compat.py", example)
            with self.subTest(example=example.name, check="contract"):
                self.assert_passes("verify-output-contract.py", example)

    def test_four_gate_sample_has_exact_source_pair(self):
        source = EXAMPLES / "four-gate-sample.md"
        output = EXAMPLES / "four-gate-sample.html"
        result = self.run_script("verify-completeness.py", source, output)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


def available_chrome():
    if os.environ.get("CHROME_BIN") and Path(os.environ["CHROME_BIN"]).is_file():
        return True
    if any(
        shutil.which(name)
        for name in ("google-chrome", "chromium", "chromium-browser", "chrome")
    ):
        return True
    return Path(
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    ).is_file()


@unittest.skipUnless(available_chrome(), "Chrome/Chromium is not installed")
class MobileRenderTestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="wechat-mobile-tests-")
        self.temp_root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, text):
        path = self.temp_root / name
        path.write_text(text, encoding="utf-8")
        return path

    def run_script(self, script, *args):
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(
            ["python3", str(SCRIPTS / script), *map(str, args)],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

    def test_real_mobile_render_passes_and_has_exact_png_size(self):
        document = preview_document(
            basic_body(),
            shell_extra="<style>.toolbar { display: flex; }</style>",
        ).replace(
            '<div id="wechat-content">',
            '<p style="font-size: 9px;">外壳中文小字</p>'
            '<img src="./shell-missing.png">'
            '<div id="wechat-content">',
        )
        path = self.write("mobile-good.html", document)
        screenshot = self.temp_root / "good.png"
        report_path = self.temp_root / "good.json"
        result = self.run_script(
            "verify-mobile-render.py",
            path,
            "--screenshot",
            screenshot,
            "--json-report",
            report_path,
            "--timeout-ms",
            "3000",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        with screenshot.open("rb") as handle:
            header = handle.read(24)
        self.assertEqual(struct.unpack(">II", header[16:24]), (390, 844))
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["capture"]["contentStageWidth"], 390)
        self.assertEqual(report["capture"]["width"], 390)
        self.assertEqual(report["capture"]["height"], 844)
        self.assertIn("browserViewport", report)

    def test_real_mobile_render_rejects_overflow_and_small_chinese(self):
        body = (
            '<section style="width: 500px;">'
            '<p style="font-size: 11px;">过小的中文正文。</p></section>'
            '<img src="./missing.png" style="width: 100%; height: auto; display: block;">'
        )
        path = self.write("mobile-bad.html", preview_document(body))
        result = self.run_script(
            "verify-mobile-render.py",
            path,
            "--screenshot",
            self.temp_root / "bad.png",
            "--timeout-ms",
            "3000",
        )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("横向溢出", result.stdout)
        self.assertIn("中文字号", result.stdout)
        self.assertIn("图片加载失败", result.stdout)

    def test_real_mobile_render_rejects_hidden_chinese(self):
        path = self.write(
            "mobile-hidden.html",
            preview_document(
                '<p style="display: none;">必须展示的正文。</p>'
            ),
        )
        result = self.run_script(
            "verify-mobile-render.py",
            path,
            "--screenshot",
            self.temp_root / "hidden.png",
            "--timeout-ms",
            "3000",
        )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("中文内容不可见", result.stdout)

    def test_real_mobile_render_rejects_nearly_zero_contrast_chinese(self):
        colors = (
            "#152238; text-shadow: 0 0 0 #152238",
            "color(srgb 0.08235 0.13333 0.21961)",
            "#eaf0f5; -webkit-text-fill-color: #152238",
        )
        for index, color in enumerate(colors):
            with self.subTest(color=color):
                body = (
                    '<section style="background-color: #152238; padding: 24px;">'
                    f'<p style="color: {color}; font-size: 16px;">'
                    "与背景同色的中文正文。</p></section>"
                )
                path = self.write(
                    f"mobile-no-contrast-{index}.html",
                    preview_document(body),
                )
                result = self.run_script(
                    "verify-mobile-render.py",
                    path,
                    "--screenshot",
                    self.temp_root / f"no-contrast-{index}.png",
                    "--timeout-ms",
                    "3000",
                )
                self.assertEqual(
                    result.returncode,
                    1,
                    result.stdout + result.stderr,
                )
                self.assertIn("近乎无对比", result.stdout)

        visible_shadow = (
            '<section style="background-color: #152238; padding: 24px;">'
            '<p style="color: #152238; font-size: 16px; '
            'text-shadow: 0 0 2px #fefefe;">'
            "由高对比阴影清楚描出的中文正文。</p></section>"
        )
        visible_path = self.write(
            "mobile-visible-shadow.html",
            preview_document(visible_shadow),
        )
        visible_result = self.run_script(
            "verify-mobile-render.py",
            visible_path,
            "--screenshot",
            self.temp_root / "visible-shadow.png",
            "--timeout-ms",
            "3000",
        )
        self.assertEqual(
            visible_result.returncode,
            0,
            visible_result.stdout + visible_result.stderr,
        )

    def test_real_mobile_render_rejects_unsafe_copy_root(self):
        document = preview_document(basic_body()).replace(
            '<div id="wechat-content">',
            '<p id="wechat-content">',
            1,
        ).replace(
            "</div>\n<script>",
            "</p>\n<script>",
            1,
        )
        path = self.write("mobile-unsafe-root.html", document)
        result = self.run_script(
            "verify-mobile-render.py",
            path,
            "--screenshot",
            self.temp_root / "unsafe-root.png",
            "--timeout-ms",
            "3000",
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("必须使用 <div>", result.stdout)

    def test_real_mobile_render_checks_ancestors_and_offscreen_text(self):
        body = (
            '<section style="opacity: calc(0);">'
            "<p>祖先透明的中文正文。</p></section>"
            '<p style="text-indent: -9999px;">移出屏幕的中文正文。</p>'
        )
        path = self.write("mobile-hidden-advanced.html", preview_document(body))
        result = self.run_script(
            "verify-mobile-render.py",
            path,
            "--screenshot",
            self.temp_root / "hidden-advanced.png",
            "--timeout-ms",
            "3000",
        )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("中文内容不可见", result.stdout)

    def test_non_executable_chrome_is_infrastructure_error(self):
        fake_browser = self.write("not-chrome", "#!/bin/sh\n")
        path = self.write("mobile-browser-error.html", preview_document(basic_body()))
        result = self.run_script(
            "verify-mobile-render.py",
            path,
            "--screenshot",
            self.temp_root / "never-created.png",
            "--chrome",
            fake_browser,
        )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_mobile_outputs_cannot_overwrite_input_or_each_other(self):
        path = self.write("protected-input.html", preview_document(basic_body()))
        original = path.read_text(encoding="utf-8")
        overwrite_input = self.run_script(
            "verify-mobile-render.py",
            path,
            "--screenshot",
            path,
        )
        self.assertEqual(
            overwrite_input.returncode,
            2,
            overwrite_input.stdout + overwrite_input.stderr,
        )
        self.assertEqual(path.read_text(encoding="utf-8"), original)

        shared = self.temp_root / "same-output"
        duplicate_outputs = self.run_script(
            "verify-mobile-render.py",
            path,
            "--screenshot",
            shared,
            "--json-report",
            shared,
        )
        self.assertEqual(
            duplicate_outputs.returncode,
            2,
            duplicate_outputs.stdout + duplicate_outputs.stderr,
        )

    def test_repository_four_gate_sample_really_renders(self):
        screenshot = self.temp_root / "four-gate-sample.png"
        result = self.run_script(
            "verify-mobile-render.py",
            EXAMPLES / "four-gate-sample.html",
            "--screenshot",
            screenshot,
            "--timeout-ms",
            "3000",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        with screenshot.open("rb") as handle:
            header = handle.read(24)
        self.assertEqual(struct.unpack(">II", header[16:24]), (390, 844))


if __name__ == "__main__":
    unittest.main()
