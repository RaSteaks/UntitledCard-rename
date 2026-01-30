#!/usr/bin/env python3
"""
存储卡重命名工具 - GUI版本 (跨平台)
读取名为"Untitled"的外置硬盘，分析视频素材文件名，提取卷号并重命名存储卡
支持 macOS 和 Windows
"""

import os
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

# 检测操作系统
IS_MACOS = sys.platform == 'darwin'
IS_WINDOWS = sys.platform == 'win32'


class CardRenamerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("存储卡重命名工具")
        self.root.geometry("500x450")
        self.root.resizable(False, False)
        
        # 状态变量
        self.video_files = []
        self.reel_numbers = set()
        self.selected_volume = tk.StringVar()
        self.selected_reel = tk.StringVar()
        self.volume_paths = {}  # 存储卷名到路径的映射
        
        self.setup_ui()
        self.refresh_volumes()
    
    def setup_ui(self):
        """设置UI界面"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 存储卡选择区域
        volume_frame = ttk.LabelFrame(main_frame, text="存储卡选择", padding="5")
        volume_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(volume_frame, text="选择存储卡:").pack(side=tk.LEFT, padx=(0, 5))
        self.volume_combo = ttk.Combobox(volume_frame, textvariable=self.selected_volume, 
                                          state="readonly", width=25)
        self.volume_combo.pack(side=tk.LEFT, padx=(0, 5))
        self.volume_combo.bind("<<ComboboxSelected>>", self.on_volume_selected)
        
        ttk.Button(volume_frame, text="刷新", command=self.refresh_volumes, width=8).pack(side=tk.LEFT)
        
        # 分析结果区域
        result_frame = ttk.LabelFrame(main_frame, text="分析结果", padding="5")
        result_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 视频文件数量
        self.video_count_label = ttk.Label(result_frame, text="视频文件: 0 个")
        self.video_count_label.pack(anchor=tk.W)
        
        # 卷号选择
        reel_frame = ttk.Frame(result_frame)
        reel_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Label(reel_frame, text="检测到的卷号:").pack(side=tk.LEFT, padx=(0, 5))
        self.reel_combo = ttk.Combobox(reel_frame, textvariable=self.selected_reel, 
                                        state="readonly", width=10)
        self.reel_combo.pack(side=tk.LEFT)
        
        # 进度显示区域
        progress_frame = ttk.LabelFrame(main_frame, text="工作进度", padding="5")
        progress_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # 进度条
        self.progress_bar = ttk.Progressbar(progress_frame, mode='indeterminate')
        self.progress_bar.pack(fill=tk.X, pady=(0, 5))
        
        # 日志显示
        font_name = "Monaco" if IS_MACOS else "Consolas"
        self.log_text = tk.Text(progress_frame, height=10, state=tk.DISABLED, 
                                 font=(font_name, 10))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # 滚动条
        scrollbar = ttk.Scrollbar(self.log_text, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)
        
        # 操作按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        self.analyze_btn = ttk.Button(button_frame, text="分析存储卡", 
                                       command=self.start_analysis, width=15)
        self.analyze_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.rename_btn = ttk.Button(button_frame, text="重命名", 
                                      command=self.rename_card, width=15, state=tk.DISABLED)
        self.rename_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.eject_btn = ttk.Button(button_frame, text="推出存储卡", 
                                     command=self.eject_card, width=15, state=tk.DISABLED)
        self.eject_btn.pack(side=tk.LEFT)
    
    def log(self, message):
        """添加日志消息"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.root.update_idletasks()
    
    def clear_log(self):
        """清空日志"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
    
    def get_removable_drives_windows(self):
        """获取Windows上的可移动驱动器"""
        drives = {}
        try:
            result = subprocess.run(
                ['wmic', 'logicaldisk', 'where', 'drivetype=2', 'get', 'deviceid,volumename'],
                capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW
            )
            lines = result.stdout.strip().split('\n')[1:]  # 跳过标题行
            for line in lines:
                parts = line.strip().split()
                if parts:
                    drive_letter = parts[0]
                    volume_name = ' '.join(parts[1:]) if len(parts) > 1 else drive_letter
                    display_name = f"{volume_name} ({drive_letter})" if volume_name != drive_letter else drive_letter
                    drives[display_name] = drive_letter
        except Exception:
            # 备用方法：列出所有驱动器
            import string
            for letter in string.ascii_uppercase:
                drive = f"{letter}:\\"
                if os.path.exists(drive) and letter not in ['C']:
                    drives[f"{letter}:"] = f"{letter}:"
        return drives
    
    def refresh_volumes(self):
        """刷新已挂载的存储卷列表"""
        self.volume_paths = {}
        
        if IS_MACOS:
            for item in Path("/Volumes").iterdir():
                if item.is_dir() and item.name != "Macintosh HD":
                    self.volume_paths[item.name] = str(item)
        elif IS_WINDOWS:
            self.volume_paths = self.get_removable_drives_windows()
        
        volumes = list(self.volume_paths.keys())
        self.volume_combo['values'] = volumes
        
        if volumes:
            # 优先选择"Untitled"
            untitled_match = [v for v in volumes if "Untitled" in v]
            if untitled_match:
                self.selected_volume.set(untitled_match[0])
            else:
                self.selected_volume.set(volumes[0])
        
        self.log("已刷新存储卷列表")
    
    def on_volume_selected(self, event=None):
        """存储卡选择变更时的回调"""
        self.video_files = []
        self.reel_numbers = set()
        self.reel_combo['values'] = []
        self.selected_reel.set("")
        self.video_count_label.config(text="视频文件: 0 个")
        self.rename_btn.config(state=tk.DISABLED)
        self.eject_btn.config(state=tk.DISABLED)
    
    def start_analysis(self):
        """开始分析存储卡（在后台线程中执行）"""
        if not self.selected_volume.get():
            messagebox.showwarning("警告", "请先选择一个存储卡")
            return
        
        self.analyze_btn.config(state=tk.DISABLED)
        self.progress_bar.start()
        self.clear_log()
        
        # 在后台线程中执行分析
        thread = threading.Thread(target=self.analyze_volume, daemon=True)
        thread.start()
    
    def analyze_volume(self):
        """分析存储卡内容"""
        volume_name = self.selected_volume.get()
        
        if IS_MACOS:
            volume_path = Path(f"/Volumes/{volume_name}")
        else:
            volume_path = Path(self.volume_paths.get(volume_name, volume_name))
        
        self.log(f"正在分析存储卡: {volume_name}")
        self.log(f"路径: {volume_path}")
        self.log("搜索视频文件中...")
        
        # 查找视频文件
        video_extensions = {'.mxf', '.MXF', '.mov', '.MOV', '.mp4', '.MP4', 
                           '.r3d', '.R3D', '.ari', '.ARI', '.braw', '.BRAW'}
        self.video_files = []
        
        file_count = 0
        try:
            for root, dirs, files in os.walk(volume_path):
                for file in files:
                    if Path(file).suffix in video_extensions:
                        self.video_files.append(file)
                        file_count += 1
                        if file_count % 100 == 0:
                            self.log(f"已找到 {file_count} 个视频文件...")
        except PermissionError:
            self.log("警告: 部分目录无访问权限")
        
        self.log(f"搜索完成，共找到 {len(self.video_files)} 个视频文件")
        
        # 更新UI
        self.root.after(0, lambda: self.video_count_label.config(
            text=f"视频文件: {len(self.video_files)} 个"))
        
        if not self.video_files:
            self.log("未找到视频素材文件")
            self.root.after(0, self.analysis_complete)
            return
        
        # 提取卷号
        self.log("正在提取卷号...")
        reel_pattern = re.compile(r'^([A-Z]\d{3})')
        self.reel_numbers = set()
        
        for filename in self.video_files:
            match = reel_pattern.match(filename)
            if match:
                self.reel_numbers.add(match.group(1))
        
        if self.reel_numbers:
            sorted_reels = sorted(self.reel_numbers)
            self.log(f"提取到的卷号: {', '.join(sorted_reels)}")
            
            # 更新卷号下拉框
            self.root.after(0, lambda: self.update_reel_combo(sorted_reels))
        else:
            self.log("无法从文件名中提取卷号")
            self.log("示例文件名:")
            for f in self.video_files[:3]:
                self.log(f"  - {f}")
        
        self.root.after(0, self.analysis_complete)
    
    def update_reel_combo(self, reels):
        """更新卷号下拉框"""
        self.reel_combo['values'] = reels
        if reels:
            self.selected_reel.set(reels[0])
            self.rename_btn.config(state=tk.NORMAL)
            self.eject_btn.config(state=tk.NORMAL)
    
    def analysis_complete(self):
        """分析完成后的清理工作"""
        self.progress_bar.stop()
        self.analyze_btn.config(state=tk.NORMAL)
        self.log("分析完成")
    
    def rename_card(self):
        """重命名存储卡"""
        old_name = self.selected_volume.get()
        new_name = self.selected_reel.get()
        
        if not old_name or not new_name:
            messagebox.showwarning("警告", "请先选择存储卡和目标卷号")
            return
        
        if old_name == new_name:
            messagebox.showinfo("提示", "存储卡名称与目标卷号相同，无需重命名")
            return
        
        # 确认对话框
        if not messagebox.askyesno("确认", 
            f"确定要将存储卡从\n'{old_name}'\n重命名为\n'{new_name}'\n吗?"):
            return
        
        self.log(f"正在重命名: {old_name} -> {new_name}")
        self.progress_bar.start()
        
        try:
            if IS_MACOS:
                result = subprocess.run(
                    ['diskutil', 'rename', old_name, new_name],
                    capture_output=True, text=True
                )
                success = result.returncode == 0
                error_msg = result.stderr
            elif IS_WINDOWS:
                drive_letter = self.volume_paths.get(old_name, old_name).rstrip('\\')
                result = subprocess.run(
                    ['label', drive_letter, new_name],
                    capture_output=True, text=True, shell=True
                )
                success = result.returncode == 0
                error_msg = result.stderr
            else:
                success = False
                error_msg = "不支持的操作系统"
            
            if success:
                self.log("重命名成功!")
                self.refresh_volumes()
                messagebox.showinfo("成功", f"存储卡已重命名为 '{new_name}'")
            else:
                self.log(f"重命名失败: {error_msg}")
                messagebox.showerror("错误", f"重命名失败:\n{error_msg}")
        except Exception as e:
            self.log(f"重命名时发生错误: {e}")
            messagebox.showerror("错误", f"重命名时发生错误:\n{e}")
        finally:
            self.progress_bar.stop()
    
    def eject_card(self):
        """推出存储卡"""
        volume_name = self.selected_volume.get()
        
        if not messagebox.askyesno("确认", f"确定要推出存储卡 '{volume_name}' 吗?"):
            return
        
        self.log(f"正在推出存储卡: {volume_name}")
        
        try:
            if IS_MACOS:
                result = subprocess.run(
                    ['diskutil', 'eject', f'/Volumes/{volume_name}'],
                    capture_output=True, text=True
                )
                success = result.returncode == 0
                error_msg = result.stderr
            elif IS_WINDOWS:
                drive_letter = self.volume_paths.get(volume_name, volume_name).rstrip('\\')
                # 使用 PowerShell 安全弹出
                ps_cmd = f"$vol = Get-WmiObject -Class Win32_Volume | Where-Object {{ $_.DriveLetter -eq '{drive_letter}' }}; $vol.Dismount($false, $false)"
                result = subprocess.run(
                    ['powershell', '-Command', ps_cmd],
                    capture_output=True, text=True
                )
                success = result.returncode == 0
                error_msg = result.stderr
            else:
                success = False
                error_msg = "不支持的操作系统"
            
            if success:
                self.log("存储卡已推出")
                self.refresh_volumes()
                self.on_volume_selected()
                messagebox.showinfo("成功", "存储卡已安全推出")
            else:
                self.log(f"推出失败: {error_msg}")
                messagebox.showerror("错误", f"推出失败:\n{error_msg}")
        except Exception as e:
            self.log(f"推出时发生错误: {e}")
            messagebox.showerror("错误", f"推出时发生错误:\n{e}")


def main():
    root = tk.Tk()
    app = CardRenamerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
