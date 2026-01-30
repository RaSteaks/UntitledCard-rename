#!/usr/bin/env python3
"""
存储卡重命名工具 - macOS版本
读取外置存储卡，分析视频素材文件名，提取卷号并重命名存储卡
"""

import json
import os
import re
import subprocess
import threading
import queue
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from collections import defaultdict

# 配置文件路径
CONFIG_FILE = Path.home() / '.card_renamer_config.json'

# 视频文件扩展名
VIDEO_EXTENSIONS = {'.mxf', '.mov', '.mp4', '.r3d', '.ari', '.braw'}

# 工作流程步骤
STEPS = ['刷新', '分析', '重命名', '推出']


class CardRenamerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("存储卡重命名工具")
        self.root.geometry("600x580")
        self.root.resizable(False, False)
        
        # 状态变量
        self.video_files = []
        self.reel_numbers = set()
        self.selected_volume = tk.StringVar()
        self.selected_reel = tk.StringVar()
        self.volume_paths = {}
        self.current_step = 0
        
        # 加载配置（包含last_reel和reel_history）
        self.config = self.load_config()
        self.last_reel = self.config.get('last_reel', '')
        self.reel_history = set(self.config.get('reel_history', []))
        
        # 日志队列
        self.log_queue = queue.Queue()
        
        self.setup_ui()
        self.refresh_volumes()
        self.update_history_table()
        self.process_log_queue()
    
    def setup_ui(self):
        """设置UI界面"""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # ===== 步骤指示器 =====
        step_frame = ttk.Frame(main_frame)
        step_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.step_labels = []
        self.step_indicators = []
        
        for i, step in enumerate(STEPS):
            container = ttk.Frame(step_frame)
            container.pack(side=tk.LEFT, expand=True)
            
            indicator = tk.Label(container, text="○", font=("Arial", 16), fg="gray")
            indicator.pack()
            self.step_indicators.append(indicator)
            
            label = ttk.Label(container, text=step, font=("Arial", 10))
            label.pack()
            self.step_labels.append(label)
            
            if i < len(STEPS) - 1:
                line = ttk.Label(step_frame, text="───", foreground="gray")
                line.pack(side=tk.LEFT, expand=True)
        
        # ===== 存储卡选择 =====
        volume_frame = ttk.LabelFrame(main_frame, text="存储卡", padding="8")
        volume_frame.pack(fill=tk.X, pady=(0, 8))
        
        vol_row = ttk.Frame(volume_frame)
        vol_row.pack(fill=tk.X)
        
        ttk.Label(vol_row, text="选择:").pack(side=tk.LEFT, padx=(0, 5))
        self.volume_combo = ttk.Combobox(vol_row, textvariable=self.selected_volume, 
                                          state="readonly", width=28)
        self.volume_combo.pack(side=tk.LEFT, padx=(0, 8))
        self.volume_combo.bind("<<ComboboxSelected>>", self.on_volume_selected)
        
        self.refresh_btn = ttk.Button(vol_row, text="刷新列表", command=self.do_refresh, width=10)
        self.refresh_btn.pack(side=tk.LEFT)
        
        # ===== 分析结果 =====
        result_frame = ttk.LabelFrame(main_frame, text="分析结果", padding="8")
        result_frame.pack(fill=tk.X, pady=(0, 8))
        
        row1 = ttk.Frame(result_frame)
        row1.pack(fill=tk.X, pady=(0, 5))
        
        self.video_count_label = ttk.Label(row1, text="视频文件: -- 个")
        self.video_count_label.pack(side=tk.LEFT)
        
        self.analyze_btn = ttk.Button(row1, text="分析存储卡", command=self.do_analysis, width=12)
        self.analyze_btn.pack(side=tk.RIGHT)
        
        row2 = ttk.Frame(result_frame)
        row2.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(row2, text="检测到的卷号:").pack(side=tk.LEFT, padx=(0, 5))
        self.reel_combo = ttk.Combobox(row2, textvariable=self.selected_reel, 
                                        state="readonly", width=8)
        self.reel_combo.pack(side=tk.LEFT, padx=(0, 15))
        
        ttk.Label(row2, text="上次修改:").pack(side=tk.LEFT, padx=(0, 5))
        self.last_reel_label = ttk.Label(row2, text=self.last_reel or "--", 
                                          font=("Arial", 11, "bold"), foreground="#007AFF")
        self.last_reel_label.pack(side=tk.LEFT)
        
        # 重复警告标签
        self.warning_label = ttk.Label(row2, text="", foreground="#FF3B30", font=("Arial", 10))
        self.warning_label.pack(side=tk.RIGHT)
        
        # ===== 操作按钮 =====
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=(0, 8))
        
        self.rename_btn = ttk.Button(action_frame, text="重命名存储卡", 
                                      command=self.do_rename, width=18, state=tk.DISABLED)
        self.rename_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.eject_btn = ttk.Button(action_frame, text="推出存储卡", 
                                     command=self.do_eject, width=18, state=tk.DISABLED)
        self.eject_btn.pack(side=tk.LEFT)
        
        # ===== 卷号历史表格 =====
        history_frame = ttk.LabelFrame(main_frame, text="卷号历史记录", padding="8")
        history_frame.pack(fill=tk.X, pady=(0, 8))
        
        # 表格容器（带滚动条）
        table_container = ttk.Frame(history_frame)
        table_container.pack(fill=tk.X)
        
        # Canvas + 滚动条
        self.table_canvas = tk.Canvas(table_container, height=100, bg="white", 
                                       highlightthickness=1, highlightbackground="#ddd")
        
        # 垂直滚动条
        v_scrollbar = ttk.Scrollbar(table_container, orient=tk.VERTICAL, 
                                     command=self.table_canvas.yview)
        # 水平滚动条
        h_scrollbar = ttk.Scrollbar(history_frame, orient=tk.HORIZONTAL, 
                                     command=self.table_canvas.xview)
        
        self.table_canvas.configure(yscrollcommand=v_scrollbar.set, 
                                     xscrollcommand=h_scrollbar.set)
        
        self.table_canvas.pack(side=tk.LEFT, fill=tk.X, expand=True)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        h_scrollbar.pack(fill=tk.X)
        
        # 绑定鼠标滚轮
        self.table_canvas.bind('<MouseWheel>', self._on_canvas_scroll)
        self.table_canvas.bind('<Enter>', lambda e: self.table_canvas.focus_set())
        
        # 清除历史按钮
        btn_frame = ttk.Frame(history_frame)
        btn_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.clear_history_btn = ttk.Button(btn_frame, text="清除历史", 
                                             command=self.clear_history, width=10)
        self.clear_history_btn.pack(side=tk.RIGHT)
        
        self.history_count_label = ttk.Label(btn_frame, text="共 0 个卷号")
        self.history_count_label.pack(side=tk.LEFT)
        
        # ===== 工作日志 =====
        progress_frame = ttk.LabelFrame(main_frame, text="工作日志", padding="8")
        progress_frame.pack(fill=tk.X, pady=(0, 8))
        
        status_row = ttk.Frame(progress_frame)
        status_row.pack(fill=tk.X, pady=(0, 5))
        
        self.status_label = ttk.Label(status_row, text="就绪", font=("Arial", 11))
        self.status_label.pack(side=tk.LEFT)
        
        self.progress_bar = ttk.Progressbar(status_row, mode='indeterminate', length=150)
        self.progress_bar.pack(side=tk.RIGHT)
        
        # 固定高度100px的日志容器
        log_container = tk.Frame(progress_frame, height=100)
        log_container.pack(fill=tk.X)
        log_container.pack_propagate(False)  # 防止子控件改变容器大小
        
        self.log_text = tk.Text(log_container, state=tk.DISABLED, 
                                 font=("Monaco", 10), bg="#1e1e1e", fg="#d4d4d4",
                                 insertbackground="white")
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(log_container, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)
    
    def _on_canvas_scroll(self, event):
        """处理Canvas鼠标滚轮事件"""
        self.table_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    
    def update_history_table(self):
        """更新卷号历史表格"""
        self.table_canvas.delete("all")
        
        if not self.reel_history:
            self.table_canvas.create_text(280, 40, text="暂无历史记录", 
                                           fill="#999", font=("Arial", 12))
            self.history_count_label.config(text="共 0 个卷号")
            self.table_canvas.configure(scrollregion=(0, 0, 560, 80))
            return
        
        # 按字母分组并排序
        groups = defaultdict(list)
        for reel in self.reel_history:
            letter = reel[0]  # 首字母 A, B, C...
            groups[letter].append(reel)
        
        # 对每组内按数字排序
        for letter in groups:
            groups[letter].sort(key=lambda x: int(x[1:]))
        
        # 按字母ASCII顺序排列列
        sorted_letters = sorted(groups.keys())
        
        # 绘制表格
        col_width = 70
        row_height = 20
        padding = 10
        header_height = 25
        
        # 计算需要的尺寸
        canvas_width = len(sorted_letters) * col_width + padding * 2
        max_rows = max(len(v) for v in groups.values()) if groups else 0
        content_height = header_height + max_rows * row_height + 10
        
        # 绘制表头和数据
        for col_idx, letter in enumerate(sorted_letters):
            x = padding + col_idx * col_width + col_width // 2
            
            # 表头
            self.table_canvas.create_text(x, 12, text=letter, 
                                           font=("Arial", 12, "bold"), fill="#333")
            
            # 分隔线
            self.table_canvas.create_line(
                padding + col_idx * col_width, header_height,
                padding + (col_idx + 1) * col_width, header_height,
                fill="#ddd"
            )
            
            # 数据行
            for row_idx, reel in enumerate(groups[letter]):
                y = header_height + 5 + row_idx * row_height + row_height // 2
                self.table_canvas.create_text(x, y, text=reel, 
                                               font=("Monaco", 10), fill="#007AFF")
        
        # 更新计数
        self.history_count_label.config(text=f"共 {len(self.reel_history)} 个卷号")
        
        # 设置滚动区域（内容区域大小）
        self.table_canvas.configure(scrollregion=(0, 0, max(canvas_width, 560), content_height))
    
    def clear_history(self):
        """清除历史记录"""
        if not self.reel_history:
            return
        
        if messagebox.askyesno("确认", "确定要清除所有卷号历史记录吗？"):
            self.reel_history.clear()
            self.save_config()
            self.update_history_table()
            self.log("已清除卷号历史记录")
    
    def check_reel_duplicate(self, reel):
        """检查卷号是否已存在于历史中"""
        return reel in self.reel_history
    
    def add_reel_to_history(self, reel):
        """添加卷号到历史记录"""
        self.reel_history.add(reel)
        self.save_config()
        self.update_history_table()
    
    def set_step(self, step_index, status='active'):
        """设置步骤状态"""
        for i, (indicator, label) in enumerate(zip(self.step_indicators, self.step_labels)):
            if i < step_index:
                indicator.config(text="●", fg="#34C759")
            elif i == step_index:
                if status == 'active':
                    indicator.config(text="◉", fg="#007AFF")
                elif status == 'done':
                    indicator.config(text="●", fg="#34C759")
                elif status == 'error':
                    indicator.config(text="●", fg="#FF3B30")
            else:
                indicator.config(text="○", fg="gray")
        
        self.current_step = step_index
    
    def set_status(self, text, busy=False):
        """设置状态栏"""
        self.status_label.config(text=text)
        if busy:
            self.progress_bar.start(10)
        else:
            self.progress_bar.stop()
    
    def process_log_queue(self):
        """处理日志队列"""
        messages = []
        try:
            while True:
                messages.append(self.log_queue.get_nowait())
        except queue.Empty:
            pass
        
        if messages:
            self.log_text.config(state=tk.NORMAL)
            for msg in messages:
                self.log_text.insert(tk.END, msg + "\n")
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)
        
        self.root.after(100, self.process_log_queue)
    
    def log(self, message):
        """线程安全日志"""
        self.log_queue.put(message)
    
    def clear_log(self):
        """清空日志"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)
    
    def load_config(self):
        """加载配置"""
        try:
            if CONFIG_FILE.exists():
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}
    
    def save_config(self):
        """保存配置"""
        try:
            self.config['last_reel'] = self.last_reel
            self.config['reel_history'] = list(self.reel_history)
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    
    def save_last_reel(self, reel):
        """保存上一个卷号"""
        self.last_reel = reel
        self.last_reel_label.config(text=reel)
        self.save_config()
    
    def get_disk_identifier(self, volume_name):
        """获取磁盘标识符"""
        try:
            result = subprocess.run(
                ['diskutil', 'info', f'/Volumes/{volume_name}'],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'Device Identifier:' in line:
                        return line.split(':')[1].strip()
        except Exception:
            pass
        return None
    
    # ===== 步骤1: 刷新 =====
    def do_refresh(self):
        """刷新存储卷列表"""
        self.set_step(0, 'active')
        self.set_status("正在刷新...", busy=True)
        self.refresh_btn.config(state=tk.DISABLED)
        
        threading.Thread(target=self._refresh_volumes, daemon=True).start()
    
    def _refresh_volumes(self):
        """后台刷新"""
        self.volume_paths = {}
        
        try:
            for item in Path("/Volumes").iterdir():
                if item.is_dir() and item.name != "Macintosh HD":
                    self.volume_paths[item.name] = str(item)
        except Exception as e:
            self.log(f"刷新错误: {e}")
        
        volumes = list(self.volume_paths.keys())
        
        def update_ui():
            self.volume_combo['values'] = volumes
            if volumes:
                untitled = [v for v in volumes if "Untitled" in v]
                self.selected_volume.set(untitled[0] if untitled else volumes[0])
            
            self.log(f"发现 {len(volumes)} 个存储卷")
            self.set_step(0, 'done')
            self.set_status("刷新完成", busy=False)
            self.refresh_btn.config(state=tk.NORMAL)
        
        self.root.after(0, update_ui)
    
    def refresh_volumes(self):
        """初始刷新"""
        self.volume_paths = {}
        try:
            for item in Path("/Volumes").iterdir():
                if item.is_dir() and item.name != "Macintosh HD":
                    self.volume_paths[item.name] = str(item)
        except Exception:
            pass
        
        volumes = list(self.volume_paths.keys())
        self.volume_combo['values'] = volumes
        if volumes:
            untitled = [v for v in volumes if "Untitled" in v]
            self.selected_volume.set(untitled[0] if untitled else volumes[0])
        self.set_step(0, 'done')
    
    def on_volume_selected(self, event=None):
        """存储卡选择变更"""
        self.video_files = []
        self.reel_numbers = set()
        self.reel_combo['values'] = []
        self.selected_reel.set("")
        self.video_count_label.config(text="视频文件: -- 个")
        self.rename_btn.config(state=tk.DISABLED)
        self.eject_btn.config(state=tk.DISABLED)
        self.warning_label.config(text="")
        for i in range(1, len(STEPS)):
            self.step_indicators[i].config(text="○", fg="gray")
    
    # ===== 步骤2: 分析 =====
    def do_analysis(self):
        """开始分析"""
        if not self.selected_volume.get():
            messagebox.showwarning("警告", "请先选择存储卡")
            return
        
        self.set_step(1, 'active')
        self.set_status("正在分析...", busy=True)
        self.analyze_btn.config(state=tk.DISABLED)
        self.warning_label.config(text="")
        self.clear_log()
        
        threading.Thread(target=self._analyze_volume, daemon=True).start()
    
    def _analyze_volume(self):
        """后台分析"""
        volume_name = self.selected_volume.get()
        volume_path = Path(f"/Volumes/{volume_name}")
        
        self.log(f"分析: {volume_name}")
        
        self.video_files = []
        reel_pattern = re.compile(r'^([A-Z]\d{3})')
        self.reel_numbers = set()
        
        try:
            for root, _, files in os.walk(volume_path):
                for file in files:
                    if Path(file).suffix.lower() in VIDEO_EXTENSIONS:
                        self.video_files.append(file)
                        match = reel_pattern.match(file)
                        if match:
                            self.reel_numbers.add(match.group(1))
        except PermissionError:
            self.log("警告: 部分目录无权限")
        except Exception as e:
            self.log(f"错误: {e}")
        
        count = len(self.video_files)
        self.log(f"找到 {count} 个视频文件")
        
        # 检查重复
        duplicates = self.reel_numbers & self.reel_history
        
        def update_ui():
            self.video_count_label.config(text=f"视频文件: {count} 个")
            
            if self.reel_numbers:
                sorted_reels = sorted(self.reel_numbers)
                self.log(f"卷号: {', '.join(sorted_reels)}")
                self.reel_combo['values'] = sorted_reels
                self.selected_reel.set(sorted_reels[0])
                
                # 显示重复警告
                if duplicates:
                    dup_str = ', '.join(sorted(duplicates))
                    self.warning_label.config(text=f"⚠️ 已存在: {dup_str}")
                    self.log(f"警告: 卷号已存在于历史记录中: {dup_str}")
                    # 仍然允许操作，但给予警告
                    self.rename_btn.config(state=tk.NORMAL)
                    self.eject_btn.config(state=tk.NORMAL)
                else:
                    self.warning_label.config(text="")
                    self.rename_btn.config(state=tk.NORMAL)
                    self.eject_btn.config(state=tk.NORMAL)
                
                self.set_step(1, 'done')
                self.set_status("分析完成", busy=False)
            else:
                self.log("未能提取卷号")
                if self.video_files:
                    self.log(f"示例: {self.video_files[0]}")
                self.set_step(1, 'error')
                self.set_status("未找到卷号", busy=False)
            
            self.analyze_btn.config(state=tk.NORMAL)
        
        self.root.after(0, update_ui)
    
    # ===== 步骤3: 重命名 =====
    def do_rename(self):
        """开始重命名"""
        old_name = self.selected_volume.get()
        new_name = self.selected_reel.get()
        
        if not old_name or not new_name:
            messagebox.showwarning("警告", "请先选择存储卡和卷号")
            return
        
        if old_name == new_name:
            messagebox.showinfo("提示", "名称相同")
            return
        
        # 检查是否重复
        if self.check_reel_duplicate(new_name):
            if not messagebox.askyesno("警告", 
                f"卷号 '{new_name}' 已存在于历史记录中！\n\n继续重命名可能导致卷号冲突。\n确定要继续吗？"):
                return
        
        if not messagebox.askyesno("确认", f"将 '{old_name}' 重命名为 '{new_name}'?"):
            return
        
        self.set_step(2, 'active')
        self.set_status("正在重命名...", busy=True)
        self.rename_btn.config(state=tk.DISABLED)
        
        threading.Thread(target=lambda: self._do_rename(old_name, new_name), daemon=True).start()
    
    def _do_rename(self, old_name, new_name):
        """执行重命名"""
        self.log(f"重命名: {old_name} -> {new_name}")
        
        success = False
        error_msg = ""
        
        try:
            volume_path = f"/Volumes/{old_name}"
            result = subprocess.run(
                ['diskutil', 'rename', volume_path, new_name],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode == 0:
                success = True
            else:
                disk_id = self.get_disk_identifier(old_name)
                if disk_id:
                    self.log(f"尝试: {disk_id}")
                    result2 = subprocess.run(
                        ['diskutil', 'rename', disk_id, new_name],
                        capture_output=True, text=True, timeout=30
                    )
                    success = result2.returncode == 0
                    error_msg = result2.stderr if not success else ""
                else:
                    error_msg = result.stderr or "未知错误"
                    
        except subprocess.TimeoutExpired:
            error_msg = "操作超时"
        except Exception as e:
            error_msg = str(e)
        
        def update_ui():
            if success:
                self.log("重命名成功!")
                self.save_last_reel(new_name)
                # 添加到历史记录
                self.add_reel_to_history(new_name)
                self.log(f"已添加 {new_name} 到历史记录")
                
                self.refresh_volumes()
                if new_name in self.volume_paths:
                    self.selected_volume.set(new_name)
                self.set_step(2, 'done')
                self.set_status("重命名完成", busy=False)
                self.warning_label.config(text="")
                messagebox.showinfo("成功", f"已重命名为 '{new_name}'")
            else:
                self.log(f"失败: {error_msg}")
                self.set_step(2, 'error')
                self.set_status("重命名失败", busy=False)
                messagebox.showerror("错误", f"重命名失败:\n{error_msg}")
            
            self.rename_btn.config(state=tk.NORMAL)
        
        self.root.after(0, update_ui)
    
    # ===== 步骤4: 推出 =====
    def do_eject(self):
        """开始推出"""
        volume_name = self.selected_volume.get()
        if not messagebox.askyesno("确认", f"推出 '{volume_name}'?"):
            return
        
        self.set_step(3, 'active')
        self.set_status("正在推出...", busy=True)
        self.eject_btn.config(state=tk.DISABLED)
        
        threading.Thread(target=lambda: self._do_eject(volume_name), daemon=True).start()
    
    def _do_eject(self, volume_name):
        """执行推出"""
        self.log(f"推出: {volume_name}")
        
        success = False
        error_msg = ""
        
        try:
            result = subprocess.run(
                ['diskutil', 'eject', f'/Volumes/{volume_name}'],
                capture_output=True, text=True, timeout=30
            )
            success = result.returncode == 0
            error_msg = result.stderr
        except subprocess.TimeoutExpired:
            error_msg = "操作超时"
        except Exception as e:
            error_msg = str(e)
        
        def update_ui():
            if success:
                self.log("推出成功!")
                self.set_step(3, 'done')
                self.set_status("已推出", busy=False)
                self.refresh_volumes()
                self.on_volume_selected()
                messagebox.showinfo("成功", "存储卡已安全推出")
            else:
                self.log(f"失败: {error_msg}")
                self.set_step(3, 'error')
                self.set_status("推出失败", busy=False)
                messagebox.showerror("错误", f"推出失败:\n{error_msg}")
            
            self.eject_btn.config(state=tk.NORMAL)
        
        self.root.after(0, update_ui)


def main():
    root = tk.Tk()
    CardRenamerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
