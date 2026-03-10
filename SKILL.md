---
name: wechat-typesetting-cy
description: 微信公众号文章多模板排版技能。将纯文本或Markdown转换为精美排版的HTML代码，支持多种视觉风格模板。当用户提到"微信文章"、"公众号文章"、"发公众号"、"帮我排版"、"公众号排版"、"排版成微信格式"、"蓝色模板"、"暗黑模板"、"科技风排版"时触发。
---

# 微信公众号排版

多模板排版系统，根据文章内容自动选择最合适的视觉风格。

## 模板选择

### 可用模板

| 模板 | 视觉风格 | 适合内容 | 关键词 |
|------|----------|----------|--------|
| `blue-minimal` | 白底蓝色，衬线字体，杂志感 | 深度分析、思考、随笔、观点文 | 论述、故事、分析、思考 |
| `dark-tech` | 黑底橙红，无衬线，卡片化 | 产品介绍、科技报道、数据驱动 | 产品、数据、时间线、竞品 |

### 自动选择逻辑

按以下优先级判断，第一条匹配即选定：

1. **用户指定** → 使用用户指定的模板
2. **有数据、时间线、产品特性、竞品分析、排名** → `dark-tech`
3. **论述、观点、分析、故事、随笔、思考** → `blue-minimal`
4. **不确定** → 问用户："这篇文章更偏向深度分析/思考（蓝色杂志风），还是产品/科技/数据报道（暗黑科技风）？"

## 工作流程

**判断任务类型：**

1. **生成HTML** → 用户给原文，需要输出排版后的HTML代码
2. **检查排版** → 用户给已有HTML，需要检查并给出改进建议

## 生成HTML流程

### Step 1: 选模板

根据"自动选择逻辑"确定使用哪个模板。告知用户选择结果。

### Step 2: 读取模板资源

根据选定模板，读取对应文件：
- 样式规范：`references/{模板名}.md` — 获取配色、字体层级、组件列表
- HTML模板：`assets/templates/{模板名}.html` — 获取 HTML 标记模式和内联样式
- 通用规范：`references/guidelines.md` — 通用排版原则

### Step 3: 分析文章结构

识别以下元素：
- 文章标题、副标题
- 章节划分
- 金句/核心观点
- 数据点/关键数字
- 列表/要点
- 引用/来源
- 时间线事件（如有）
- 结论/行动号召

### Step 4: 将内容映射到模板组件

#### blue-minimal 组件映射

| 文章元素 | 模板组件 | 说明 |
|----------|----------|------|
| 文章标题 | 标签 + 大标题 + 副标题 | 提取关键词做标签，标题可换行 |
| 章节开始 | 蓝色分割线 + 水印章节标题 | 水印编号 01/02/03 |
| 核心金句 | 蓝色金句区块 | 蓝底白字，主句+副句 |
| 关键数据/概念 | 三栏信息卡片 | 3个关键词+说明 |
| 目录/要点列表 | 目录卡片 | 灰底两列编号列表 |
| 正文段落 | 正文段落区块 | 15px，#1A1A1A，衬线字体 |
| 二级要点 | 二级标题 | 16px 蓝色加粗 |
| 文章结尾 | END标记 | 居中灰色 |

#### dark-tech 组件映射

| 文章元素 | 模板组件 | 说明 |
|----------|----------|------|
| 文章标题 | 封面Banner | 标签行 + 大字标题 + 副标题 |
| 关键数据 | 三列数据栏 | 嵌套table，橙红大数字 |
| 章节开始 | 章节头（双色标题） | 空格分隔标签 + 白色/橙红双色标题 |
| 功能/能力列表 | 能力卡片 | 绿色左边框，CAPABILITY标签 |
| 时间线事件 | 时间线节点 | 绿色=正面，红色=危机 |
| 引用/观点 | 引用卡片 | 橙红左边框 + 来源标注 |
| 类比/解释 | FEELS LIKE类比卡 | 琥珀标签头 + "所以呢?"框 |
| 排名/竞品 | 排名列表 | 大号彩色数字 + 描述 |
| 事件/案例 | 事件卡片 | 彩色左边框 |
| 结论 | 结尾递进区 | 文字透明度渐增，末句强调色 |

### Step 5: 生成HTML

严格按照模板HTML中的内联样式生成。关键规则：

**通用规则：**
- 所有样式必须内联（不用 `<style>` 标签）
- 不用 class/id 选择器
- 不用 JavaScript

**blue-minimal 专属规则：**
- 字体族：`'Times New Roman', serif`
- 主题色：`#0044FF`
- 正文色：`#1A1A1A`
- 章节间用蓝色分割线分隔
- 强调用蓝色加粗 `color: #0044FF; font-weight: bold` 或蓝色下划线

**dark-tech 专属规则：**
- 字体族：`-apple-system, 'Helvetica Neue', sans-serif`
- 主色：`#FF4500`（OrangeRed）
- 正文色：`#F0EFEB`
- **必须用 `<table>` 做主布局**，每章节一个 `<tr><td>`
- **所有 `<td>` 加 `border: none`**
- **背景色用实色 hex，不用 `rgba()`**（文字颜色的 rgba 可以）
- **不用 `display: flex` / `gap`**，用嵌套 table 代替
- **不用 `linear-gradient`**
- 章节间用分隔带 `<tr><td>` 分隔（`#0d0d0d`，16px高）
- 分隔带加 `font-size: 0; line-height: 0;`

### Step 6: 输出并预览

1. 将排版后的内容写入 HTML 文件，保存到 `output/` 目录
2. 文件名用文章主题的 slug（如 `output/ai-agent-analysis.html`）
3. 用 `open` 命令在浏览器中打开预览
4. 告知用户：在浏览器中选中内容区域 → 复制 → 粘贴到公众号编辑器

HTML文件外壳模板（根据模板选择背景色）：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>微信公众号排版预览</title>
<style>
  body { margin: 0; padding: 40px; background: {{背景色}}; }
  .preview-wrapper {
    max-width: 677px;
    margin: 0 auto;
    background: {{内容背景色}};
    box-shadow: 0 2px 20px rgba(0,0,0,0.08);
  }
  .tip { background: #fff3cd; padding: 12px; margin-bottom: 20px; border-radius: 4px; font-size: 14px; user-select: none; -webkit-user-select: none; max-width: 677px; margin: 0 auto 20px; }
</style>
</head>
<body>
<div class="tip">选中下方内容 → 复制 → 粘贴到公众号编辑器</div>
<div class="preview-wrapper">

<!-- 排版后的内容放这里 -->

</div>
</body>
</html>
```

背景色参数：
- `blue-minimal`：`background: #f5f5f5`，`内容背景色: #fff`
- `dark-tech`：`background: #222`，`内容背景色: #080808`

## 检查排版流程

根据文章使用的模板风格，对照相应规范检查：

### 通用检查项
- [ ] 所有样式是否内联
- [ ] 段落是否过长（>4行）
- [ ] 是否使用了不支持的CSS（position、外部样式表等）

### blue-minimal 检查项
- [ ] 字号是否为15px正文 / 32px大标题 / 22px章节标题
- [ ] 行间距是否为1.75倍
- [ ] 正文颜色是否为 #1A1A1A
- [ ] 字体是否为 Times New Roman, serif
- [ ] 主题色是否统一为 #0044FF
- [ ] 章节间是否有蓝色分割线

### dark-tech 检查项
- [ ] 主布局是否使用 `<table>`（不用 flex）
- [ ] 所有 `<td>` 是否有 `border: none`
- [ ] 背景色是否全部为实色 hex（不用 rgba 背景）
- [ ] 章节分隔带是否有 `font-size: 0; line-height: 0;`
- [ ] 是否使用了 `linear-gradient`（不允许）
- [ ] 正文色是否为 #F0EFEB
- [ ] 主强调色是否为 #FF4500

详细规范见对应的 `references/{模板名}.md`。

## 扩展新模板

未来添加新模板只需：
1. 添加 `assets/templates/{new-name}.html` — HTML模板
2. 添加 `references/{new-name}.md` — 样式规范
3. 在本文件的"可用模板"表格加一行
4. 在"组件映射"部分加对应的映射表
