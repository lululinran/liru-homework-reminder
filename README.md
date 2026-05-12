# 砺儒云课堂作业提醒工具

华南师范大学砺儒云课堂（moodle.scnu.edu.cn）的作业抓取和提醒工具。自动抓取所有课程作业，到期**微信提醒**你。设置一次，每天自动推送，从此告别手忙脚乱。

> **注意**：本工具仅供学习交流使用，请遵守学校相关规定。

## 安装

打开在线安装指南，跟着步骤操作，几分钟搞定：

**[lululinran.github.io/liru-homework-reminder](https://lululinran.github.io/liru-homework-reminder/)**

支持 macOS 和 Windows，包含微信推送配置和定时任务设置。

## 快速开始

> **怎么打开终端？**
> - **macOS**：按 `Command + 空格` 调出搜索，输入 `Terminal` 或「终端」，按回车
> - **Windows**：按 `Win + R`，输入 `powershell`，按回车；或右键开始菜单 →「Windows PowerShell」

```bash
# 1. 克隆仓库
git clone https://github.com/lululinran/liru-homework-reminder.git
cd liru-homework-reminder

# 2. 安装依赖
pip install playwright
playwright install chromium

# 3. 首次运行（弹出浏览器，手动登录砺儒云课堂）
python fetch.py
# 登录成功后选择要抓取的课程，等待抓取完成

# 4. 获取 Server酱 SendKey（微信推送用）
#    ① 用浏览器打开 https://sct.ftqq.com/
#    ② 微信扫码登录
#    ③ 在页面复制你的 SendKey（格式: SCTxxxxx）

# 5. 配置推送
cp config.json.example config.json
# 编辑 config.json，在 "sendkey": "" 里填入你的 SendKey
# macOS: nano config.json （Ctrl+O 保存，Ctrl+X 退出）
# Windows: notepad config.json

# 6. 测试推送（微信应该会收到消息）
python report.py
```

## 定时自动提醒

确认推送正常后，设置定时任务，每天自动运行：

**macOS：**
```bash
chmod +x setup_launchd.sh
./setup_launchd.sh install    # 安装（每天 8:00）
./setup_launchd.sh status     # 查看状态
./setup_launchd.sh run        # 立即运行一次
./setup_launchd.sh uninstall  # 取消
```

**Windows（管理员 PowerShell）：**
```powershell
.\setup_task.ps1 install      # 安装（每天 8:00）
.\setup_task.ps1 status       # 查看状态
.\setup_task.ps1 run          # 立即运行一次
.\setup_task.ps1 uninstall    # 取消
```

> Cookie 通常几周后过期，过期后重新运行 `python fetch.py` 手动登录一次即可。

## 帮同学设置

很多同学不怎么用电脑？你可以用自己的电脑帮多个同学设置：

1. 帮同学注册 Server酱（[sct.ftqq.com](https://sct.ftqq.com/)）并获取 SendKey
2. 用同学的账号登录一次 `python fetch.py`（保存 Cookie）
3. 在 `config.json` 中填入同学的 SendKey
4. 安装定时任务 `./setup_launchd.sh install` 或 `.\setup_task.ps1 install`

每个同学一份独立的配置（Cookie + SendKey），互不影响。如果同学没有电脑，可以把电脑借出来，依次登录保存即可。

## 功能

- 自动抓取砺儒云课堂所有课程的作业信息
- 智能识别作业提交状态（5种检测策略）
- 按截止日期分类：已过期 / 紧急（3天内）/ 待提交 / 无截止日期
- **消息推送**：支持 Server酱（微信）、企业微信机器人、邮件
- **定时任务**：macOS（launchd）/ Windows（Task Scheduler），每天自动运行
- 支持手动标记已提交的作业、按课程过滤
- Cookie 保存复用，首次登录后自动运行无需再次登录

## 配置推送

```bash
cp config.json.example config.json
# 编辑 config.json，填入 Server酱 SendKey（推荐）
# 获取方式: https://sct.ftqq.com/ 微信扫码登录
```

支持三种推送（可同时启用）：
- **Server酱**（微信推送，推荐）— 填 `serverchan.sendkey`
- **企业微信机器人** — 填 `wecom.webhook`
- **邮件**（QQ邮箱/163） — 填 `email` 相关字段

## 文件说明

```
liru-homework-reminder/
├── fetch.py                     # 作业数据抓取（支持 Cookie 复用）
├── report.py                    # 报告生成 + 推送
├── notify.py                    # 推送模块（Server酱/企业微信/邮件）
├── run.sh / run.bat            # 一键运行（macOS / Windows）
├── setup_launchd.sh            # macOS 定时任务安装
├── setup_task.ps1              # Windows 定时任务安装
├── config.json.example          # 推送配置模板
└── docs/index.html             # 在线安装指南（GitHub Pages）
```

## License

MIT License
