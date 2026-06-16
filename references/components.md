# 微信安全实现手法库

这里的价值是 **DOM 结构**：每种手法都按 `wechat-compat.md` 硬规则验证过（全内联、无 flex、无渐变、列表用 p+span、多列用 table）。

使用方法：**保留结构，样式自己设计**——把 `{{token}}` 占位符和示例里的具体数值（颜色、圆角、边框、间距、装饰符号）全部换成本篇设计方案定下的值；示例值只是演示，不是默认值。设计方案需要库里没有的形态时可以自创结构，守住 compat 硬规则即可。

**占位符约定**：`{{主色}}` `{{正文色}}` `{{标题色}}` `{{辅助灰}}` `{{浅底}}` `{{边色}}` `{{字体}}` `{{页底色}}`（取值全部来自本篇设计方案）

## 目录

- [0. 页面骨架](#0-页面骨架)
- [1. 头部标题区](#1-头部标题区)（3 变体）
- [2. 章节标题](#2-章节标题)（4 变体）
- [3. 正文段落与行内强调](#3-正文段落与行内强调)
- [4. 金句卡](#4-金句卡)（3 变体）
- [5. 数据栏](#5-数据栏)
- [6. 清单 / 要点](#6-清单--要点)
- [7. 步骤块](#7-步骤块)
- [8. 时间线](#8-时间线)
- [9. 引用 / 出处卡](#9-引用--出处卡)
- [10. 对比表](#10-对比表)
- [11. 代码块](#11-代码块)
- [12. 图片与图注](#12-图片与图注)
- [13. 分隔](#13-分隔)
- [14. 文末区](#14-文末区)
- [15. 参考资料（外链处理）](#15-参考资料外链处理)
- [16. 文末关注 / 作者卡](#16-文末关注--作者卡)

---

## 0. 页面骨架

**白底页面**（蓝调杂志 / 极简黑白 / 清新治愈 / 商务蓝灰 / 活力橙黄 / 学术线框）——顺序 section 流：

```html
<section style="background-color: #fefefe; padding: 0 0 40px 0;">
  <!-- 依次放各组件，正文区统一左右 padding 24px -->
</section>
```

**整页有底色**（暗夜科技的深底、暖纸阅读的米白底）——table 骨架，规则见 wechat-compat.md 第 19-22 条：

```html
<section data-role="outer" style="background-color: {{页底色}}; padding: 0;">
<table width="100%" cellspacing="0" cellpadding="0" border="0"
       style="border-collapse: collapse; border-spacing: 0; background-color: {{页底色}}; border: none;">
  <tr><td style="background-color: {{页底色}}; padding: 24px; border: none;">
    <!-- 一个章节的全部内容（内部可以放 section 卡片，安全） -->
  </td></tr>
  <!-- 章节分隔带 -->
  <tr><td style="background-color: {{分隔带色}}; height: 16px; font-size: 0; line-height: 0; border: none;">&nbsp;</td></tr>
</table>
</section>
```

## 1. 头部标题区

**变体 A · 杂志式**（蓝调杂志/商务蓝灰）——色底横幅 + 标签 + 大标题 + 副题：

```html
<section style="background-color: {{主色}}; padding: 14px 24px;">
  <table width="100%" cellspacing="0" cellpadding="0" border="0" style="border-collapse: collapse; border: none;">
    <tr>
      <td style="border: none; text-align: left;"><span style="color: #fefefe; font-size: 15px; font-weight: 700; font-family: {{字体}}; letter-spacing: 1px;">2026</span></td>
      <td style="border: none; text-align: right;"><span style="color: #fefefe; font-size: 11px; letter-spacing: 3px; font-family: {{字体}};">ENGLISH TAG</span></td>
    </tr>
  </table>
</section>
<section style="padding: 28px 24px 8px;">
  <p style="margin: 0 0 12px 0;"><span style="font-size: 14px; color: {{主色}}; font-weight: 600; letter-spacing: 2px; font-family: {{字体}};">栏目标签</span></p>
  <p style="margin: 0 0 12px 0;"><span style="font-size: 30px; font-weight: 900; color: {{标题色}}; letter-spacing: -0.5px; line-height: 1.25; font-family: {{字体}};">文章主标题<br>可以换行</span></p>
  <p style="margin: 0;"><span style="font-size: 14px; color: {{辅助灰}};">一句话副标题或核心摘要</span></p>
</section>
```

**变体 B · 居中式**（清新治愈/活力橙黄/暖纸阅读）：

```html
<section style="padding: 36px 24px 8px; text-align: center;">
  <p style="margin: 0 0 14px 0;"><span style="font-size: 12px; color: {{主色}}; letter-spacing: 4px;">栏 目 标 签</span></p>
  <p style="margin: 0 0 12px 0;"><span style="font-size: 27px; font-weight: 800; color: {{标题色}}; line-height: 1.35; font-family: {{字体}};">文章主标题</span></p>
  <p style="margin: 0 0 18px 0;"><span style="font-size: 14px; color: {{辅助灰}};">一句话副标题</span></p>
  <section style="width: 36px; height: 3px; background-color: {{主色}}; margin: 0 auto;"></section>
</section>
```

**变体 C · 极简式**（极简黑白/严肃长文）——只有标题与日期，靠留白：

```html
<section style="padding: 44px 24px 8px;">
  <p style="margin: 0 0 16px 0;"><span style="font-size: 26px; font-weight: 800; color: {{标题色}}; line-height: 1.4; font-family: {{字体}};">文章主标题</span></p>
  <p style="margin: 0; border-top: 1px solid {{边色}}; padding-top: 12px;"><span style="font-size: 13px; color: {{辅助灰}};">作者 · 2026.06</span></p>
</section>
```

## 2. 章节标题

**变体 A · 水印编号**（蓝调杂志）：

```html
<section style="padding: 40px 24px 0;">
  <p style="margin: 0; line-height: 1;"><span style="font-size: 56px; font-weight: 900; color: {{水印色}}; font-family: {{字体}};">01</span></p>
  <p style="margin: 0 0 20px 0;"><span style="font-size: 22px; font-weight: 800; color: {{标题色}}; line-height: 1.4; font-family: {{字体}};">章节标题</span></p>
</section>
```

**变体 B · 序号色块**（清新治愈/活力橙黄/学术线框）：

```html
<section style="padding: 36px 24px 16px;">
  <p style="margin: 0;">
    <span style="display: inline-block; background-color: {{主色}}; color: #fefefe; font-size: 13px; font-weight: 700; padding: 3px 10px; border-radius: 4px; margin-right: 10px;">01</span>
    <span style="font-size: 18px; font-weight: 800; color: {{标题色}};">章节标题</span>
  </p>
</section>
```

**变体 C · 左色条**（商务蓝灰/引用感强的方向）：

```html
<section style="padding: 36px 24px 16px;">
  <section style="border-left: 4px solid {{主色}}; padding-left: 12px;">
    <p style="margin: 0;"><span style="font-size: 18px; font-weight: 800; color: {{标题色}};">章节标题</span></p>
  </section>
</section>
```

**变体 D · 居中细线**（极简黑白/暖纸阅读）：

```html
<section style="padding: 40px 24px 16px; text-align: center;">
  <p style="margin: 0 0 8px 0;"><span style="font-size: 12px; color: {{辅助灰}}; letter-spacing: 3px;">— 01 —</span></p>
  <p style="margin: 0;"><span style="font-size: 18px; font-weight: 700; color: {{标题色}}; font-family: {{字体}};">章节标题</span></p>
</section>
```

深色页面的章节头（暗夜科技）：空格字距标签 + 双色标题，写在 td 内：

```html
<p style="margin: 0 0 10px 0;"><span style="font-size: 10px; color: {{主色}}; letter-spacing: 4px;">核 心 定 义</span></p>
<p style="margin: 0 0 16px 0;"><span style="font-size: 24px; font-weight: 900; color: {{标题色}};">章节标题的<span style="color: {{主色}};">强调部分</span></span></p>
```

## 3. 正文段落与行内强调

标准段落（所有方向通用，替换字号/行距/颜色 token）：

```html
<section style="padding: 0 24px;">
  <p style="margin: 0 0 16px 0; text-align: justify; line-height: 1.75; font-size: 15px; color: {{正文色}}; letter-spacing: 0.5px; font-family: {{字体}};">
    正文内容。每段 3-4 行一个意思，关键句可以独立成段。
  </p>
</section>
```

行内强调（一篇文章选 1-2 种，不混用太多）：

```html
<strong style="color: {{主色}};">彩色加粗</strong>
<strong style="color: {{正文色}};">普通加粗</strong>
<span style="text-decoration: underline; text-decoration-color: {{主色}}; text-underline-offset: 4px;">色彩下划线</span>
<span style="background-color: {{高亮底}}; padding: 0 2px;">荧光笔（活力橙黄）</span>
```

## 4. 金句卡

**变体 A · 色底**（蓝调杂志/暗夜科技）：

```html
<section style="margin: 28px 24px; background-color: {{主色}}; padding: 24px 20px; text-align: center;">
  <p style="margin: 0 0 8px 0;"><span style="font-size: 17px; font-weight: 700; color: #fefefe; line-height: 1.6; font-family: {{字体}};">金句主句</span></p>
  <p style="margin: 0;"><span style="font-size: 13px; color: rgba(254,254,254,0.75);">补充副句</span></p>
</section>
```

**变体 B · 边框**（商务蓝灰/学术线框/暖纸阅读）：

```html
<section style="margin: 28px 24px; border: 1px solid {{边色}}; border-left: 4px solid {{主色}}; background-color: {{浅底}}; padding: 18px 20px;">
  <p style="margin: 0;"><span style="font-size: 15px; font-weight: 600; color: {{标题色}}; line-height: 1.7;">结论或金句内容</span></p>
</section>
```

**变体 C · 留白居中**（极简黑白）——无底色，靠留白与字重：

```html
<section style="margin: 36px 24px; text-align: center;">
  <p style="margin: 0;"><span style="font-size: 16px; font-weight: 700; color: {{标题色}}; line-height: 1.8;">金句内容</span></p>
</section>
```

## 5. 数据栏

三列数据（嵌套 table，**不用 flex**）；两列就删一个 td 并调宽度。
注意两件兼容事：① **圆角 + `overflow:hidden` 必须放在外层 `<section>` 上**（放在 table 上 iOS 不裁切，td 直角会戳出圆角）；② table 加 `table-layout: fixed`，否则某列文字一长就把 `width:33%` 顶破、三列不等宽；td 内补 `word-break` 防长串英文/数字撑破列。

```html
<section style="margin: 24px 24px; border: 1px solid {{边色}}; border-radius: 12px; overflow: hidden;">
  <table width="100%" cellspacing="0" cellpadding="0" border="0"
         style="border-collapse: collapse; table-layout: fixed; border: none;">
    <tr>
      <td width="33%" style="background-color: {{浅底}}; padding: 18px 10px; text-align: center; word-break: break-all; border: none; border-right: 1px solid {{边色}};">
        <p style="margin: 0 0 4px 0;"><span style="font-size: 26px; font-weight: 900; color: {{主色}};">87%</span></p>
        <p style="margin: 0;"><span style="font-size: 12px; color: {{辅助灰}};">指标名称</span></p>
      </td>
      <td width="33%" style="background-color: {{浅底}}; padding: 18px 10px; text-align: center; word-break: break-all; border: none; border-right: 1px solid {{边色}};">
        <p style="margin: 0 0 4px 0;"><span style="font-size: 26px; font-weight: 900; color: {{主色}};">3.2亿</span></p>
        <p style="margin: 0;"><span style="font-size: 12px; color: {{辅助灰}};">指标名称</span></p>
      </td>
      <td width="34%" style="background-color: {{浅底}}; padding: 18px 10px; text-align: center; word-break: break-all; border: none;">
        <p style="margin: 0 0 4px 0;"><span style="font-size: 26px; font-weight: 900; color: {{主色}};">No.1</span></p>
        <p style="margin: 0;"><span style="font-size: 12px; color: {{辅助灰}};">指标名称</span></p>
      </td>
    </tr>
  </table>
</section>
```

## 6. 清单 / 要点

**不用 ul/li**，p + 序号 span。普通版：

```html
<section style="padding: 0 24px; margin-bottom: 16px;">
  <p style="margin: 0 0 10px 0; line-height: 1.7; font-size: 15px; color: {{正文色}};">
    <span style="color: {{主色}}; font-weight: 700; margin-right: 8px;">1.</span>要点内容写在这里
  </p>
  <p style="margin: 0 0 10px 0; line-height: 1.7; font-size: 15px; color: {{正文色}};">
    <span style="color: {{主色}}; font-weight: 700; margin-right: 8px;">2.</span>要点内容写在这里
  </p>
</section>
```

圆底序号版（清新治愈/活力橙黄）：

```html
<p style="margin: 0 0 12px 0; line-height: 1.7; font-size: 15px; color: {{正文色}};">
  <span style="display: inline-block; width: 20px; height: 20px; line-height: 20px; text-align: center; background-color: {{主色}}; color: #fefefe; border-radius: 50%; font-size: 12px; font-weight: 700; margin-right: 8px;">1</span>要点内容
</p>
```

清单卡（整组要点放进浅底卡，适合"食材/工具/前提条件"）：

```html
<section style="margin: 20px 24px; background-color: {{浅底}}; border: 1px solid {{边色}}; border-radius: 10px; padding: 16px 18px;">
  <p style="margin: 0 0 10px 0;"><span style="font-size: 13px; font-weight: 700; color: {{主色}}; letter-spacing: 1px;">你需要准备</span></p>
  <!-- 此处放上面的 p+序号 行 -->
</section>
```

## 7. 步骤块

```html
<section style="margin: 24px 24px 0;">
  <p style="margin: 0 0 6px 0;">
    <span style="display: inline-block; background-color: {{主色}}; color: #fefefe; font-size: 11px; font-weight: 700; letter-spacing: 2px; padding: 3px 8px; border-radius: 3px;">STEP 01</span>
  </p>
  <p style="margin: 0 0 8px 0;"><span style="font-size: 16px; font-weight: 700; color: {{标题色}};">步骤标题</span></p>
  <p style="margin: 0 0 8px 0; line-height: 1.75; font-size: 15px; color: {{正文色}}; text-align: justify;">步骤说明文字。</p>
  <p style="margin: 0;"><span style="font-size: 13px; color: {{辅助灰}};">⚠︎ 这一步的注意事项（可选）</span></p>
</section>
```

## 8. 时间线

table 实现左点右文（深浅色页面通用，换色即可）：

```html
<section style="margin: 20px 24px;">
  <table width="100%" cellspacing="0" cellpadding="0" border="0" style="border-collapse: collapse; border: none;">
    <tr>
      <td width="20" valign="top" style="border: none; padding: 2px 10px 0 0;">
        <span style="display: inline-block; width: 10px; height: 10px; border-radius: 50%; background-color: {{主色}};"></span>
      </td>
      <td style="border: none; border-left: 1px solid {{边色}}; padding: 0 0 20px 14px;">
        <p style="margin: 0 0 4px 0;"><span style="font-size: 12px; color: {{辅助灰}}; letter-spacing: 1px;">2026.03</span></p>
        <p style="margin: 0 0 4px 0;"><span style="font-size: 15px; font-weight: 700; color: {{标题色}};">事件标题</span></p>
        <p style="margin: 0; font-size: 14px; line-height: 1.7; color: {{正文色}};">事件说明。</p>
      </td>
    </tr>
    <!-- 更多事件复制 <tr> ；正面/危机事件换圆点颜色（语义色） -->
  </table>
</section>
```

## 9. 引用 / 出处卡

```html
<section style="margin: 24px 24px; border-left: 4px solid {{主色}}; background-color: {{浅底}}; padding: 14px 16px;">
  <p style="margin: 0 0 8px 0; font-size: 14px; line-height: 1.75; color: {{正文色}};">"引用的原话内容。"</p>
  <p style="margin: 0;"><span style="font-size: 12px; color: {{辅助灰}};">—— 来源人物 · 身份/场合</span></p>
</section>
```

## 10. 对比表

第一行做表头（td 加粗加底色，**不用 th**）。多列等宽稳定要靠 `table-layout: fixed`（给每个 td 配 `width`），td 内补 `word-break: break-all` 防长内容撑破列：

```html
<section style="margin: 24px 24px;">
  <table width="100%" cellspacing="0" cellpadding="0" border="0" style="border-collapse: collapse; table-layout: fixed; word-break: break-all; border: 1px solid {{边色}}; font-size: 13px;">
    <tr>
      <td style="background-color: {{浅底}}; padding: 10px 12px; border: 1px solid {{边色}}; font-weight: 700; color: {{标题色}};">维度</td>
      <td style="background-color: {{浅底}}; padding: 10px 12px; border: 1px solid {{边色}}; font-weight: 700; color: {{标题色}};">方案 A</td>
      <td style="background-color: {{浅底}}; padding: 10px 12px; border: 1px solid {{边色}}; font-weight: 700; color: {{标题色}};">方案 B</td>
    </tr>
    <tr>
      <td style="padding: 10px 12px; border: 1px solid {{边色}}; color: {{辅助灰}};">价格</td>
      <td style="padding: 10px 12px; border: 1px solid {{边色}}; color: {{正文色}};">内容</td>
      <td style="padding: 10px 12px; border: 1px solid {{边色}}; color: {{正文色}};">内容</td>
    </tr>
  </table>
</section>
```

## 11. 代码块

不用 `<pre>`，section + pre-wrap；行数多时控制在关键片段：

```html
<section style="margin: 20px 24px; background-color: #1F2329; border-radius: 8px; padding: 14px 16px;">
  <p style="margin: 0; font-family: Menlo, Consolas, monospace; font-size: 12px; line-height: 1.8; color: #E6E6E6; white-space: pre-wrap; word-break: break-all;">const answer = 42;
console.log(answer);</p>
</section>
```

## 12. 图片 / 视频与占位块

**真图**（https 外链，粘贴时编辑器自动转存）：

```html
<section style="margin: 24px 24px;">
  <img src="https://example.com/image.jpg" style="width: 100%; height: auto; display: block; border-radius: 8px;">
  <p style="margin: 8px 0 0 0; text-align: center;"><span style="font-size: 12px; color: {{辅助灰}};">▲ 图注说明文字</span></p>
</section>
```

**图片占位块**（本地图 / 只标位置没给地址的图；HTML 注释粘贴后会消失，必须用可视元素）：

```html
<p style="margin: 24px 24px; border: 1px dashed {{边色}}; border-radius: 8px; background-color: {{浅底}}; padding: 26px 14px; text-align: center; font-size: 13px; line-height: 1.7; color: {{辅助灰}};"><strong style="color: {{主色}};">▢ 图 1</strong>&nbsp;&nbsp;店门口的木质招牌，下午的光</p>
```

**视频占位块**（视频无法随粘贴带入，必须在编辑器内用「视频」按钮插入——这句关键提示集中放在占位清单和交付说明里，块内只留一句短的）：

```html
<p style="margin: 24px 24px; border: 1px dashed {{边色}}; border-radius: 8px; background-color: {{浅底}}; padding: 34px 14px; text-align: center; font-size: 13px; line-height: 1.7; color: {{辅助灰}};"><strong style="color: {{主色}};">▶ 视频 1</strong>&nbsp;&nbsp;手冲注水的 30 秒（编辑器工具栏「视频」插入）</p>
```

**占位块为什么必须是单个 `<p>`（删除体验）**：粘贴进编辑器后，删除动作 = **三击占位行（整段全选）→ Delete**，若留下空框再按一次退格——两步删完。做成"容器套多个段落"的话，用户要跨段拖选、容易剩半个空壳。同理块内不堆操作说明（保持单行），说明集中进文末占位清单。

**占位清单**（放正文末尾，同样单段落好删；带删除方法提示）：

```html
<p style="margin: 30px 24px 0; border-top: 1px solid {{边色}}; padding: 12px 0 24px; font-size: 12px; line-height: 1.9; color: {{辅助灰}};"><strong>媒体占位清单</strong>　图 1 店门口木招牌 ／ 视频 1 注水 30 秒（视频粘贴带不进，必须用工具栏「视频」插入）<br>替换方法：三击占位行全选 → 删除（留空框再按一次退格）→ 原位插入媒体 ｜ 全部替换后把本行也删掉</p>
```

占位块外观跟随本篇设计（虚线框 + 浅底是默认形态，颜色全用设计 token）；全文占位统一编号。

## 13. 分隔

```html
<!-- 细线（极简/商务） -->
<section style="border-top: 1px solid {{边色}}; margin: 32px 24px;"></section>

<!-- 色块短线（杂志） -->
<section style="width: 100%; height: 4px; background-color: {{主色}}; margin: 28px 0;"></section>

<!-- 居中点（极简/暖纸） -->
<section style="margin: 32px 0; text-align: center;"><span style="color: {{辅助灰}}; font-size: 14px; letter-spacing: 8px;">· · ·</span></section>
```

深色页分隔带用骨架里的 `<tr><td>` 形式（见 0 节）。

## 14. 文末区

END 标记 + 互动引导（按方向调整语气）：

```html
<section style="margin: 40px 24px 0; text-align: center;">
  <p style="margin: 0 0 24px 0;"><span style="font-size: 12px; color: {{辅助灰}}; letter-spacing: 6px;">— END —</span></p>
  <p style="margin: 0; font-size: 14px; color: {{正文色}}; line-height: 1.8;">你怎么看？评论区聊聊 👇</p>
</section>
```

递进式结尾（暗夜科技专属）：连续几行文字颜色透明度递增，最后一句用主色。

## 15. 参考资料（外链处理）

外链不可点（未认证号），统一收到文末；正文中对应位置加上标 `<span style="font-size: 11px; color: {{主色}};">[1]</span>`：

```html
<section style="margin: 28px 24px 0; border-top: 1px solid {{边色}}; padding-top: 14px;">
  <p style="margin: 0 0 8px 0;"><span style="font-size: 13px; font-weight: 700; color: {{辅助灰}};">参考资料</span></p>
  <p style="margin: 0 0 6px 0; font-size: 12px; line-height: 1.7; color: {{辅助灰}}; word-break: break-all;">[1] 文章标题 — example.com/path</p>
</section>
```


## 16. 文末关注 / 作者卡

公众号文末刚需组件。账号信息（名称 / 简介 / 引导语 / 往期标题）一律用【占位文字】并加注释让用户替换，**不可代写**：

```html
<section style="margin: 32px 24px 0; border-top: 1px solid {{边色}}; padding-top: 22px; text-align: center;">
  <!-- 以下账号信息为占位，发布前替换 -->
  <p style="margin: 0 0 6px 0;"><span style="font-size: 14px; font-weight: 700; color: {{标题色}}; letter-spacing: 1px;">【公众号名称】</span></p>
  <p style="margin: 0 0 14px 0;"><span style="font-size: 12px; color: {{辅助灰}};">【一句话账号简介】</span></p>
  <p style="margin: 0;"><span style="font-size: 12px; color: {{主色}};">【关注引导语，按文章气质改写】</span></p>
</section>
```

往期推荐列表同理（标题用占位；只有公众号文章链接 mp.weixin.qq.com 可保留为可点链接）。样式形态跟随本篇设计方案。

---

## 组装节奏（重要）

组件是调味料，正文才是主菜。组装时遵守：

- 每个章节 = 章节标题 + 若干正文段（主体）+ **至多 1-2 个组件**
- 两个卡片组件不要紧挨着连发，中间隔正文段
- 全文组件种类 ≤ 5 种（不含正文/标题/分隔），重复使用同种组件保持版面统一
- 数据、金句、引用——只有内容里真有这些素材时才用对应组件，**不要为了好看编造**
