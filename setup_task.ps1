# 砺儒云课堂作业提醒 - Windows 定时任务安装脚本
# 用法:
#   setup_task.ps1 install   # 安装定时任务（每天早8点）
#   setup_task.ps1 uninstall # 卸载定时任务
#   setup_task.ps1 status    # 查看状态
#   setup_task.ps1 run      # 立即运行一次
#
# 需要 PowerShell 5.1+（Windows 10/11 自带）

param(
    [string]$Action = ""
)

$ErrorActionPreference = "Stop"
$TaskName = "LiruHomeworkReminder"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RunBat = Join-Path $ScriptDir "run.bat"
$LogDir = Join-Path $ScriptDir "logs"
$StdoutLog = Join-Path $LogDir "task.log"
$StderrLog = Join-Path $LogDir "task_err.log"

function Write-Step($msg) {
    Write-Host "`n[setup_task] $msg" -ForegroundColor Cyan
}

function New-LogDir {
    if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }
}

function Test-CommandExists($cmd) {
    try { Get-Command $cmd -ErrorAction Stop | Out-Null; return $true }
    catch { return $false }
}

# ─── Install ────────────────────────────────────────────────
function Install-Task {
    Write-Step "检查依赖..."

    if (-not (Test-CommandExists "python")) {
        Write-Host "  [ERROR] 未找到 python 命令，请先安装 Python 并加入 PATH" -ForegroundColor Red
        exit 1
    }

    Write-Step "创建日志目录..."
    New-LogDir

    Write-Step "注册定时任务: $TaskName"

    # 如果已存在，先删除
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

    # 触发时间：每天 08:00
    $Trigger = New-ScheduledTaskTrigger -Daily -At "08:00"

    # 操作：运行 run.bat --headless
    $Exe = "cmd.exe"
    $Args = "/c ""$RunBat"" --headless"
    $Action = New-ScheduledTaskAction -Execute $Exe -Argument $Args -WorkingDirectory $ScriptDir

    # 无论用户是否登录都运行（不需要解锁屏幕）
    $Settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -WakeToRun

    Register-ScheduledTask `
        -TaskName $TaskName `
        -Trigger $Trigger `
        -Action $Action `
        -Settings $Settings `
        -Description "华南师范大学砺儒云课堂 - 每日作业提醒"

    Write-Host "`n[OK] 定时任务已安装！" -ForegroundColor Green
    Write-Host "  任务名称: $TaskName"
    Write-Host "  运行时间:  每天 08:00"
    Write-Host "  脚本路径:  $RunBat"
    Write-Host "`n  查看日志:  type '$StdoutLog'"
    Write-Host "  卸载任务:  .\setup_task.ps1 uninstall"
}

# ─── Uninstall ──────────────────────────────────────────────
function Uninstall-Task {
    Write-Step "卸载定时任务..."
    $t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($t) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "[OK] 定时任务已卸载" -ForegroundColor Green
    } else {
        Write-Host "[INFO] 未找到已安装的任务" -ForegroundColor Yellow
    }
}

# ─── Status ─────────────────────────────────────────────────
function Show-Status {
    Write-Step "定时任务状态："
    $t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($t) {
        $info = Get-ScheduledTaskInfo -TaskName $TaskName
        Write-Host "  任务名称: $TaskName"
        Write-Host "  状态:      $($t.State)"
        Write-Host "  上次运行:  $($info.LastRunTime)"
        Write-Host "  上次结果:  $($info.LastTaskResult)"
        Write-Host "  下次运行:  $($info.NextRunTime)"
    } else {
        Write-Host "  (未安装。运行 .\setup_task.ps1 install 安装)" -ForegroundColor Yellow
    }
    if (Test-Path $StdoutLog) {
        Write-Host "`n  最近日志（最后 8 行）："
        Get-Content $StdoutLog -Tail 8 | ForEach-Object { Write-Host "    $_" }
    }
}

# ─── Run Now ───────────────────────────────────────────────
function Run-Now {
    Write-Step "立即运行一次（同步等待）..."
    New-LogDir
    $t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($t) {
        Start-ScheduledTask -TaskName $TaskName
        Write-Host "[OK] 任务已触发，可在任务计划程序中查看进度"
        Write-Host "  或查看日志:  type '$StdoutLog'"
    } else {
        Write-Host "  [WARN] 任务未安装，直接运行 run.bat..." -ForegroundColor Yellow
        & "$RunBat" --headless
    }
}

# ─── Main ───────────────────────────────────────────────────
if ($Action -eq "") { $Action = Read-Host "选择操作 (install/uninstall/status/run)" }

switch ($Action.ToLower()) {
    "install"   { Install-Task }
    "uninstall" { Uninstall-Task }
    "status"    { Show-Status }
    "run"       { Run-Now }
    default     {
        Write-Host "用法: setup_task.ps1 {install|uninstall|status|run}" -ForegroundColor Yellow
        Write-Host "  install   - 安装定时任务（每天早8:00）"
        Write-Host "  uninstall - 卸载定时任务"
        Write-Host "  status    - 查看状态"
        Write-Host "  run       - 立即手动运行一次"
    }
}
