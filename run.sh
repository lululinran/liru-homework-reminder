#!/bin/bash
# 砺儒云课堂作业提醒 - 完整运行脚本
# 一键完成：抓取数据 + 生成报告 + 推送通知
#
# 用法：
#   ./run.sh          # 正常模式（有头浏览器，首次运行用这个）
#   ./run.sh --headless  # 无头模式（定时任务用这个）

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

HEADLESS=""
if [ "$1" = "--headless" ]; then
    HEADLESS="--headless"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 以无头模式运行..."
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 以正常模式运行..."
fi

# Step 1: 抓取数据
echo ""
echo "==> Step 1: 抓取作业数据..."
python3 fetch.py --all $HEADLESS -o data/assignments_raw.json

# Step 2: 生成报告 + 推送
echo ""
echo "==> Step 2: 生成报告 + 推送通知..."
python3 report.py -i data/assignments_raw.json

echo ""
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 全部完成！"
