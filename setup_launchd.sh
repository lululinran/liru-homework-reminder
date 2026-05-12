#!/bin/bash
# 安装/卸载 macOS 定时任务（launchd）
# 用法:
#   ./setup_launchd.sh install   # 安装定时任务（每天早8点）
#   ./setup_launchd.sh uninstall # 卸载定时任务
#   ./setup_launchd.sh status    # 查看状态
#   ./setup_launchd.sh run       # 立即运行一次（不等定时）

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_NAME="com.liru.homework.reminder"
PLIST_SRC="${SCRIPT_DIR}/launchd.${PLIST_NAME}.plist.template"
PLIST_DST="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"
LOG_DIR="${SCRIPT_DIR}/logs"

usage() {
    echo "用法: $0 {install|uninstall|status|run}"
    echo ""
    echo "  install   - 安装定时任务（每天早8:00自动运行）"
    echo "  uninstall - 卸载定时任务"
    echo "  status    - 查看定时任务状态"
    echo "  run       - 立即手动运行一次"
    exit 1
}

do_install() {
    if [ ! -f "$PLIST_SRC" ]; then
        echo "[ERROR] 找不到模板文件: $PLIST_SRC"
        exit 1
    fi

    # 创建日志目录
    mkdir -p "$LOG_DIR"

    # 替换模板中的 {{SCRIPT_DIR}}
    sed "s|{{SCRIPT_DIR}}|$SCRIPT_DIR|g" "$PLIST_SRC" > "$PLIST_DST"

    echo "[OK] plist 已写入: $PLIST_DST"
    echo "     脚本路径: $SCRIPT_DIR/run.sh"
    echo "     运行时间: 每天 08:00"
    echo ""

    # 加载到 launchd
    launchctl load "$PLIST_DST" 2>/dev/null || true
    launchctl enable "gui/$(id -u)/${PLIST_NAME}" 2>/dev/null || true

    echo "[OK] 定时任务已启动！"
    echo ""
    echo "查看日志:   tail -f $LOG_DIR/launchd.log"
    echo "卸载任务:   $0 uninstall"
}

do_uninstall() {
    if [ -f "$PLIST_DST" ]; then
        launchctl unload "$PLIST_DST" 2>/dev/null || true
        rm -f "$PLIST_DST"
        echo "[OK] 定时任务已卸载"
    else
        echo "[INFO] 未找到已安装的定时任务"
    fi
}

do_status() {
    echo "=== 定时任务状态 ==="
    if [ -f "$PLIST_DST" ]; then
        echo "[plist] 已安装: $PLIST_DST"
    else
        echo "[plist] 未安装"
    fi
    echo ""
    echo "=== launchctl 列表 ==="
    launchctl list | grep "$PLIST_NAME" || echo "(未在运行)"
    echo ""
    if [ -f "$LOG_DIR/launchd.log" ]; then
        echo "=== 最近日志（最后10行）==="
        tail -10 "$LOG_DIR/launchd.log"
    fi
}

do_run() {
    echo "立即运行一次..."
    bash "${SCRIPT_DIR}/run.sh" --headless
}

if [ $# -eq 0 ]; then
    usage
fi

case "$1" in
    install)   do_install ;;
    uninstall) do_uninstall ;;
    status)    do_status ;;
    run)       do_run ;;
    *)         usage ;;
esac
