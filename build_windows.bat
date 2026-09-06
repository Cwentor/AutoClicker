@echo off
rem 一键打包 Windows 可执行文件
rem 用法：双击运行，或在命令行中执行 build_windows.bat
chcp 65001 >nul
cd /d "%~dp0"

echo ==========================================
echo   鼠标连点器 - Windows 打包脚本
echo ==========================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3.9+ 并勾选 "Add to PATH"。
    echo        下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [1/4] 创建/复用虚拟环境 .venv ...
if not exist .venv (
    python -m venv .venv
    if errorlevel 1 (
        echo [错误] 创建虚拟环境失败。
        pause
        exit /b 1
    )
)
call .venv\Scripts\activate.bat

echo [2/4] 安装依赖 ...
python -m pip install --upgrade pip -q
pip install -r requirements.txt -r requirements-dev.txt -q
if errorlevel 1 (
    echo [错误] 依赖安装失败，请检查网络连接。
    pause
    exit /b 1
)

echo [3/4] 清理旧的打包产物 ...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [4/4] 开始打包 ...
pyinstaller auto_clicker.spec --noconfirm
if errorlevel 1 (
    echo [错误] 打包失败，请查看上方日志。
    pause
    exit /b 1
)

echo.
echo ==========================================
echo   打包完成！可执行文件位于 dist\AutoClicker.exe
echo ==========================================
pause
