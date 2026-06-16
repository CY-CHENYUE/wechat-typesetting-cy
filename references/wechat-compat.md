# 微信公众号编辑器兼容性硬约束

这份文件是全技能的安全底线：**无论选了什么风格，生成的 HTML 都必须逐条满足这里的规则。**
规则大多来自真实踩坑——违反的后果是"浏览器预览正常、粘贴进编辑器后崩坏"，而且往往只在部分手机端暴露。

## 粘贴机制（理解这些规则为什么存在）

公众号官方编辑器没有"源代码模式"。内容进入编辑器的方式是**富文本粘贴**：
浏览器把选区/剪贴板里的 HTML 交给编辑器 → 编辑器按白名单过滤。

过滤会做这些事：剥掉 class / id、剥掉 `<style>` 和 `<script>`、丢弃白名单外的 CSS 属性、改写部分标签。
所以：**样式必须全部内联，且只能用白名单内的 CSS。** 任何依赖选择器、脚本、外部资源的效果都会丢失。

## 硬规则（必须遵守）

### 结构

1. 所有样式写在元素的 `style=""` 里，不用 `<style>` 块、不引外部 CSS
2. 不依赖 class / id 呈现样式（粘贴后会被剥掉）
3. 不用 `<script>`、不用任何事件属性
4. 块结构用 `<section>` 和 `<p>`，行内用 `<span>` / `<strong>`
5. 标题不用 `<h1>`-`<h6>`（编辑器对 h 标签有默认样式与行为，容易干扰），用 `section`/`p` + 内联样式实现标题
6. 列表不用 `<ul>`/`<ol>`/`<li>`（部分手机端 li 的内联样式会丢失），用 `p` + 序号 `span` 实现，见组件库
7. 代码不用裸 `<pre>`/`<code>`，用 `section` + `white-space: pre-wrap` + 等宽字体

### CSS 禁用项

8. `display: flex` / `display: grid` / `gap` —— 部分手机端粘贴后整段塌掉。**多列布局一律用嵌套 `<table>`**
9. `position` / `float` / `transform` / `animation` / `transition` / `z-index` —— position 全部失效会被删，float 使元素脱离文档流产生怪异显示，transform 端差异大
10. `linear-gradient` 等所有渐变、`background-image` —— 不渲染，用实色替代
11. **背景色不用 `rgba()`** —— 微信不渲染 rgba 背景，把半透明效果换算成实色 hex（文字颜色用 rgba 是安全的）
12. 不用负 margin；不用百分比 `height` / 百分比 `margin` / 百分比定位（依赖父级确定高度，微信容器高度不定 → 失效）。**百分比 `width` 是安全的**——块级元素、`<img>`、table 列宽用 % 正常生效
13. `@media` 媒体查询、`@keyframes` CSS 动画 —— 无效；不存在响应式与动画能力，动效只能靠 GIF 图

### 结构补充（公开资料交叉验证）

14. **所有元素的 id 会被删除** —— 锚点跳转必然失效，不要做"点目录跳转"类设计；class 会保留但没有外部 CSS 可引用，等于无效

### 颜色与背景

15. 纯白背景写 `#fefefe`，不写 `#ffffff`（会被过滤掉）
16. 整页有底色（深色页面，或米白等非白底）→ 用 `<table>` 做主骨架，见下节
17. **背景一律用 `background-color`，不用 `background` 简写**——简写可能触发编辑器对渐变的清洗，把整条声明（连同纯色）一起删掉，背景变白
18. 正文主文字色优先用**实色 hex**：rgba 文字色虽安全，但 Android 老内核偶发忽略 alpha 当不透明渲染，大面积正文会偏色。把 `rgba(232,228,220,0.82)` 在底色上预乘成实色 hex 给正文用；rgba 文字色留给装饰性文字（大引号、弱化副句）

### 整页底色的 table 骨架（深色页面必须，非白浅底建议）

兄弟 `<section>` 之间在编辑器里会出现不可控间隙，整页有底色时间隙会露出白缝。解法：

19. 外层结构固定为：
    ```html
    <section data-role="outer" style="background-color: {底色}; padding: 0;">
    <table width="100%" cellspacing="0" cellpadding="0" border="0"
           style="border-collapse: collapse; border-spacing: 0; background-color: {底色}; border: none;">
      <tr><td style="background-color: {底色}; padding: ...; border: none;"> 章节内容 </td></tr>
      ...
    </table>
    </section>
    ```
20. 每个章节占一个 `<tr><td>`；**所有 `<td>` 显式写 `border: none`**（否则出现白色细线）
21. 章节分隔带做成独立的 `<tr><td>`，并加 `font-size: 0; line-height: 0;` 防止被空行撑高
22. `<section>` 不做兄弟布局；放在 `<td>` 内部做卡片容器是安全的

纯白底页面可以直接用顺序 `<section>` 流，不强制 table 骨架。

### 间距与宽度

23. `padding` 比 `margin` 可靠：外层间距用 padding；段落间距用 `p` 的 `margin-bottom`（实测稳定）
24. 块级元素不设固定 px 宽度（手机端会溢出），用 `width: 100%` + padding 控制；table 列宽用百分比

### 图片与视频（媒体）

25. 有 **https** 外链的图片 → 直接生成 `<img>`，粘贴时编辑器自动转存到素材库；http 图大概率转存失败，按"无地址图"处理
26. `<img>` 统一写 `style="width: 100%; height: auto; display: block;"`，按设计可加圆角；下方配图注
27. **本地图片、或只标了位置没给地址的图**（如 `![成品](./img/1.jpg)`、【图：成品特写】）→ 生成**图片占位块**：用**单个 `<p>`** 做成的可视虚线框（编号 + 建议内容，样式见 components.md）。单段落是为了删除方便——编辑器里三击全选就能删；HTML 注释粘贴后会消失，占位必须用可视元素；不要做成容器套多段落
28. **视频不可能随粘贴带入**：`<video>` / `<iframe>` / `<audio>` / `<svg>` / `<canvas>` / `<form>` / `<input>` 都会被编辑器整体剥掉，禁止生成。视频位置一律生成**视频占位块**，提示用户粘贴后用编辑器工具栏「视频」按钮插入（视频号 / 腾讯视频 / 上传素材库）。图标只能用 emoji / Unicode 几何字符 / 转存为位图 `<img>`，**不能用内联 SVG**
29. 占位块统一编号（图 1、图 2、视频 1……），**交付时给出占位清单**；用户替换完媒体后删除占位块
30. 原文没有任何媒体标记时，不生成可视占位（避免污染正文）；配图建议写进交付说明即可
31. 交付时提醒用户：粘贴后检查外链图是否全部转存成功，裂图需手动上传替换

### 链接

32. 未认证公众号文内外链不可点击。**外链一律转成文末"参考资料"纯文本列表**，正文中用上标 `[1]` 标注；公众号文章链接（mp.weixin.qq.com）可以保留为可点链接

## 放心使用（三端确信安全的白名单）

`border`（含 `dashed` / `dotted` / `double` 线型）/ `border-radius` / `box-shadow`（单层、模糊半径 ≤24px、rgba 黑低透明；阴影色用 rgba 安全）/ `text-shadow`（模糊 ≤12px，深底标题做微光、浅底做描边）/ `letter-spacing`（正值随意）/ `line-height` / `text-align`（含 justify）/ `text-decoration` 与 `text-decoration-color`（彩色下划线）/ `vertical-align`（table 对齐核心）/ `text-transform: uppercase`（英文标签免手敲大写）/ 文字颜色 rgba / `width` 百分比 / `&nbsp;` `&middot;` 等 HTML 实体 / 纯彩色 emoji

## 渐进增强（iOS 出效果 / Android 兜底，用了不崩但效果不保证）

- **`text-underline-offset`**：iOS 15+ 支持（下划线悬浮），Android 多机型忽略 → 退化成贴底下划线，不影响可读
- **`-webkit-text-stroke`（空心描边字）**：iOS 确信、Android 老内核忽略 → **必须同时写 `color` 兜底**，不支持时降级为实心字而非空白；超大 hero 数字/标题用
- **字体栈**（Baskerville / Optima / Avenir 等）：见 design-craft.md，iOS 出彩 Android 回退系统字
- 用到这类手法**必须提醒用户手机预览验证**

## 谨慎使用

- **字号 < 12px**：仅用于英文装饰性标签（9-11px 实测可用），中文正文、说明、图注不低于 12px
- **负 `letter-spacing`**：限 -0.5px 以内、仅无衬线大标题；再大 iOS 可能裁切行末字符
- **竖排文字 `writing-mode: vertical-rl`**：国风/文艺标题区可用，但 Android 部分机型表现不一——用了必须手机预览验证
- **百分比宽度色块（进度条类）**：部分端不可靠；比例可视化优先用等宽字符条（▓░ / ●○，见 design-craft.md"字符数据条"）

## 常见但不靠谱（教程里常见，微信实测会坑，别用）

- **`overflow: hidden` 裁 table/td 圆角**：iOS 不裁切，直角戳出圆角——圆角 + overflow 要放在**外层 `<section>`** 上，table 本身不靠它
- **`linear-gradient` / `background-image` / `border-image`**：三端都不渲染、白名单清洗，花式渐变边框必坑——渐变感用多段实色拼接（见 design-craft.md）
- **内联 `<svg>` 做图标/分隔线**：整体被剥离，进不去编辑器（见规则 26）
- **`::first-letter` 等伪元素**：依赖选择器，粘贴全滤——首字放大只能用行内 `<span>`
- **带变体选择符的符号（⚠︎ ▶︎，U+FE0E）**：Android 可能变豆腐方框——装饰符号优先用纯几何字符 ▲ ● ◆ ■ ▢

## 生成后自检清单（逐条过，违规必须修复后再交付）

- [ ] 全部样式内联，无 `<style>` / `<script>` / 事件属性
- [ ] 无 flex / grid / position / float / transform / 渐变
- [ ] 背景用 `background-color`（非 `background` 简写）、无 rgba、无 `#ffffff`（纯白用 `#fefefe`）
- [ ] 无内联 `<svg>` / `<canvas>` / `<form>`；圆角裁切放在外层 section 不放 table
- [ ] 整页深色 → table 骨架；所有 td 有 `border: none`；分隔行有 `font-size: 0; line-height: 0;`
- [ ] 列表用 p + 序号 span，无裸 ul / ol / li
- [ ] 无 `<h1>`-`<h6>`、无裸 `<pre>` / `<code>`
- [ ] 无 `<video>` / `<iframe>` / `<audio>`（视频用占位块）
- [ ] 块元素无固定 px 宽度
- [ ] 图片 https + `width: 100%`；本地图/视频已转可视占位块并编号
- [ ] 外链已转文末参考资料
- [ ] 中文文字字号 ≥ 12px

## 交付时提醒用户做的检查

33. 粘贴进编辑器后对照预览页扫一遍：背景色、卡片边框、间距是否还原
34. 用编辑器"预览"发到手机看一遍：深色背景是否完整、小字是否可读
35. 检查图片是否全部转存成功（裂图 → 手动上传素材库）
