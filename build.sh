#!/bin/bash
# 存储卡重命名工具 - macOS 打包脚本

echo "开始打包存储卡重命名工具..."

# 检查 pyinstaller 是否安装
if ! command -v pyinstaller &> /dev/null; then
    echo "PyInstaller 未安装，正在安装..."
    pip3 install pyinstaller
fi

# 清理旧的构建文件
rm -rf build dist

# 打包为 macOS .app（使用 onedir 模式）
pyinstaller --windowed --name "存储卡重命名工具" rename_card.py

echo "打包完成！"
echo "应用位置: dist/存储卡重命名工具.app"
echo ""
echo "你可以直接双击运行 dist/存储卡重命名工具.app"
