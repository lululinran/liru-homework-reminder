#!/usr/bin/env python3
"""
砺儒云课堂 - 消息推送模块
支持：Server酱(微信)、企业微信机器人、邮件
"""

import json
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.request import Request, urlopen
from urllib.error import URLError

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")


def load_config():
    """加载配置文件，不存在则返回空 dict"""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def build_push_text(report_text, summary):
    """
    根据完整报告构建适合推送的精简文本。
    summary 是一个 dict，包含 overdue/urgent/normal/no_deadline 列表。
    """
    lines = []
    lines.append("📖 砺儒云课堂 - 作业提醒")
    lines.append("")

    total = summary.get("total", 0)
    if total == 0:
        lines.append("✅ 没有待办作业，全部已提交！")
        return "\n".join(lines)

    overdue = summary.get("overdue", [])
    urgent = summary.get("urgent", [])
    normal = summary.get("normal", [])
    no_deadline = summary.get("no_deadline", [])

    lines.append(f"共 {total} 个待办（过期 {len(overdue)} / 紧急 {len(urgent)} / "
                 f"普通 {len(normal)} / 无截止日期 {len(no_deadline)}）")
    lines.append("")

    if overdue:
        lines.append("⚠️ 已过期：")
        for a in overdue:
            lines.append(f"  · {a['name']}（{a['course']}）过期 {-a['remaining_days']}天")
        lines.append("")

    if urgent:
        lines.append("🔴 紧急（3天内）：")
        for a in urgent:
            tag = "今天截止" if a["remaining_days"] == 0 else f"剩{a['remaining_days']}天"
            lines.append(f"  · {a['name']}（{a['course']}）{tag} {a['due_date']}")
        lines.append("")

    if normal:
        lines.append("📝 待提交：")
        for a in normal:
            lines.append(f"  · {a['name']}（{a['course']}）剩{a['remaining_days']}天 {a['due_date']}")
        lines.append("")

    if no_deadline:
        lines.append("📋 无截止日期（可能期末验收）：")
        for a in no_deadline:
            lines.append(f"  · {a['name']}（{a['course']}）")
        lines.append("")

    return "\n".join(lines)


def push_serverchan(title, content, config):
    """
    通过 Server酱 推送到微信。
    配置: config["serverchan"]["sendkey"]
    """
    sendkey = config.get("serverchan", {}).get("sendkey", "")
    if not sendkey:
        return False, "未配置 serverchan.sendkey"

    url = f"https://sctapi.ftqq.com/{sendkey}.send"
    data = json.dumps({"title": title, "desp": content}).encode("utf-8")
    req = Request(url, data=data, headers={"Content-Type": "application/json"})

    try:
        with urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if result.get("code") == 0:
                return True, "Server酱推送成功"
            else:
                return False, f"Server酱返回错误: {result.get('message', '')}"
    except URLError as e:
        return False, f"Server酱请求失败: {e}"
    except Exception as e:
        return False, f"Server酱推送异常: {e}"


def push_wecom(content, config):
    """
    通过企业微信群机器人 Webhook 推送。
    配置: config["wecom"]["webhook"]
    """
    webhook = config.get("wecom", {}).get("webhook", "")
    if not webhook:
        return False, "未配置 wecom.webhook"

    payload = json.dumps({
        "msgtype": "text",
        "text": {"content": content}
    }).encode("utf-8")
    req = Request(webhook, data=payload, headers={"Content-Type": "application/json"})

    try:
        with urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if result.get("errcode") == 0:
                return True, "企业微信推送成功"
            else:
                return False, f"企业微信返回错误: {result.get('errmsg', '')}"
    except URLError as e:
        return False, f"企业微信请求失败: {e}"
    except Exception as e:
        return False, f"企业微信推送异常: {e}"


def push_email(title, content, config):
    """
    通过 SMTP 发送邮件。
    配置:
      config["email"]["smtp_host"], config["email"]["smtp_port"]
      config["email"]["sender"], config["email"]["password"]
      config["email"]["receiver"]  (可选，默认同 sender)
    """
    email_cfg = config.get("email", {})
    smtp_host = email_cfg.get("smtp_host", "")
    smtp_port = email_cfg.get("smtp_port", 465)
    sender = email_cfg.get("sender", "")
    password = email_cfg.get("password", "")
    receiver = email_cfg.get("receiver", sender)

    if not all([smtp_host, sender, password]):
        return False, "未完整配置 email（需要 smtp_host, sender, password）"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = title
    msg["From"] = sender
    msg["To"] = receiver

    # 纯文本版
    msg.attach(MIMEText(content, "plain", "utf-8"))
    # HTML 版（用 <pre> 保持格式）
    html = f"<pre style='font-family:monospace;font-size:14px;line-height:1.6;'>" \
           f"{content.replace('<', '&lt;').replace('>', '&gt;')}</pre>"
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=15)
            if smtp_port == 587:
                server.starttls()
        server.login(sender, password)
        server.sendmail(sender, receiver, msg.as_string())
        server.quit()
        return True, f"邮件推送成功 -> {receiver}"
    except Exception as e:
        return False, f"邮件推送失败: {e}"


def push_all(title, push_text, full_markdown, config):
    """
    根据配置推送所有已启用的渠道。
    返回: list of (channel_name, success, message)
    """
    results = []

    if config.get("serverchan", {}).get("sendkey"):
        ok, msg = push_serverchan(title, full_markdown, config)
        results.append(("Server酱(微信)", ok, msg))

    if config.get("wecom", {}).get("webhook"):
        ok, msg = push_wecom(push_text, config)
        results.append(("企业微信", ok, msg))

    if config.get("email", {}).get("smtp_host"):
        ok, msg = push_email(title, push_text, config)
        results.append(("邮件", ok, msg))

    return results
