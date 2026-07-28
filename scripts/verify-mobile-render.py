#!/usr/bin/env python3
"""用真实 Chrome/Chromium 在 390px 内容舞台检查公众号复制区。

检查横向溢出、破图、小于 12px 的中文、隐藏中文和近乎无对比中文，
并保存 390×844 首屏截图。

    python3 verify-mobile-render.py article.html \
      --screenshot qa/article-390x844.png \
      [--json-report qa/article-390x844.json] [--chrome /path/to/chrome]

通过返回 0；视觉硬伤返回 1；参数、复制边界或浏览器错误返回 2。
本工具验证 Blink 真实渲染，不替代微信兼容静态检查和发布前手机预览。
"""

import argparse
import base64
import html as html_mod
import json
import os
import platform
import re
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

from wechat_html import get_copy_html


VIEWPORT_WIDTH = 390
VIEWPORT_HEIGHT = 844


MEASURE_SCRIPT = r"""
(function () {
  const stage = document.getElementById('wechat-qa-stage');
  const images = Array.from(stage.querySelectorAll('img'));
  const visible = (element) => {
    const rect = element.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return false;
    let current = element;
    while (current && current !== document.documentElement) {
      const style = getComputedStyle(current);
      const transparent = (value) => {
        const normalized = (value || '').trim().toLowerCase();
        if (normalized === 'transparent') return true;
        if (/^(?:rgba|hsla)\(/.test(normalized)) {
          return /,\s*0(?:\.0+)?\s*\)$/.test(normalized);
        }
        if (/^(?:rgb|hsl)\(/.test(normalized) && normalized.includes('/')) {
          return /\/\s*0(?:\.0+)?%?\s*\)$/.test(normalized);
        }
        return false;
      };
      if (style.display === 'none' ||
          style.visibility === 'hidden' ||
          style.visibility === 'collapse' ||
          Number(style.opacity || 1) === 0 ||
          style.contentVisibility === 'hidden' ||
          transparent(style.color)) {
        return false;
      }
      if (current === stage) break;
      current = current.parentElement;
    }
    return true;
  };
  const selector = (element) => {
    const parts = [];
    let current = element;
    while (current && current !== stage && parts.length < 5) {
      let part = current.tagName.toLowerCase();
      if (current.getAttribute('data-role')) {
        part += '[data-role="' + current.getAttribute('data-role') + '"]';
      }
      if (current.parentElement) {
        const peers = Array.from(current.parentElement.children)
          .filter((item) => item.tagName === current.tagName);
        if (peers.length > 1) part += ':nth-of-type(' + (peers.indexOf(current) + 1) + ')';
      }
      parts.unshift(part);
      current = current.parentElement;
    }
    return parts.join(' > ');
  };
  const parseColor = (value) => {
    const normalized = (value || '').trim().toLowerCase();
    if (normalized === 'transparent') return [0, 0, 0, 0];
    const srgbMatch = normalized.match(/^color\(\s*srgb\s+([^)]*)\)/);
    if (srgbMatch) {
      const tokens = srgbMatch[1].match(/[\d.]+%?/g) || [];
      if (tokens.length < 3) return null;
      const channel = (token) =>
        (token.endsWith('%') ? parseFloat(token) / 100 : parseFloat(token)) * 255;
      const alpha = tokens.length > 3
        ? (tokens[3].endsWith('%') ? parseFloat(tokens[3]) / 100 : parseFloat(tokens[3]))
        : 1;
      return [channel(tokens[0]), channel(tokens[1]), channel(tokens[2]), alpha];
    }
    const rgbMatch = normalized.match(/^rgba?\(([^)]*)\)/);
    if (!rgbMatch) return null;
    const tokens = rgbMatch[1].match(/[\d.]+%?/g) || [];
    if (tokens.length < 3) return null;
    const channel = (token) =>
      token.endsWith('%') ? parseFloat(token) * 2.55 : parseFloat(token);
    const alpha = tokens.length > 3
      ? (tokens[3].endsWith('%') ? parseFloat(tokens[3]) / 100 : parseFloat(tokens[3]))
      : 1;
    return [channel(tokens[0]), channel(tokens[1]), channel(tokens[2]), alpha];
  };
  const composite = (foreground, background) => {
    if (!foreground) return background;
    const alpha = foreground[3] + background[3] * (1 - foreground[3]);
    if (alpha <= 0) return [0, 0, 0, 0];
    return [
      (foreground[0] * foreground[3] +
        background[0] * background[3] * (1 - foreground[3])) / alpha,
      (foreground[1] * foreground[3] +
        background[1] * background[3] * (1 - foreground[3])) / alpha,
      (foreground[2] * foreground[3] +
        background[2] * background[3] * (1 - foreground[3])) / alpha,
      alpha
    ];
  };
  const effectiveBackground = (element) => {
    const chain = [];
    let current = element;
    while (current) {
      chain.unshift(current);
      if (current === document.documentElement) break;
      current = current.parentElement;
    }
    let background = [254, 254, 254, 1];
    for (const node of chain) {
      background = composite(
        parseColor(getComputedStyle(node).backgroundColor),
        background
      );
    }
    return background;
  };
  const luminance = (color) => {
    const linear = color.slice(0, 3).map((channel) => {
      const value = Math.max(0, Math.min(255, channel)) / 255;
      return value <= 0.04045
        ? value / 12.92
        : Math.pow((value + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
  };
  const contrastRatio = (foreground, background) => {
    const foregroundLuminance = luminance(foreground);
    const backgroundLuminance = luminance(background);
    const lighter = Math.max(foregroundLuminance, backgroundLuminance);
    const darker = Math.min(foregroundLuminance, backgroundLuminance);
    return (lighter + 0.05) / (darker + 0.05);
  };

  const measure = () => {
  const stageRect = stage.getBoundingClientRect();
  const textIntersectsStage = (textNode) => {
    const range = document.createRange();
    range.selectNodeContents(textNode);
    const rectangles = Array.from(range.getClientRects());
    return rectangles.some((rect) =>
      rect.width > 0 && rect.height > 0 &&
      rect.right > stageRect.left + 0.5 &&
      rect.left < stageRect.right - 0.5 &&
      rect.bottom > stageRect.top + 0.5
    );
  };
  const overflow = [];
  for (const element of Array.from(stage.querySelectorAll('*'))) {
    if (!visible(element)) continue;
    const rect = element.getBoundingClientRect();
    if (rect.left < stageRect.left - 1 || rect.right > stageRect.right + 1) {
      overflow.push({
        selector: selector(element),
        left: Math.round((rect.left - stageRect.left) * 10) / 10,
        right: Math.round((rect.right - stageRect.right) * 10) / 10,
        width: Math.round(rect.width * 10) / 10
      });
    }
  }

  const brokenImages = images
    .filter((img) => !img.complete || img.naturalWidth === 0)
    .map((img) => img.currentSrc || img.getAttribute('src') || '(missing src)');

  const smallChinese = [];
  const hiddenChinese = [];
  const lowContrastChinese = [];
  const unparsedChineseColors = [];
  const seenSmall = new Set();
  const seenHidden = new Set();
  const seenLowContrast = new Set();
  const seenUnparsedColor = new Set();
  const walker = document.createTreeWalker(stage, NodeFilter.SHOW_TEXT);
  let textNode;
  while ((textNode = walker.nextNode())) {
    const sample = (textNode.nodeValue || '').trim();
    if (!/[\u3400-\u9fff]/.test(sample)) continue;
    const parent = textNode.parentElement;
    if (!parent) continue;
    if (!visible(parent) || !textIntersectsStage(textNode)) {
      const key = selector(parent) + '|' + sample.slice(0, 36);
      if (!seenHidden.has(key)) {
        seenHidden.add(key);
        hiddenChinese.push({
          selector: selector(parent),
          text: sample.slice(0, 36)
        });
      }
      continue;
    }
    const style = getComputedStyle(parent);
    const size = parseFloat(style.fontSize);
    if (size < 12) {
      const key = selector(parent) + '|' + size + '|' + sample.slice(0, 36);
      if (!seenSmall.has(key)) {
        seenSmall.add(key);
        smallChinese.push({
          selector: selector(parent),
          fontSize: size,
          text: sample.slice(0, 36)
        });
      }
    }
    const background = effectiveBackground(parent);
    const fillColor = parseColor(style.webkitTextFillColor);
    const textColor = fillColor || parseColor(style.color);
    if (!textColor) {
      const key = selector(parent) + '|' + style.color + '|' + sample.slice(0, 36);
      if (!seenUnparsedColor.has(key)) {
        seenUnparsedColor.add(key);
        unparsedChineseColors.push({
          selector: selector(parent),
          color: style.color,
          text: sample.slice(0, 36)
        });
      }
      continue;
    }
    const paintedText = textColor ? composite(textColor, background) : null;
    const contrast = paintedText ? contrastRatio(paintedText, background) : null;
    const shadowColor = style.textShadow === 'none'
      ? null
      : parseColor(style.textShadow);
    const shadowContrast = shadowColor
      ? contrastRatio(composite(shadowColor, background), background)
      : 0;
    const strokeColor = parseColor(style.webkitTextStrokeColor);
    const strokeContrast = strokeColor
      ? contrastRatio(composite(strokeColor, background), background)
      : 0;
    const hasVisibleShadow = shadowContrast >= 1.15;
    const hasVisibleStroke =
      parseFloat(style.webkitTextStrokeWidth || '0') > 0 &&
      strokeContrast >= 1.15;
    if (contrast !== null &&
        contrast < 1.15 &&
        !hasVisibleShadow &&
        !hasVisibleStroke) {
      const key = selector(parent) + '|' + sample.slice(0, 36);
      if (!seenLowContrast.has(key)) {
        seenLowContrast.add(key);
        lowContrastChinese.push({
          selector: selector(parent),
          contrast: Math.round(contrast * 100) / 100,
          color: style.color,
          backgroundColor: 'rgb(' +
            background.slice(0, 3).map((value) => Math.round(value)).join(', ') +
            ')',
          text: sample.slice(0, 36)
        });
      }
    }
  }

  const report = {
    browserViewport: { width: window.innerWidth, height: window.innerHeight },
    stage: {
      clientWidth: stage.clientWidth,
      scrollWidth: stage.scrollWidth,
      horizontalOverflow: stage.scrollWidth > stage.clientWidth + 1
    },
    overflowElements: overflow.slice(0, 30),
    brokenImages: brokenImages,
    smallChinese: smallChinese.slice(0, 30),
    hiddenChinese: hiddenChinese.slice(0, 30),
    lowContrastChinese: lowContrastChinese.slice(0, 30),
    unparsedChineseColors: unparsedChineseColors.slice(0, 30)
  };
  const encoded = btoa(unescape(encodeURIComponent(JSON.stringify(report))));
  let marker = document.getElementById('wechat-qa-report');
  if (!marker) {
    marker = document.createElement('div');
    marker.id = 'wechat-qa-report';
    marker.style.display = 'none';
    document.body.appendChild(marker);
  }
  marker.setAttribute('data-report', encoded);
  };
  measure();
  window.addEventListener('load', measure, { once: true });
  setTimeout(measure, 4000);
})();
"""


def browser_candidates():
    names = [
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
        "chrome",
        "msedge",
        "brave-browser",
    ]
    for name in names:
        found = shutil.which(name)
        if found:
            yield Path(found)

    system = platform.system()
    if system == "Darwin":
        for candidate in (
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        ):
            yield Path(candidate)
    elif system == "Windows":
        roots = [
            os.environ.get("PROGRAMFILES"),
            os.environ.get("PROGRAMFILES(X86)"),
            os.environ.get("LOCALAPPDATA"),
        ]
        suffixes = (
            "Google/Chrome/Application/chrome.exe",
            "Chromium/Application/chrome.exe",
            "Microsoft/Edge/Application/msedge.exe",
            "BraveSoftware/Brave-Browser/Application/brave.exe",
        )
        for root in filter(None, roots):
            for suffix in suffixes:
                yield Path(root) / Path(suffix)


def find_browser(explicit=None):
    if explicit:
        path = Path(explicit).expanduser()
        return path if path.is_file() and os.access(path, os.X_OK) else None
    env_path = os.environ.get("CHROME_BIN")
    if env_path:
        path = Path(env_path).expanduser()
        if path.is_file() and os.access(path, os.X_OK):
            return path
    seen = set()
    for candidate in browser_candidates():
        resolved = str(candidate)
        if resolved in seen:
            continue
        seen.add(resolved)
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    return None


def build_qa_document(content, source_directory):
    base_href = source_directory.resolve().as_uri().rstrip("/") + "/"
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<base href="{html_mod.escape(base_href, quote=True)}">
<meta http-equiv="Content-Security-Policy"
      content="default-src 'none'; img-src https: data: file:; style-src 'unsafe-inline'; font-src https: data: file:; script-src 'nonce-wechatqa'">
<style>
html, body {{ margin: 0; padding: 0; width: {VIEWPORT_WIDTH}px; min-height: {VIEWPORT_HEIGHT}px; }}
body {{ background-color: #fefefe; font-family: -apple-system, 'PingFang SC', sans-serif; }}
#wechat-qa-stage {{ width: {VIEWPORT_WIDTH}px; min-height: 1px; margin: 0; padding: 0; }}
</style>
</head>
<body>
<main id="wechat-qa-stage">{content}</main>
<script nonce="wechatqa">{MEASURE_SCRIPT}</script>
</body>
</html>
"""


def parse_report(dumped_dom):
    match = re.search(
        r'id=["\']wechat-qa-report["\'][^>]*\bdata-report=["\']([^"\']+)["\']',
        dumped_dom,
        flags=re.I,
    )
    if not match:
        match = re.search(
            r'data-report=["\']([^"\']+)["\'][^>]*\bid=["\']wechat-qa-report["\']',
            dumped_dom,
            flags=re.I,
        )
    if not match:
        raise ValueError("浏览器没有返回 QA 度量报告")
    encoded = html_mod.unescape(match.group(1))
    return json.loads(base64.b64decode(encoded).decode("utf-8"))


def png_dimensions(path):
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("截图不是有效 PNG")
    return struct.unpack(">II", header[16:24])


def stop_browser_process_tree(process):
    """Stop Chrome and helpers so inherited output pipes cannot hang the caller."""

    if os.name == "nt":
        if process.poll() is not None:
            return
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            check=False,
        )
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path, help="待检查的完整预览 HTML")
    parser.add_argument("--screenshot", required=True, type=Path, help="390×844 PNG 输出路径")
    parser.add_argument("--json-report", type=Path, help="可选 JSON 报告路径")
    parser.add_argument("--chrome", help="Chrome/Chromium 可执行文件")
    parser.add_argument(
        "--timeout-ms",
        type=int,
        default=6000,
        help="浏览器虚拟时间预算，默认 6000",
    )
    parser.add_argument(
        "--fragment",
        action="store_true",
        help="把整个输入当作裸复制片段；完整预览页不要使用",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])
    if not args.html.is_file():
        print(f"✗ 文件不存在: {args.html}")
        return 2
    if args.timeout_ms < 1000:
        print("✗ --timeout-ms 不能小于 1000")
        return 2

    document = args.html.read_text(encoding="utf-8", errors="replace")
    try:
        content = get_copy_html(document, allow_fragment=args.fragment)
    except ValueError as error:
        print(f"✗ 复制边界错误: {error}")
        return 2

    browser = find_browser(args.chrome)
    if not browser:
        print("✗ 未找到 Chrome/Chromium；可用 --chrome 或 CHROME_BIN 指定")
        return 2

    output_paths = [args.screenshot]
    if args.json_report:
        output_paths.append(args.json_report)
    resolved_outputs = [path.resolve() for path in output_paths]
    if args.html.resolve() in resolved_outputs:
        print("✗ 渲染输出不能覆盖输入 HTML")
        return 2
    if len(set(resolved_outputs)) != len(resolved_outputs):
        print("✗ 截图与 JSON 报告不能写到同一路径")
        return 2
    for output_path in output_paths:
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            print(f"✗ 无法创建输出目录 {output_path.parent}: {error}")
            return 2
        if output_path.exists() and not (
            output_path.is_file() or output_path.is_symlink()
        ):
            print(f"✗ 输出路径不是文件: {output_path}")
            return 2
        try:
            output_path.unlink(missing_ok=True)
        except OSError as error:
            print(f"✗ 无法清理旧渲染产物 {output_path}: {error}")
            return 2

    with tempfile.TemporaryDirectory(prefix="wechat-mobile-qa-") as temp_dir:
        temp_root = Path(temp_dir)
        qa_html = temp_root / "render.html"
        qa_html.write_text(
            build_qa_document(content, args.html.parent),
            encoding="utf-8",
        )
        user_data = temp_root / "chrome-profile"
        command = [
            str(browser),
            "--headless",
            "--hide-scrollbars",
            "--force-device-scale-factor=1",
            f"--window-size={VIEWPORT_WIDTH},{VIEWPORT_HEIGHT}",
            f"--virtual-time-budget={args.timeout_ms}",
            "--run-all-compositor-stages-before-draw",
            "--allow-file-access-from-files",
            "--disable-background-networking",
            "--disable-component-update",
            "--disable-default-apps",
            "--disable-extensions",
            "--no-first-run",
            f"--user-data-dir={user_data}",
            f"--screenshot={args.screenshot.resolve()}",
            "--dump-dom",
            qa_html.resolve().as_uri(),
        ]
        timed_out_after_artifacts = False
        process = None
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=os.name != "nt",
            )
            try:
                stdout, stderr = process.communicate(
                    timeout=max(8, args.timeout_ms / 1000 + 4)
                )
                returncode = process.returncode
            except subprocess.TimeoutExpired:
                stop_browser_process_tree(process)
                try:
                    stdout, stderr = process.communicate(timeout=3)
                except subprocess.TimeoutExpired:
                    if os.name != "nt":
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                    else:
                        process.kill()
                    stdout, stderr = process.communicate()
                # 某些桌面 Chrome 在 --dump-dom + --screenshot 完成后仍等待后台
                # 子进程；脚本会终止整个进程组。只在两个产物都已完整生成
                # 时接受，避免把真正的渲染超时误判为成功。
                timed_out_after_artifacts = bool(
                    args.screenshot.is_file() and "wechat-qa-report" in stdout
                )
                returncode = 0 if timed_out_after_artifacts else 124
        except OSError as error:
            if process is not None:
                stop_browser_process_tree(process)
            print(f"✗ 无法启动 Chrome/Chromium：{error}")
            return 2

    if returncode != 0:
        detail = (stderr or stdout).strip().splitlines()
        print(f"✗ Chrome 渲染失败（退出码 {returncode}）")
        if detail:
            print(f"  {detail[-1][:240]}")
        return 2
    if not args.screenshot.is_file():
        print("✗ Chrome 未生成截图")
        return 2

    try:
        dimensions = png_dimensions(args.screenshot)
        report = parse_report(stdout)
    except (ValueError, json.JSONDecodeError, OSError) as error:
        print(f"✗ 渲染产物无效: {error}")
        return 2
    if dimensions != (VIEWPORT_WIDTH, VIEWPORT_HEIGHT):
        print(f"✗ 截图尺寸错误: {dimensions[0]}×{dimensions[1]}")
        return 2
    if report.get("stage", {}).get("clientWidth") != VIEWPORT_WIDTH:
        actual_width = report.get("stage", {}).get("clientWidth", "未知")
        print(
            f"✗ 内容舞台宽度错误: {actual_width}px，"
            f"预期 {VIEWPORT_WIDTH}px"
        )
        return 2

    report["source"] = str(args.html.resolve())
    report["screenshot"] = str(args.screenshot.resolve())
    report["capture"] = {
        "width": dimensions[0],
        "height": dimensions[1],
        "contentStageWidth": report["stage"]["clientWidth"],
    }
    if args.json_report:
        args.json_report.parent.mkdir(parents=True, exist_ok=True)
        args.json_report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    overflow = report["stage"]["horizontalOverflow"] or bool(
        report["overflowElements"]
    )
    broken = report["brokenImages"]
    small = report["smallChinese"]
    hidden = report.get("hiddenChinese", [])
    low_contrast = report.get("lowContrastChinese", [])
    unparsed_colors = report.get("unparsedChineseColors", [])
    failures = (
        int(bool(overflow))
        + int(bool(broken))
        + int(bool(small))
        + int(bool(hidden))
        + int(bool(low_contrast))
        + int(bool(unparsed_colors))
    )
    print(
        f"手机真实渲染：内容舞台 {report['stage']['clientWidth']}px，"
        f"截图 {dimensions[0]}×{dimensions[1]}；"
        f"浏览器内部视口 {report['browserViewport']['width']}×"
        f"{report['browserViewport']['height']}；"
        f"溢出 {len(report['overflowElements'])}；"
        f"破图 {len(broken)}；中文小字 {len(small)}；"
        f"隐藏中文 {len(hidden)}；近乎无对比中文 {len(low_contrast)}；"
        f"无法判定颜色 {len(unparsed_colors)}"
    )
    if timed_out_after_artifacts:
        print("说明：桌面 Chrome 产物完成后未自行退出，脚本已受控终止其主进程")
    print(f"截图：{args.screenshot.resolve()}")
    if overflow:
        for item in report["overflowElements"][:5]:
            print(
                f"  ✗ 横向溢出 {item['selector']} "
                f"（left {item['left']} / right {item['right']}）"
            )
    for src in broken[:5]:
        print(f"  ✗ 图片加载失败：{src}")
    for item in small[:5]:
        print(
            f"  ✗ 中文字号 {item['fontSize']}px：{item['text']} "
            f"（{item['selector']}）"
        )
    for item in hidden[:5]:
        print(
            f"  ✗ 中文内容不可见：{item['text']} "
            f"（{item['selector']}）"
        )
    for item in low_contrast[:5]:
        print(
            f"  ✗ 中文与背景近乎无对比（{item['contrast']}:1）："
            f"{item['text']}（{item['selector']}）"
        )
    for item in unparsed_colors[:5]:
        print(
            f"  ✗ 无法判定中文文字颜色 {item['color']}："
            f"{item['text']}（{item['selector']}）"
        )
    if failures:
        print(f"\n✗ 手机真实渲染未通过 {failures} 类问题")
        return 1
    print("✓ 手机真实渲染通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
