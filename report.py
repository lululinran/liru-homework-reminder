#!/usr/bin/env python3
"""
砺儒云课堂 - 作业提醒报告生成器
读取 fetch.py 的输出，生成 Markdown 报告，并支持推送到微信/企业微信/邮件。
支持：手动标记已提交、按课程过滤、消息推送。
"""

import json
import re
import os
import argparse
from datetime import datetime, timezone, timedelta
from notify import load_config, build_push_text, push_all

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_INPUT = os.path.join(SCRIPT_DIR, "data", "assignments_raw.json")
DEFAULT_OUTPUT_MD = os.path.join(SCRIPT_DIR, "assignments_report.md")
DEFAULT_OUTPUT_JSON = os.path.join(SCRIPT_DIR, "data", "assignments_report.json")
SELECTED_COURSES_FILE = os.path.join(SCRIPT_DIR, "data", "selected_courses.json")


def parse_chinese_date(text):
    """解析中文日期: 2026年05月18日 星期一 23:59"""
    if not text:
        return None
    m = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日[^\d]*(\d{1,2}):(\d{2})', text)
    if m:
        return datetime(int(m[1]), int(m[2]), int(m[3]), int(m[4]), int(m[5]),
                       tzinfo=timezone(timedelta(hours=8)))
    return None


def parse_due_from_description(text):
    """从描述中提取截止日期: 5月18日23:50"""
    if not text:
        return None
    m = re.search(r'(\d{1,2})月(\d{1,2})日(\d{1,2}):(\d{2})', text)
    if m:
        now = datetime.now(tz=timezone(timedelta(hours=8)))
        return datetime(now.year, int(m[1]), int(m[2]), int(m[3]), int(m[4]),
                       tzinfo=timezone(timedelta(hours=8)))
    return None


def main():
    parser = argparse.ArgumentParser(description="砺儒云课堂作业报告生成器")
    parser.add_argument("-i", "--input", type=str, default=DEFAULT_INPUT,
                       help="输入JSON路径（fetch.py 的输出）")
    parser.add_argument("-o", "--output", type=str, default=DEFAULT_OUTPUT_MD,
                       help="输出Markdown报告路径")
    parser.add_argument("--exclude-submitted", type=str, default="",
                       help="手动排除已提交的作业（课程ID:作业名，逗号分隔），"
                            "例: --exclude-submitted 19038:实验一,18969:第一章作业")
    parser.add_argument("--only-courses", type=str, default="",
                       help="只显示指定课程的作业（课程名关键词，逗号分隔），"
                            "例: --only-courses 机器学习,数据安全")
    parser.add_argument("--no-push", action="store_true",
                       help="跳过消息推送，只生成报告")
    args = parser.parse_args()

    with open(args.input, 'r', encoding='utf-8') as f:
        raw = json.load(f)

    now = datetime.now(tz=timezone(timedelta(hours=8)))

    # 解析手动已提交名单
    manually_submitted = set()
    if args.exclude_submitted:
        for item in args.exclude_submitted.split(","):
            item = item.strip()
            if ":" in item:
                cid_str, name = item.split(":", 1)
                manually_submitted.add((int(cid_str.strip()), name.strip()))

    # 解析课程过滤关键词
    course_keywords = []
    if args.only_courses:
        course_keywords = [k.strip() for k in args.only_courses.split(",")]

    # 获取所有作业（优先用 all_assignments，回退到 not_submitted）
    all_assignments = raw.get("all_assignments", raw.get("not_submitted", []))

    # 过滤1: 已提交的不要
    unsubmitted = [a for a in all_assignments if not a.get("submitted", False)]

    # 过滤2: 只保留 selected_courses.json 中选定的课程（如果存在）
    selected_course_ids = None
    if os.path.exists(SELECTED_COURSES_FILE):
        try:
            with open(SELECTED_COURSES_FILE, "r", encoding="utf-8") as f:
                selected_course_ids = set(json.load(f))
        except Exception:
            pass
    if selected_course_ids:
        unsubmitted = [a for a in unsubmitted
                       if a.get("courseid", 0) in selected_course_ids]

    # 过滤3: 手动标记为已提交的也不要
    if manually_submitted:
        unsubmitted = [a for a in unsubmitted
                       if (a.get("courseid", 0), a.get("name", "")) not in manually_submitted]

    # 过滤4: 课程关键词过滤
    if course_keywords:
        unsubmitted = [a for a in unsubmitted
                       if any(kw in a.get("course", "") or kw in a.get("name", "")
                              for kw in course_keywords)]

    # 解析截止日期
    processed = []
    for a in unsubmitted:
        cid = a.get("courseid", 0)
        name = a.get("name", "")
        duedate_str = a.get("duedate_str", "")
        duedate_ts = a.get("duedate", 0)

        course_name = a.get("course", f"课程-{cid}")

        # 优先用 fetch.py 提供的 duedate timestamp
        due_dt = None
        due_fmt = ""

        if duedate_ts and duedate_ts > 0:
            try:
                due_dt = datetime.fromtimestamp(duedate_ts, tz=timezone(timedelta(hours=8)))
                due_fmt = due_dt.strftime("%Y-%m-%d %H:%M")
            except (OSError, ValueError):
                pass

        # 回退: 从 duedate_str 文本解析
        if not due_dt and duedate_str:
            due_dt = parse_chinese_date(duedate_str)
            if due_dt:
                due_fmt = due_dt.strftime("%Y-%m-%d %H:%M")

        # 再回退: 从描述文本中提取
        if not due_dt and duedate_str:
            due_dt = parse_due_from_description(duedate_str)
            if due_dt:
                due_fmt = due_dt.strftime("%Y-%m-%d %H:%M")

        processed.append({
            "name": name,
            "course": course_name,
            "courseid": cid,
            "description": duedate_str,
            "due_date": due_fmt,
            "due_timestamp": int(due_dt.timestamp()) if due_dt else 0,
        })

    # 分为有截止日期和无截止日期
    with_deadline = [a for a in processed if a.get("due_timestamp", 0) > 0]
    without_deadline = [a for a in processed if a.get("due_timestamp", 0) == 0]

    # 分类：过期 / 紧急(<=3天) / 普通
    overdue, urgent, normal = [], [], []
    for a in with_deadline:
        ts = a.get("due_timestamp", 0)
        due_dt = datetime.fromtimestamp(ts, tz=timezone(timedelta(hours=8)))
        remaining = (due_dt - now).days
        a["remaining_days"] = remaining
        if remaining < 0:
            overdue.append(a)
        elif remaining <= 3:
            urgent.append(a)
        else:
            normal.append(a)

    overdue.sort(key=lambda x: x["remaining_days"], reverse=True)
    urgent.sort(key=lambda x: x["remaining_days"])
    normal.sort(key=lambda x: x["remaining_days"])

    total_unsubmitted = len(with_deadline) + len(without_deadline)

    # 生成 Markdown 报告
    lines = []
    lines.append("# 砺儒云课堂 - 待办作业提醒")
    lines.append(f"\n> 更新时间：{now.strftime('%Y-%m-%d %H:%M')}  |  "
                 f"仅显示未提交的作业")
    lines.append("")

    if total_unsubmitted == 0:
        lines.append("## 没有待办作业")
        lines.append("")
        lines.append("所有作业均已提交。")
    else:
        lines.append(f"**共 {total_unsubmitted} 个待办作业**"
                     f"（已过期 {len(overdue)}，紧急 {len(urgent)}，"
                     f"普通 {len(normal)}，无截止日期 {len(without_deadline)}）")
        lines.append("")

        if overdue:
            lines.append("---")
            lines.append(f"## 已过期（{len(overdue)}个）")
            lines.append("")
            lines.append("| 作业 | 课程 | 截止日期 | 过期天数 |")
            lines.append("|:-----|:-----|:---------|:--------|")
            for a in overdue:
                lines.append(f"| {a['name']} | {a['course']} | {a['due_date']} | "
                           f"{-a['remaining_days']}天 |")
            lines.append("")

        if urgent:
            lines.append("---")
            lines.append(f"## 紧急 - 3天内截止（{len(urgent)}个）")
            lines.append("")
            lines.append("| 作业 | 课程 | 截止日期 | 剩余天数 |")
            lines.append("|:-----|:-----|:---------|:--------|")
            for a in urgent:
                lines.append(f"| {a['name']} | {a['course']} | {a['due_date']} | "
                           f"{a['remaining_days']}天 |")
            lines.append("")

        if normal:
            lines.append("---")
            lines.append(f"## 待提交（{len(normal)}个）")
            lines.append("")
            lines.append("| 作业 | 课程 | 截止日期 | 剩余天数 |")
            lines.append("|:-----|:-----|:---------|:--------|")
            for a in normal:
                lines.append(f"| {a['name']} | {a['course']} | {a['due_date']} | "
                           f"{a['remaining_days']}天 |")
            lines.append("")

        if without_deadline:
            lines.append("---")
            lines.append(f"## 无截止日期 - 可能期末统一验收（{len(without_deadline)}个）")
            lines.append("")
            lines.append("| 作业 | 课程 | 备注 |")
            lines.append("|:-----|:-----|:-----|")
            for a in without_deadline:
                desc = a.get("description", "")[:60]
                lines.append(f"| {a['name']} | {a['course']} | {desc} |")
            lines.append("")

    lines.append("---")
    lines.append(f"*数据来源：砺儒云课堂 (moodle.scnu.edu.cn) | "
                f"{now.strftime('%Y-%m-%d %H:%M')}*")

    report_text = "\n".join(lines)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(report_text)

    # 保存 JSON
    json_path = os.path.join(os.path.dirname(args.output) or SCRIPT_DIR, "data",
                             "assignments_report.json")
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    output_json = {
        "fetch_time": raw.get("fetch_time", ""),
        "report_time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "total_unsubmitted": total_unsubmitted,
        "overdue_count": len(overdue),
        "urgent_count": len(urgent),
        "normal_count": len(normal),
        "no_deadline_count": len(without_deadline),
        "overdue": overdue,
        "urgent": urgent,
        "normal": normal,
        "no_deadline": without_deadline,
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output_json, f, ensure_ascii=False, indent=2)

    # 终端输出
    print(report_text)
    print(f"\n报告已保存: {args.output}")
    print(f"JSON已保存: {json_path}")

    # 消息推送
    if not args.no_push:
        config = load_config()
        if any(config.get(k) for k in ("serverchan", "wecom", "email")):
            # 全部已提交 → 静默不推
            if total_unsubmitted == 0:
                print("\n[推送] 全部已提交，无需提醒，跳过推送。")
            else:
                push_text = build_push_text(report_text, {
                    "total": total_unsubmitted,
                    "overdue": overdue,
                    "urgent": urgent,
                    "normal": normal,
                    "no_deadline": without_deadline,
                })
                results = push_all(push_text, report_text, config)

                if results:
                    print("\n" + "-" * 40)
                    print("推送结果：")
                    for channel, ok, msg in results:
                        status = "✅" if ok else "❌"
                        print(f"  {status} {channel}: {msg}")
        else:
            print("\n[提示] 未找到 config.json，跳过推送。"
                  "创建 config.json 可开启微信/邮件提醒，详见 README。")
    else:
        print("\n[已跳过推送] (--no-push)")


if __name__ == "__main__":
    main()
