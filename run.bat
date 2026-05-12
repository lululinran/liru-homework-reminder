@echo off
REM 砺儒云课堂作业提醒 - Windows 完整运行脚本
REM 一键完成：抓取数据 + 生成报告 + 推送通知
REM
REM 用法：
REM   run.bat          - 正常模式（有头浏览器，首次运行用这个）
REM   run.bat --headless - 无头模式（定时任务用这个）

setlocal enabledelayedexpansion

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

set HEADLESS=
if "%1"=="--headless" (
    set HEADLESS=--headless
    echo [%date% %time%] 以无头模式运行...
) else (
    echo [%date% %time%] 以正常模式运行...
)

echo.
echo ==^> Step 1: 抓取作业数据...
python fetch.py --all %HEADLESS% -o data\assignments_raw.json
if errorlevel 1 (
    echo [ERROR] 抓取失败，请检查 Cookie 是否过期
    exit /b 1
)

echo.
echo ==^> Step 2: 生成报告 + 推送通知...
python report.py -i data\assignments_raw.json
if errorlevel 1 (
    echo [ERROR] 报告生成失败
    exit /b 1
)

echo.
echo [%date% %time%] 全部完成！
endlocal
