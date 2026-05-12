#!/usr/bin/env python3
"""
砺儒云课堂作业检查 - 复用 liru-homework-reminder 项目
每天定时运行，通过 nanobot 推送微信提醒
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta

PROJECT_DIR = os.path.expanduser("~/liru-homework-reminder")
FETCH_SCRIPT = os.path.join(PROJECT_DIR, "fetch.py")
REPORT_SCRIPT = os.path.join(PROJECT_DIR, "report.py")
DATA_DIR = os.path.join(PROJECT_DIR, "data")
REPORT_FILE = os.path.join(DATA_DIR, "assignments_report.json")
COOKIE_FILE = os.path.join(DATA_DIR, "cookies.json")
SELECTED_COURSES_FILE = os.path.join(DATA_DIR, "selected_courses.json")

BJT = timezone(timedelta(hours=8))


def load_selected_courses():
    """读取用户选择的课程 ID 列表"""
    if not os.path.exists(SELECTED_COURSES_FILE):
        print(f"[Moodle] selected_courses.json 不存在，不过滤")
        return None
    with open(SELECTED_COURSES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def run_fetch():
    """运行 fetch.py 无头模式抓取作业"""
    print("[Moodle] 开始抓取作业...")
    result = subprocess.run(
        [sys.executable, FETCH_SCRIPT, "--headless", "--all"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        timeout=120,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"[Moodle] 抓取失败: {result.stderr}")
        return False
    return True


def run_report():
    """运行 report.py 生成报告"""
    print("[Moodle] 生成报告...")
    result = subprocess.run(
        [sys.executable, REPORT_SCRIPT],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
        timeout=30,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(f"[Moodle] 报告生成失败: {result.stderr}")
        return False
    return True


def load_report():
    """读取报告 JSON"""
    if not os.path.exists(REPORT_FILE):
        print(f"[Moodle] 报告文件不存在: {REPORT_FILE}")
        return None
    with open(REPORT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def filter_by_selected_courses(report, selected_ids):
    """只保留用户选择的课程中的作业"""
    if selected_ids is None:
        return report

    for key in ["overdue", "urgent", "normal", "no_deadline"]:
        items = report.get(key, [])
        report[key] = [item for item in items if item.get("courseid") in selected_ids]

    # 重新统计
    report["overdue_count"] = len(report.get("overdue", []))
    report["urgent_count"] = len(report.get("urgent", []))
    report["normal_count"] = len(report.get("normal", []))
    report["no_deadline_count"] = len(report.get("no_deadline", []))
    report["total_unsubmitted"] = (
        report["overdue_count"]
        + report["urgent_count"]
        + report["normal_count"]
        + report["no_deadline_count"]
    )
    return report


def format_message(report):
    """将报告格式化为微信推送消息"""
    now = datetime.now(BJT).strftime("%m/%d %H:%M")
    lines = [f"📖 砺儒作业提醒 ({now})"]

    total = report.get("total_unsubmitted", 0)
    overdue = report.get("overdue_count", 0)
    urgent = report.get("urgent_count", 0)
    normal = report.get("normal_count", 0)

    if total == 0:
        lines.append("✅ 没有待办作业，全部已提交！")
        return "\n".join(lines)

    lines.append(f"共 {total} 个待办（过期 {overdue} / 紧急 {urgent} / 普通 {normal}）")
    lines.append("")

    for item in report.get("overdue", []):
        lines.append(f"🔴 [过期] {item['name']}")
        lines.append(f"  课程: {item['course']}")
        lines.append(f"  截止: {item['due_date']}")
        lines.append("")

    for item in report.get("urgent", []):
        days = item.get("remaining_days", "?")
        lines.append(f"🟠 [紧急] {item['name']} (剩 {days} 天)")
        lines.append(f"  课程: {item['course']}")
        lines.append(f"  截止: {item['due_date']}")
        lines.append("")

    for item in report.get("normal", []):
        days = item.get("remaining_days", "?")
        lines.append(f"🟢 {item['name']} (剩 {days} 天)")
        lines.append(f"  课程: {item['course']}")
        lines.append(f"  截止: {item['due_date']}")
        lines.append("")

    return "\n".join(lines).strip()


def main():
    print("=" * 40)
    print("砺儒云课堂作业检查 v2")
    print("=" * 40)

    # 检查 Cookie 是否存在
    if not os.path.exists(COOKIE_FILE):
        print("[Moodle] ❌ Cookie 文件不存在！请先手动运行 fetch.py 登录一次。")
        print(f"   cd ~/liru-homework-reminder && python3 fetch.py")
        return

    # 读取已选课程
    selected_ids = load_selected_courses()
    if selected_ids:
        print(f"[Moodle] 已选课程: {selected_ids}")

    # 抓取
    if not run_fetch():
        print("[Moodle] ❌ 抓取失败，可能是 Cookie 过期，请重新运行 fetch.py 登录。")
        return

    # 生成报告
    if not run_report():
        return

    # 读取报告
    report = load_report()
    if not report:
        return

    # 按已选课程过滤
    report = filter_by_selected_courses(report, selected_ids)

    # 格式化消息
    message = format_message(report)
    print("\n" + "=" * 40)
    print(message)
    print("=" * 40)

    # 输出 JSON 供 nanobot 读取
    output = {
        "has_new": report.get("total_unsubmitted", 0) > 0,
        "total_unsubmitted": report.get("total_unsubmitted", 0),
        "message": message,
    }
    print("\n---NANOBOT_OUTPUT_START---")
    print(json.dumps(output, ensure_ascii=False))
    print("---NANOBOT_OUTPUT_END---")


if __name__ == "__main__":
    main()
