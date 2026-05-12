# 砺儒云课堂作业提醒工具

华南师范大学砺儒云课堂（moodle.scnu.edu.cn）的作业抓取和提醒工具。自动抓取所有课程的作业信息，识别提交状态，生成待办提醒报告。

> **注意**：本工具仅供学习交流使用，请遵守学校相关规定。

## 功能

- 自动抓取砺儒云课堂所有课程的作业信息
- 智能识别作业提交状态（5种检测策略）
- 按截止日期分类：已过期 / 紧急（3天内）/ 待提交 / 无截止日期
- 支持手动标记已提交的作业（应对检测不准的情况）
- 支持按课程过滤
- 交互式选择要抓取的课程，也可指定课程ID

## 使用效果

```
# 砺儒云课堂 - 待办作业提醒

> 更新时间：2026-05-12 16:27  |  仅显示未提交的作业

**共 2 个待办作业**（已过期 0，紧急 0，普通 2，无截止日期 0）

---
## 待提交（2个）

| 作业 | 课程 | 截止日期 | 剩余天数 |
|:-----|:-----|:---------|:--------|
| 第四章数据加密 | 数据安全 | 2026-05-18 23:59 | 6天 |
| 课程项目 | Web系统开发 | 2026-06-29 00:00 | 47天 |
```

## 安装

### 环境要求

- Python 3.8+
- [Playwright](https://playwright.dev/python/)（浏览器自动化）

### 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/你的用户名/liru-homework-reminder.git
cd liru-homework-reminder

# 2. 安装依赖
pip install playwright

# 3. 安装浏览器（只需要运行一次）
playwright install chromium
```

## 使用方法

### 第一步：抓取数据

```bash
python fetch.py
```

运行后会弹出浏览器窗口：

1. **在浏览器中手动登录**砺儒云课堂（统一身份认证登录）
2. 登录成功后脚本会自动继续
3. **交互式选择要抓取的课程**（输入编号，逗号分隔，`a` 全选）
4. 等待抓取完成，数据保存在 `data/assignments_raw.json`

**命令行参数：**

```bash
# 抓取所有课程
python fetch.py --all

# 指定课程ID
python fetch.py --course-ids 19038,18969,18899

# 指定输出路径
python fetch.py -o /path/to/output.json
```

### 第二步：生成报告

```bash
python report.py
```

读取抓取的数据，生成 Markdown 格式的待办报告，保存在 `assignments_report.md`。

**命令行参数：**

```bash
# 手动标记已提交的作业（格式：课程ID:作业名）
python report.py --exclude-submitted "19038:实验一,18969:第一章作业"

# 只看特定课程
python report.py --only-courses "机器学习,数据安全"

# 指定输入输出
python report.py -i data/assignments_raw.json -o my_report.md
```

### 完整流程示例

```bash
# 第一次使用
python fetch.py
python report.py

# 日常使用（数据没过期时只需重新生成报告更新天数）
python report.py

# 如果想抓取最新数据
python fetch.py --course-ids 19038,18969
python report.py
```

## 常见问题

### Q: 为什么有些作业我明明交了，还是显示未提交？

提交状态检测依赖 Moodle 页面结构，不同课程的作业页面布局可能不同。你可以用 `--exclude-submitted` 参数手动标记：

```bash
python report.py --exclude-submitted "19038:实验一,18969:第一章作业"
```

### Q: 提示"等待登录超时"怎么办？

登录超时时间为 3 分钟。如果超时，重新运行脚本即可，不需要等 1 小时。

> **重要**：不要尝试用程序自动填写账号密码登录！多次尝试会导致账号被锁定（约1小时）。

### Q: 抓取的数据多久过期？

建议每周重新运行一次 `fetch.py` 抓取最新数据。日常只需运行 `report.py` 刷新报告中的过期天数即可。

### Q: 只想看当前学期的作业怎么办？

`fetch.py` 运行时会交互式让你选择课程，只选本学期的即可。

## 文件说明

```
liru-homework-reminder/
├── fetch.py                # 作业数据抓取脚本
├── report.py               # 报告生成脚本
├── assignments_report.md   # 生成的报告（gitignored）
└── data/                   # 数据目录（gitignored）
    ├── assignments_raw.json    # 抓取的原始数据
    └── assignments_report.json # 处理后的结构化数据
```

## 技术细节

- **登录方式**：手动浏览器登录（不存储密码，不会锁号）
- **提交状态检测**：5种策略
  1. 文字匹配（已提交/Submitted）
  2. img 标签 alt/src 属性
  3. SVG 图标（Moodle 4.x）
  4. CSS class（fa-check, icon-check 等）
  5. HTML 内容分析
- **日期解析**：支持中文日期格式（2026年05月18日 星期一 23:59）

## License

MIT License
