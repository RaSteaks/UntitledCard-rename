# 存储卡重命名工具

自动识别存储卡中的视频素材文件，提取卷号并重命名存储卡。

## 功能特性

- 自动扫描存储卡中的视频素材文件
- 支持多种视频格式：MXF, MOV, MP4, R3D, ARI, BRAW
- 从文件名中提取卷号（如 `A001C001_200101B6.MXF` → `A001`）
- 一键重命名存储卡
- 安全推出存储卡
- 跨平台支持：macOS / Windows

## 支持的文件命名格式

| 格式示例 | 提取的卷号 | 说明 |
|---------|-----------|------|
| A001C001_200101B6.MXF | A001 | Sony XDCAM |
| B002C015_240115AB.mov | B002 | ARRI |
| C003R001_123456.MP4 | C003 | 通用格式 |

命名规则：文件名以 **1个大写字母 + 3个数字** 开头（如 A001, B002, C003）

## 使用方法

### 方式一：运行 Python 脚本

```bash
python3 rename_card.py
```

### 方式二：运行打包后的应用程序

- **macOS**: 双击 `存储卡重命名工具.app`
- **Windows**: 双击 `存储卡重命名工具.exe`

## 操作流程

1. 插入存储卡
2. 启动程序
3. 从下拉框选择存储卡（默认选择 "Untitled"）
4. 点击 **分析存储卡** 按钮
5. 等待分析完成，查看检测到的卷号
6. 从卷号下拉框选择目标名称
7. 点击 **重命名** 执行重命名
8. 点击 **推出存储卡** 安全弹出

## 构建可执行文件

### 前提条件

```bash
pip install pyinstaller
```

### macOS 构建

```bash
pyinstaller --onefile --windowed --name "存储卡重命名工具" rename_card.py
```

生成的应用位于 `dist/存储卡重命名工具.app`

### Windows 构建

```cmd
pyinstaller --onefile --windowed --name "存储卡重命名工具" rename_card.py
```

生成的应用位于 `dist\存储卡重命名工具.exe`

## 系统要求

- **macOS**: macOS 10.14 或更高版本
- **Windows**: Windows 10 或更高版本
- **Python**: 3.7 或更高版本（仅源码运行需要）

## 注意事项

- Windows 上重命名需要管理员权限
- 确保存储卡未被其他程序占用
- 重命名后存储卡会保持挂载状态

## 许可证

MIT License
