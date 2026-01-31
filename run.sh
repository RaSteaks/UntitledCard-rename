#!/bin/bash
# 存储卡重命名工具 - 启动脚本
# 优先使用 Homebrew Python 3.13（已安装 tkinter），备用 conda Python

cd "$(dirname "$0")"

# 优先使用 Homebrew Python（如果可用）
if [ -f "/opt/homebrew/bin/python3.13" ]; then
    /opt/homebrew/bin/python3.13 rename_card.py
else
    # 备用：使用 conda 的 python3
    python3 rename_card.py
fi
