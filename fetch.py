#!/usr/bin/env python3
"""
华南师范大学 砺儒云课堂 - 作业抓取脚本
弹出浏览器让用户手动登录，登录后自动抓取所有课程的作业和提交状态。
支持 Cookie 保存复用，实现自动化定时运行。
支持自动过滤本学期课程，多策略识别提交状态。
"""

import json
import sys
import os
import re
import argparse
from datetime import datetime, timezone, timedelta
from playwright.sync_api import sync_playwright

MOODLE_URL = "https://moodle.scnu.edu.cn"
LOGIN_URL = f"{MOODLE_URL}/login/index.php"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUTPUT = os.path.join(SCRIPT_DIR, "data", "assignments_raw.json")
COOKIE_FILE = os.path.join(SCRIPT_DIR, "data", "cookies.json")

# 默认本学期课程ID（用户可自行修改，或使用 --all 参数抓取全部课程）
# 运行脚本时如不带 --course-ids，会先列出所有课程让你选择
DEFAULT_SEMESTER_IDS = set()


def save_cookies(context):
    """保存浏览器 Cookie 到文件"""
    cookies = context.cookies()
    os.makedirs(os.path.dirname(COOKIE_FILE), exist_ok=True)
    with open(COOKIE_FILE, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    print(f"[Cookie] 已保存到 {COOKIE_FILE}")


def load_cookies(context):
    """从文件加载 Cookie 到浏览器，返回是否成功"""
    if not os.path.exists(COOKIE_FILE):
        return False
    try:
        with open(COOKIE_FILE, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        if not cookies:
            return False
        context.add_cookies(cookies)
        return True
    except Exception:
        return False


def check_logged_in(page):
    """检查当前是否已登录（通过 Cookie）"""
    try:
        page.goto(f"{MOODLE_URL}/my/", wait_until="domcontentloaded", timeout=15000)
        # 如果跳转到了登录页，说明 Cookie 已过期
        if "login" in page.url:
            return False
        # 检查页面是否有用户相关元素
        page.wait_for_load_state("networkidle", timeout=10000)
        has_content = page.evaluate("""
            () => {
                // 页面包含课程列表或用户菜单，说明已登录
                const hasCourse = document.querySelector('a[href*="/course/view.php"]');
                const hasUserMenu = document.querySelector('.usermenu, [data-region="user-menu"]');
                const hasDashboard = document.querySelector('.dashboard, .mydashboard');
                return hasCourse || hasUserMenu || hasDashboard;
            }
        """)
        return bool(has_content)
    except Exception:
        return False


def wait_for_manual_login(page):
    """弹出浏览器等待用户手动登录"""
    page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)

    print()
    print("=" * 60)
    print("  请在弹出的浏览器中手动登录砺儒云课堂")
    print("  登录成功后脚本会自动继续...")
    print("  (等待超时: 3分钟)")
    print("=" * 60)
    print()

    try:
        page.wait_for_url(
            lambda url: "login" not in url and MOODLE_URL in url,
            timeout=180000
        )
        page.wait_for_load_state("networkidle", timeout=30000)
        print(f"\n[OK] 登录成功！当前页面: {page.url}")
        return True
    except Exception:
        if "login" not in page.url:
            print(f"\n[OK] 检测到已登录！当前页面: {page.url}")
            return True
        print("\n[ERROR] 等待登录超时（3分钟），请重新运行脚本")
        return False


def get_courses(page):
    """获取所有已注册课程"""
    print("\n[1/2] 获取课程列表...")
    page.goto(f"{MOODLE_URL}/my/courses.php", wait_until="networkidle", timeout=30000)

    courses = page.evaluate("""
        () => {
            const courses = [];
            const seen = new Set();

            const links = document.querySelectorAll('a[href*="/course/view.php?id="]');
            for (const link of links) {
                const href = link.getAttribute('href');
                const match = href.match(/id=(\\d+)/);
                if (match) {
                    const id = parseInt(match[1]);
                    if (!seen.has(id)) {
                        seen.add(id);
                        courses.push({
                            id: id,
                            fullname: link.textContent.trim() || `课程-${id}`,
                            url: href
                        });
                    }
                }
            }

            const cards = document.querySelectorAll('[data-courseid]');
            for (const card of cards) {
                const id = parseInt(card.getAttribute('data-courseid'));
                if (!seen.has(id)) {
                    seen.add(id);
                    const nameEl = card.querySelector('.coursename, .card-title, h3, h4, a');
                    courses.push({
                        id: id,
                        fullname: nameEl ? nameEl.textContent.trim() : `课程-${id}`,
                    });
                }
            }

            return courses;
        }
    """)

    print(f"[1/2] 找到 {len(courses)} 门课程")
    return courses


def select_courses_interactive(courses):
    """交互式选择要抓取的课程"""
    print("\n" + "-" * 60)
    print("  请选择要抓取的课程（输入编号，逗号分隔，a=全选）：")
    print("-" * 60)
    for i, c in enumerate(courses):
        print(f"  [{i + 1}] {c['fullname']}")

    print()
    user_input = input("你的选择: ").strip()

    if user_input.lower() == 'a':
        selected = courses
    else:
        indices = []
        for part in user_input.split(','):
            part = part.strip()
            if part.isdigit():
                idx = int(part) - 1
                if 0 <= idx < len(courses):
                    indices.append(idx)
        selected = [courses[i] for i in indices]

    print(f"\n已选择 {len(selected)} 门课程:")
    for c in selected:
        print(f"  - {c['fullname']}")
    return selected


def get_course_assignments(page, course_id, course_name):
    """获取某课程的所有作业和提交状态"""
    url = f"{MOODLE_URL}/mod/assign/index.php?id={course_id}"
    try:
        page.goto(url, wait_until="networkidle", timeout=20000)
    except Exception:
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
        except Exception as e:
            print(f"    [WARN] 无法访问: {e}")
            return []

    assignments = page.evaluate(f"""
        (courseName) => {{
            const results = [];
            const courseId = {course_id};

            // 查找作业表格
            const tables = document.querySelectorAll('table');
            for (const table of tables) {{
                const rows = table.querySelectorAll('tr');
                for (let i = 1; i < rows.length; i++) {{
                    const cols = rows[i].querySelectorAll('td');
                    if (cols.length >= 2) {{
                        const nameLink = cols[0].querySelector('a');
                        const name = nameLink ? nameLink.textContent.trim() : cols[0].textContent.trim();
                        const href = nameLink ? nameLink.getAttribute('href') : '';
                        if (!name) continue;

                        let cmId = '';
                        const idMatch = href.match(/id=(\\d+)/);
                        if (idMatch) cmId = idMatch[1];

                        // 截止日期
                        let dueDateText = '';
                        let dueTimestamp = 0;

                        for (let ci = 1; ci < cols.length; ci++) {{
                            const colText = cols[ci].textContent.trim();
                            const dm = colText.match(/(\\d{{4}})年(\\d{{1,2}})月(\\d{{1,2}})日[^\\d]*(\\d{{1,2}}):(\\d{{2}})/);
                            if (dm) {{
                                dueDateText = colText;
                                dueTimestamp = new Date(
                                    parseInt(dm[1]), parseInt(dm[2]) - 1,
                                    parseInt(dm[3]), parseInt(dm[4]), parseInt(dm[5])
                                ).getTime() / 1000;
                                break;
                            }}
                        }}

                        // 提交状态检测（5种策略）
                        let status = '';
                        let submitted = false;

                        // 策略1: 文字匹配
                        for (let ci = 1; ci < cols.length; ci++) {{
                            const colText = cols[ci].textContent.trim();
                            if (colText.includes('已提交') || colText.toLowerCase().includes('submitted') || colText === '是') {{
                                status = colText;
                                submitted = true;
                                break;
                            }}
                            if (colText.includes('未提交') || colText.toLowerCase().includes('not submitted') || colText === '-' || colText === '否') {{
                                status = colText;
                                submitted = false;
                                break;
                            }}
                        }}

                        // 策略2: img 标签
                        if (status === '') {{
                            const imgs = rows[i].querySelectorAll('img');
                            for (const img of imgs) {{
                                const alt = (img.getAttribute('alt') || '').toLowerCase();
                                const src = (img.getAttribute('src') || '').toLowerCase();
                                if (alt.includes('submitted') || alt.includes('已提交') ||
                                    src.includes('tick') || src.includes('check') || src.includes('yes')) {{
                                    submitted = true;
                                    status = '已提交';
                                    break;
                                }}
                                if (alt.includes('not submitted') || alt.includes('未提交') ||
                                    src.includes('cross') || src.includes('no')) {{
                                    submitted = false;
                                    status = '未提交';
                                    break;
                                }}
                            }}
                        }}

                        // 策略3: SVG 图标（Moodle 4.x）
                        if (status === '') {{
                            const svgs = rows[i].querySelectorAll('svg');
                            for (const svg of svgs) {{
                                const cls = (svg.getAttribute('class') || '');
                                const parentTitle = svg.closest('[title]')?.getAttribute('title') || '';
                                const titleEl = svg.querySelector('title');
                                const titleText = titleEl ? titleEl.textContent.trim().toLowerCase() : '';
                                if (titleText.includes('submitted') || titleText.includes('已提交') ||
                                    parentTitle.includes('Submitted') || parentTitle.includes('已提交') ||
                                    cls.includes('check') || cls.includes('tick') || cls.includes('success')) {{
                                    submitted = true;
                                    status = '已提交';
                                    break;
                                }}
                                if (titleText.includes('not') || titleText.includes('未') ||
                                    parentTitle.includes('Not') || parentTitle.includes('未') ||
                                    cls.includes('cross') || cls.includes('times') || cls.includes('danger')) {{
                                    submitted = false;
                                    status = '未提交';
                                    break;
                                }}
                            }}
                        }}

                        // 策略4: CSS class
                        if (status === '') {{
                            const icons = rows[i].querySelectorAll('[class*="check"], [class*="tick"], [class*="complete"], [class*="success"]');
                            for (const icon of icons) {{
                                const cls = icon.getAttribute('class') || '';
                                if (cls.includes('fa-check') || cls.includes('icon-check') ||
                                    cls.includes('fa-tick') || cls.includes('completion-complete') ||
                                    cls.includes('text-success')) {{
                                    submitted = true;
                                    status = '已提交';
                                    break;
                                }}
                            }}
                        }}

                        // 策略5: HTML 内容（最后一列）
                        if (status === '') {{
                            const lastCol = cols[cols.length - 1];
                            if (lastCol) {{
                                const html = lastCol.innerHTML.toLowerCase();
                                if (html.includes('submitted') || html.includes('已提交') || html.includes('fa-check') || html.includes('icon-check')) {{
                                    submitted = true;
                                    status = '已提交';
                                }} else if (html.includes('not') || html.includes('未') || html.includes('fa-times') || html.includes('fa-remove')) {{
                                    submitted = false;
                                    status = '未提交';
                                }}
                            }}
                        }}

                        results.push({{
                            name, course: courseName, courseid: courseId,
                            cmid, duedate_str: dueDateText, duedate: dueTimestamp,
                            status, submitted, url: href,
                        }});
                    }}
                }}
            }}

            // 备选: activity item 布局
            if (results.length === 0) {{
                const items = document.querySelectorAll('.activity-item, .activityinstance');
                for (const item of items) {{
                    const link = item.querySelector('a[href*="/mod/assign/"]');
                    if (link) {{
                        const name = link.textContent.trim();
                        const href = link.getAttribute('href');
                        let cmId = '';
                        const idMatch = href.match(/id=(\\d+)/);
                        if (idMatch) cmId = idMatch[1];

                        let dueDateText = '';
                        let dueTimestamp = 0;
                        const itemText = item.textContent;
                        const dm = itemText.match(/(\\d{{4}})年(\\d{{1,2}})月(\\d{{1,2}})日[^\\d]*(\\d{{1,2}}):(\\d{{2}})/);
                        if (dm) {{
                            dueDateText = dm[0];
                            dueTimestamp = new Date(
                                parseInt(dm[1]), parseInt(dm[2]) - 1,
                                parseInt(dm[3]), parseInt(dm[4]), parseInt(dm[5])
                            ).getTime() / 1000;
                        }}

                        let submitted = false;
                        let aStatus = '';
                        if (itemText.includes('已提交') || itemText.toLowerCase().includes('submitted')) {{
                            submitted = true;
                            aStatus = '已提交';
                        }} else {{
                            const svgs = item.querySelectorAll('svg');
                            for (const svg of svgs) {{
                                const titleEl = svg.querySelector('title');
                                if (titleEl) {{
                                    const t = titleEl.textContent.toLowerCase();
                                    if (t.includes('submitted') || t.includes('已提交')) {{
                                        submitted = true;
                                        aStatus = '已提交';
                                        break;
                                    }}
                                }}
                            }}
                        }}

                        results.push({{
                            name, course: courseName, courseid: courseId,
                            cmid, duedate_str: dueDateText, duedate: dueTimestamp,
                            status: aStatus || '', submitted, url: href,
                        }});
                    }}
                }}
            }}

            return results;
        }}
    """)

    return assignments


def main():
    parser = argparse.ArgumentParser(description="砺儒云课堂作业抓取工具")
    parser.add_argument("--all", action="store_true",
                       help="抓取所有课程的作业（默认会交互式选择）")
    parser.add_argument("--course-ids", type=str, default="",
                       help="指定课程ID（逗号分隔），如 --course-ids 19038,18969")
    parser.add_argument("-o", "--output", type=str, default=DEFAULT_OUTPUT,
                       help=f"输出JSON路径（默认: data/assignments_raw.json）")
    parser.add_argument("--headless", action="store_true",
                       help="无头模式（不弹出浏览器，用于定时任务自动运行）")
    args = parser.parse_args()

    print("=" * 60)
    print("  砺儒云课堂 - 作业抓取工具")
    print("  华南师范大学 moodle.scnu.edu.cn")
    print("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=args.headless,
            args=["--no-sandbox"]
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            # 尝试复用已保存的 Cookie
            logged_in = False
            if load_cookies(context):
                print("\n[Cookie] 发现已保存的登录信息，尝试自动登录...")
                if check_logged_in(page):
                    print("[Cookie] 自动登录成功！")
                    logged_in = True
                    # Cookie 有效，刷新保存一次
                    save_cookies(context)
                else:
                    print("[Cookie] Cookie 已过期，需要重新登录")
                    os.remove(COOKIE_FILE)

            if not logged_in:
                if args.headless:
                    print("\n[ERROR] Cookie 已过期，无头模式下无法手动登录。")
                    print("请先运行一次非无头模式登录：python fetch.py")
                    browser.close()
                    sys.exit(1)

                if not wait_for_manual_login(page):
                    browser.close()
                    sys.exit(1)

                # 登录成功，保存 Cookie
                save_cookies(context)

            courses = get_courses(page)
            if not courses:
                print("\n[ERROR] 未找到任何课程")
                browser.close()
                sys.exit(1)

            # 确定要抓取的课程
            if args.course_ids:
                target_ids = set(int(x.strip()) for x in args.course_ids.split(","))
                selected_courses = [c for c in courses if c.get("id") in target_ids]
                print(f"\n已通过参数指定 {len(selected_courses)} 门课程")
            elif args.all:
                selected_courses = courses
                print(f"\n将抓取全部 {len(courses)} 门课程")
            else:
                selected_courses = select_courses_interactive(courses)

            if not selected_courses:
                print("\n未选择任何课程，退出。")
                browser.close()
                sys.exit(0)

            print(f"\n[2/2] 开始获取各课程作业...")
            all_assignments = []

            for course in selected_courses:
                cid = course.get("id")
                cname = course.get("fullname", f"课程-{cid}")
                print(f"\n  [{cname}] (ID: {cid})")

                assigns = get_course_assignments(page, cid, cname)
                if assigns:
                    all_assignments.extend(assigns)
                    submitted_n = sum(1 for a in assigns if a.get("submitted"))
                    print(f"    -> {len(assigns)} 个作业（已提交 {submitted_n}，未提交 {len(assigns) - submitted_n}）")
                else:
                    print(f"    -> 无作业")

            now = datetime.now(tz=timezone(timedelta(hours=8)))
            not_submitted = [a for a in all_assignments if not a.get("submitted", False)]

            print("\n" + "=" * 60)
            print(f"  抓取完成")
            print(f"  总计: {len(all_assignments)} 个作业")
            print(f"  已提交: {len(all_assignments) - len(not_submitted)} 个")
            print(f"  未提交: {len(not_submitted)} 个")
            print("=" * 60)

            output = {
                "fetch_time": now.strftime("%Y-%m-%d %H:%M:%S"),
                "total_assignments": len(all_assignments),
                "submitted_count": len(all_assignments) - len(not_submitted),
                "not_submitted_count": len(not_submitted),
                "not_submitted": not_submitted,
                "all_assignments": all_assignments,
            }

            # 确保输出目录存在
            os.makedirs(os.path.dirname(args.output), exist_ok=True)
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(output, f, ensure_ascii=False, indent=2)
            print(f"\n数据已保存: {args.output}")

            # 抓取完成后更新 Cookie（可能续期了）
            save_cookies(context)

            if not args.headless:
                print("\n完成！3秒后关闭浏览器...")
                page.wait_for_timeout(3000)

        except Exception as e:
            print(f"\n[ERROR] 出错: {e}")
            import traceback
            traceback.print_exc()
            try:
                page.wait_for_timeout(10000)
            except KeyboardInterrupt:
                pass
        finally:
            browser.close()


if __name__ == "__main__":
    main()
