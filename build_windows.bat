@echo off
REM Windows构建脚本 - 存储卡重命名工具
REM 请在Windows系统上运行此脚本

echo 正在检查 Python...
python --version
if errorlevel 1 (
    echo 错误: 未找到 Python，请先安装 Python 3.7+
    pause
    exit /b 1
)

echo 正在检查 PyInstaller...
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo 正在安装 PyInstaller...
    pip install pyinstaller
)

echo 正在构建应用程序...
pyinstaller --onefile --windowed --name "存储卡重命名工具" rename_card.py

echo.
echo 构建完成！
echo 应用程序位于: dist\存储卡重命名工具.exe
pause
