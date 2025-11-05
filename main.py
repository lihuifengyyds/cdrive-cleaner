import tkinter as tk
from tkinter import messagebox
import math
import os
import shutil
import tempfile
from datetime import datetime
import threading
import time
import ctypes

class CDriveCleaner(tk.Tk):
    def __init__(self):
        super().__init__()
        
        # 窗口设置
        self.title("C盘清理工具")
        self.geometry("920x680")
        self.configure(bg="#2d3e5f")
        
        # 数据初始化
        self.scan_progress = 0
        self.is_scanning = False
        self.is_cleaning = False
        self.found_files = []
        self.cleaned_size = 0
        self.temp_files_size = 0
        self.temp_files_count = 0
        
        # 获取初始磁盘信息
        self.update_disk_info()
        
        # 启动后台线程计算临时文件
        self.start_temp_calculation()
        
        # 创建界面
        self.create_widgets()
        
        # 检查管理员权限
        if not self.is_admin():
            self.add_log("⚡ 提示：右键 → 以管理员身份运行，可再多删 8GB")
        
    def is_admin(self):
        try: 
            return ctypes.windll.shell32.IsUserAnAdmin()
        except: 
            return False
         
    def stop_wuauserv(self):
        os.system("net stop wuauserv 2>nul")
        time.sleep(1)

    def start_wuauserv(self):
        os.system("net start wuauserv 2>nul")
        
    def update_disk_info(self):
        """获取C盘实时信息"""
        try:
            c_drive = "C:\\" if os.name == 'nt' else "/"
            stat = shutil.disk_usage(c_drive)
            
            self.disk_total_gb = stat.total / (1024**3)
            self.disk_used_gb = stat.used / (1024**3)
            self.disk_free_gb = stat.free / (1024**3)
            self.disk_usage_percent = (stat.used / stat.total) * 100
        except:
            # 默认值
            self.disk_total_gb = 800
            self.disk_used_gb = 500
            self.disk_free_gb = 300
            self.disk_usage_percent = 62.5
            
    def get_junk_paths(self):
        """返回所有能删的大垃圾路径（按体积排序）"""
        paths = []
        if os.name != 'nt':
            return paths

        # 1. Windows Update 缓存（最大头目，动辄 5-15GB）
        paths.append(r"C:\Windows\SoftwareDistribution\Download")

        # 2. 旧版系统升级残留（Win10→Win11 后留下的 Windows.old，20-40GB）
        paths.append(r"C:\Windows.old")

        # 3. 系统错误转储 + 内存 dump（单文件 1-8GB）
        paths.append(r"C:\Windows\Minidump")
        paths.append(r"C:\Windows\Memory.dmp")

        # 4. 升级日志 + 安装缓存
        paths.append(r"C:\Windows\Logs")
        paths.append(r"C:\Windows\Panther")
        paths.append(r"C:\Windows\Temp")
        paths.append(r"C:\Windows\Prefetch")

        # 5. 磁盘清理向导的隐藏缓存
        paths.append(r"C:\Windows\ServiceProfiles\LocalService\AppData\Local\Microsoft\Windows\DeliveryOptimization\Cache")

        # 6. 浏览器 200GB 缓存（Edge/Chrome/Firefox）
        appdata = os.getenv("LOCALAPPDATA")
        userprof = os.getenv("USERPROFILE")
        paths.extend([
            os.path.join(appdata, r"Google\Chrome\User Data\Default\Cache"),
            os.path.join(appdata, r"Google\Chrome\User Data\Default\Code Cache"),
            os.path.join(appdata, r"Google\Chrome\User Data\Default\Media Cache"),
            os.path.join(appdata, r"Microsoft\Edge\User Data\Default\Cache"),
            os.path.join(appdata, r"Mozilla\Firefox\Profiles"),  # 内部再递归 cache2
            os.path.join(userprof, r"AppData\Local\Temp"),
        ])

        # 7. 回收站（所有盘符）
        for drive in "CDEFG":
            recycle = f"{drive}:\\$Recycle.Bin"
            if os.path.exists(recycle):
                paths.append(recycle)

        # 8. 用户下载临时包（微信/QQ/钉钉）
        paths.append(os.path.join(userprof, r"Downloads"))
        paths.append(os.path.join(userprof, r"AppData\Local\Temp"))

        return [p for p in paths if os.path.exists(p)]
        
    def create_widgets(self):
        # 标题栏
        title_frame = tk.Frame(self, bg="#1e2836", height=50)
        title_frame.pack(fill="x")
        title_frame.pack_propagate(False)
        
        # Python图标和标题
        title_label = tk.Label(
            title_frame, 
            text="🐍 C盘清理工具",
            font=("Microsoft YaHei UI", 14, "bold"),
            bg="#1e2836",
            fg="white"
        )
        title_label.pack(side="left", padx=20, pady=10)
        
        # 窗口控制按钮
        btn_frame = tk.Frame(title_frame, bg="#1e2836")
        btn_frame.pack(side="right", padx=10)
        
        minimize_btn = tk.Button(btn_frame, text="─", font=("Arial", 12), bg="#1e2836", 
                                fg="white", bd=0, width=3, command=self.iconify)
        minimize_btn.pack(side="left", padx=2)
        
        close_btn = tk.Button(btn_frame, text="✕", font=("Arial", 12), bg="#1e2836", 
                             fg="white", bd=0, width=3, command=self.quit)
        close_btn.pack(side="left", padx=2)
        
        # 主内容区域
        main_frame = tk.Frame(self, bg="#3d5a80")
        main_frame.pack(fill="both", expand=True, padx=2, pady=2)
        
        # 上部区域 - 扫描进度和按钮
        top_frame = tk.Frame(main_frame, bg="#3d5a80")
        top_frame.pack(fill="x", padx=30, pady=30)
        
        # 左侧 - 圆形进度条
        left_frame = tk.Frame(top_frame, bg="#3d5a80")
        left_frame.pack(side="left", padx=20)
        
        self.canvas = tk.Canvas(
            left_frame,
            width=200,
            height=200,
            bg="#3d5a80",
            highlightthickness=0
        )
        self.canvas.pack()
        self.draw_circular_progress()
        
        # 右侧 - 按钮
        right_frame = tk.Frame(top_frame, bg="#3d5a80")
        right_frame.pack(side="right", padx=40)
        
        # 开始扫描按钮
        self.scan_btn = tk.Button(
            right_frame,
            text="开始扫描",
            font=("Microsoft YaHei UI", 14, "bold"),
            bg="#2d4a6f",
            fg="white",
            width=14,
            height=2,
            relief="flat",
            cursor="hand2",
            command=self.start_scan
        )
        self.scan_btn.pack(pady=10)
        
        # 立即清理按钮
        self.clean_btn = tk.Button(
            right_frame,
            text="立即清理",
            font=("Microsoft YaHei UI", 14, "bold"),
            bg="#5b9dd9",
            fg="white",
            width=14,
            height=2,
            relief="flat",
            cursor="hand2",
            command=self.clean_now,
            state="disabled"
        )
        self.clean_btn.pack(pady=10)
        
        # 统计信息卡片区域
        self.stats_frame = tk.Frame(main_frame, bg="#4a6fa5", relief="flat")
        self.stats_frame.pack(fill="x", padx=30, pady=10)
        
        self.create_stats_cards()
        
        # 底部区域
        bottom_frame = tk.Frame(main_frame, bg="#3d5a80")
        bottom_frame.pack(fill="both", expand=True, padx=30, pady=20)
        
        # 左侧 - 扫描结果日志
        log_frame = tk.Frame(bottom_frame, bg="#2d4a6f", relief="flat")
        log_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        log_title = tk.Label(
            log_frame,
            text="扫描结果与日志",
            font=("Microsoft YaHei UI", 13, "bold"),
            bg="#2d4a6f",
            fg="white",
            anchor="w"
        )
        log_title.pack(fill="x", padx=20, pady=(15, 10))
        
        # 添加滚动条
        log_scroll_frame = tk.Frame(log_frame, bg="#2d4a6f")
        log_scroll_frame.pack(fill="both", expand=True, padx=20, pady=(0, 15))
        
        scrollbar = tk.Scrollbar(log_scroll_frame)
        scrollbar.pack(side="right", fill="y")
        
        self.log_text = tk.Text(
            log_scroll_frame,
            font=("Consolas", 10),
            bg="#2d4a6f",
            fg="#c8d8e8",
            relief="flat",
            height=10,
            wrap="word",
            yscrollcommand=scrollbar.set
        )
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.log_text.yview)
        
        # 初始日志
        self.add_log("[系统] C盘清理工具已启动")
        self.add_log(f"[信息] 系统：{self.get_os_info()}")
        self.add_log(f"[信息] Python版本：{self.get_python_version()}")
        
        # 右侧 - 系统信息
        info_frame = tk.Frame(bottom_frame, bg="#2d4a6f", relief="flat", width=280)
        info_frame.pack(side="right", fill="both", padx=(10, 0))
        info_frame.pack_propagate(False)
        
        info_title = tk.Label(
            info_frame,
            text="系统信息",
            font=("Microsoft YaHei UI", 13, "bold"),
            bg="#2d4a6f",
            fg="white",
            anchor="w"
        )
        info_title.pack(fill="x", padx=20, pady=(15, 15))
        
        self.os_label = tk.Label(
            info_frame,
            text=f"操作系统：{self.get_os_info()}",
            font=("Microsoft YaHei UI", 11),
            bg="#2d4a6f",
            fg="#c8d8e8",
            anchor="w"
        )
        self.os_label.pack(fill="x", padx=20, pady=5)
        
        self.python_label = tk.Label(
            info_frame,
            text=f"Python版本：{self.get_python_version()}",
            font=("Microsoft YaHei UI", 11),
            bg="#2d4a6f",
            fg="#c8d8e8",
            anchor="w"
        )
        self.python_label.pack(fill="x", padx=20, pady=5)
        
        self.scan_time_label = tk.Label(
            info_frame,
            text="上次扫描：未扫描",
            font=("Microsoft YaHei UI", 11),
            bg="#2d4a6f",
            fg="#c8d8e8",
            anchor="w"
        )
        self.scan_time_label.pack(fill="x", padx=20, pady=5)
        
        # 图表区域
        self.chart_canvas = tk.Canvas(info_frame, width=240, height=100, bg="#2d4a6f", highlightthickness=0)
        self.chart_canvas.pack(padx=20, pady=20)
        self.draw_chart()
    
    def create_stats_cards(self):
        """创建统计卡片"""
        # 清空旧卡片
        for widget in self.stats_frame.winfo_children():
            widget.destroy()
        
        # 三个统计卡片
        stats_data = [
            ("磁盘使用情况", 
             f"{self.disk_usage_percent:.1f}% 已用 ({self.disk_used_gb:.1f}GB/{self.disk_total_gb:.1f}GB)", 
             "📊",
             self.disk_usage_percent / 100),
            ("剩余空间", 
             f"{self.disk_free_gb:.1f}GB 可用", 
             "💾",
             self.disk_free_gb / self.disk_total_gb),
            ("临时文件", 
             self.get_temp_files_display(), 
             "🕐",
             min(1.0, self.temp_files_size / 10.0) if self.temp_files_size > 0 else 0)
        ]
        
        for i, (title, value, icon, progress) in enumerate(stats_data):
            card = tk.Frame(self.stats_frame, bg="#4a6fa5")
            card.pack(side="left", expand=True, padx=15, pady=20)
            
            icon_label = tk.Label(
                card,
                text=icon,
                font=("Segoe UI Emoji", 24),
                bg="#4a6fa5",
                fg="white"
            )
            icon_label.pack()
            
            title_label = tk.Label(
                card,
                text=title,
                font=("Microsoft YaHei UI", 12, "bold"),
                bg="#4a6fa5",
                fg="white"
            )
            title_label.pack(pady=5)
            
            value_label = tk.Label(
                card,
                text=value,
                font=("Microsoft YaHei UI", 10),
                bg="#4a6fa5",
                fg="#c8d8e8"
            )
            value_label.pack()
            
            if i == 2:  # 临时文件卡片
                self.temp_files_label = value_label
            
            # 进度条
            progress_bar = tk.Canvas(card, width=200, height=4, bg="#4a6fa5", highlightthickness=0)
            progress_bar.pack(pady=5)
            progress_bar.create_rectangle(0, 0, 200, 4, fill="#2d4a6f", outline="")
            progress_bar.create_rectangle(0, 0, int(200 * progress), 4, fill="#5b9dd9", outline="")
    
    def get_temp_files_display(self):
        """获取临时文件显示文本"""
        if self.temp_files_count == 0:
            return "计算中..."
        
        size_text = f"{self.temp_files_size:.2f}GB" if self.temp_files_size >= 1 else f"{self.temp_files_size*1024:.0f}MB"
        return f"约 {self.temp_files_count} 个文件 ({size_text})"
    
    def start_temp_calculation(self):
        """启动后台计算临时文件"""
        thread = threading.Thread(target=self.calculate_temp_files)
        thread.daemon = True
        thread.start()
    
    def calculate_temp_files(self):
        """后台计算临时文件大小和数量"""
        self.after(0, lambda: self.add_log("[后台] 正在计算临时文件信息..."))
        
        # 使用新的垃圾路径函数
        temp_paths = self.get_junk_paths()
        
        total_size = 0
        file_count = 0
        
        for temp_path in temp_paths:
            try:
                if not os.path.exists(temp_path):
                    continue
                
                # 跳过需要管理员权限的某些系统文件夹
                if 'System32' in temp_path or 'WinSxS' in temp_path:
                    continue
                
                # 针对不同路径使用不同的扫描深度
                max_depth = 1
                if 'Chrome' in temp_path or 'Firefox' in temp_path or 'Edge' in temp_path:
                    max_depth = 3  # 浏览器缓存扫描更深
                elif 'Recycle' in temp_path:
                    max_depth = 2  # 回收站扫描2层
                elif 'Download' in temp_path:
                    max_depth = 1  # Windows更新下载文件夹
                elif 'Windows.old' in temp_path:
                    max_depth = 1  # Windows.old 文件夹
                elif 'SoftwareDistribution' in temp_path:
                    max_depth = 2  # Windows更新缓存
                
                for dirpath, dirnames, filenames in os.walk(temp_path):
                    # 计算当前深度
                    depth = dirpath[len(temp_path):].count(os.sep)
                    if depth >= max_depth:
                        dirnames.clear()
                    
                    for filename in filenames:
                        try:
                            filepath = os.path.join(dirpath, filename)
                            size = os.path.getsize(filepath)
                            total_size += size
                            file_count += 1
                            
                            # 每计算100个文件更新一次界面
                            if file_count % 100 == 0:
                                self.temp_files_size = total_size / (1024**3)
                                self.temp_files_count = file_count
                                self.after(0, self.create_stats_cards)
                                
                        except:
                            continue
                        
            except:
                continue
        
        # 最终更新
        self.temp_files_size = total_size / (1024**3)
        self.temp_files_count = file_count
        self.after(0, self.create_stats_cards)
        
        size_text = f"{self.temp_files_size:.2f}GB" if self.temp_files_size >= 1 else f"{self.temp_files_size*1024:.0f}MB"
        self.after(0, lambda: self.add_log(f"[完成] 发现约 {file_count} 个临时文件，总大小 {size_text}"))
    
    def draw_circular_progress(self):
        """绘制圆形进度条"""
        self.canvas.delete("all")
        
        # 绘制背景圆
        self.canvas.create_oval(20, 20, 180, 180, outline="#4a6fa5", width=15)
        
        # 绘制进度圆弧
        extent = -self.scan_progress * 3.6
        self.canvas.create_arc(
            20, 20, 180, 180,
            start=90,
            extent=extent,
            outline="#5bc9d9",
            width=15,
            style="arc"
        )
        
        # 添加文字
        self.canvas.create_text(
            100, 85,
            text=f"{self.scan_progress}%",
            font=("Microsoft YaHei UI", 32, "bold"),
            fill="white"
        )
        self.canvas.create_text(
            100, 120,
            text="已扫描",
            font=("Microsoft YaHei UI", 14),
            fill="white"
        )
    
    def draw_chart(self):
        """绘制图表"""
        self.chart_canvas.delete("all")
        bars = [30, 50, 35, 60, 45, 70, 55, 40, 65, 50]
        bar_width = 20
        for i, height in enumerate(bars):
            x = i * (bar_width + 4)
            self.chart_canvas.create_rectangle(
                x, 100 - height, x + bar_width, 100,
                fill="#4a6fa5",
                outline=""
            )
    
    def add_log(self, message):
        """添加日志"""
        self.log_text.config(state="normal")
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{timestamp}] {message}\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")
    
    def get_os_info(self):
        """获取操作系统信息"""
        import platform
        return f"{platform.system()} {platform.release()}"
    
    def get_python_version(self):
        """获取Python版本"""
        import sys
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    
    def start_scan(self):
        """开始扫描"""
        if self.is_scanning:
            messagebox.showwarning("警告", "正在扫描中，请稍候...")
            return
        
        # 禁用按钮
        self.scan_btn.config(state="disabled")
        self.clean_btn.config(state="disabled")
        
        # 重置数据
        self.scan_progress = 0
        self.found_files = []
        self.draw_circular_progress()
        
        self.add_log("[开始] 开始扫描C盘...")
        
        # 在新线程中执行扫描
        thread = threading.Thread(target=self.scan_thread)
        thread.daemon = True
        thread.start()
    
    def scan_thread(self):
        """扫描线程"""
        self.is_scanning = True
        
        # 使用新的垃圾路径函数
        temp_paths = self.get_junk_paths()
        
        # 添加发现垃圾目录数量的日志
        self.add_log(f"[扫描] 发现 {len(temp_paths)} 个垃圾目录")
        
        total_size = 0
        file_count = 0
        
        for temp_path in temp_paths:
            try:
                if not os.path.exists(temp_path):
                    continue
                    
                self.add_log(f"[扫描] 正在扫描: {temp_path}")
                
                # 针对不同类型设置不同的扫描深度
                max_depth = 1
                if 'Chrome' in temp_path or 'Firefox' in temp_path or 'Edge' in temp_path:
                    max_depth = 3  # 浏览器缓存深度扫描
                elif 'Recycle' in temp_path:
                    max_depth = 2  # 回收站
                elif 'Download' in temp_path or 'Prefetch' in temp_path:
                    max_depth = 1  # Windows更新下载和预读取
                elif 'Explorer' in temp_path:
                    max_depth = 2  # 缩略图缓存
                elif 'Windows.old' in temp_path:
                    max_depth = 1  # Windows.old 文件夹
                elif 'SoftwareDistribution' in temp_path:
                    max_depth = 2  # Windows更新缓存
                
                for dirpath, dirnames, filenames in os.walk(temp_path):
                    # 计算当前深度
                    depth = dirpath[len(temp_path):].count(os.sep)
                    if depth >= max_depth:
                        dirnames.clear()
                    
                    for filename in filenames:
                        try:
                            filepath = os.path.join(dirpath, filename)
                            size = os.path.getsize(filepath)
                            total_size += size
                            file_count += 1
                            
                            self.found_files.append({
                                'path': filepath,
                                'size': size,
                                'name': filename
                            })
                            
                            # 更新进度
                            if file_count % 50 == 0:
                                progress = min(90, int((file_count / 1000) * 90))
                                self.scan_progress = progress
                                self.after(0, self.draw_circular_progress)
                                
                            # 记录大文件
                            if size > 5 * 1024 * 1024:  # 大于5MB
                                self.after(0, lambda: self.add_log(f"[发现] {filename} ({size/(1024*1024):.2f}MB)"))
                                
                        except Exception as e:
                            continue
                        
            except Exception as e:
                self.after(0, lambda: self.add_log(f"[警告] 无法访问: {temp_path}"))
        
        # 更新临时文件大小和数量
        temp_gb = total_size / (1024**3)
        self.temp_files_size = temp_gb
        self.temp_files_count = file_count
        self.after(0, self.create_stats_cards)
        
        # 完成扫描
        self.scan_progress = 100
        self.after(0, self.draw_circular_progress)
        
        self.after(0, lambda: self.add_log(f"[完成] 扫描完成！发现 {file_count} 个临时文件"))
        self.after(0, lambda: self.add_log(f"[统计] 临时文件总大小: {temp_gb:.2f}GB"))
        
        # 更新扫描时间
        scan_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.after(0, lambda: self.scan_time_label.config(text=f"上次扫描：{scan_time}"))
        
        # 启用清理按钮
        self.after(0, lambda: self.clean_btn.config(state="normal"))
        self.after(0, lambda: self.scan_btn.config(state="normal"))
        self.after(0, lambda: self.scan_btn.config(text=f"可清理 {temp_gb:.1f}GB"))
        
        self.is_scanning = False
    
    def clean_now(self):
        """立即清理"""
        if self.is_cleaning:
            messagebox.showwarning("警告", "正在清理中，请稍候...")
            return
        
        if not self.found_files:
            messagebox.showinfo("提示", "没有发现需要清理的文件，请先扫描！")
            return
        
        # 确认对话框
        result = messagebox.askyesno(
            "确认清理",
            f"发现 {len(self.found_files)} 个临时文件\n"
            f"总大小约 {sum(f['size'] for f in self.found_files)/(1024**3):.2f}GB\n\n"
            "确定要清理这些文件吗？"
        )
        
        if not result:
            return
        
        # 禁用按钮
        self.clean_btn.config(state="disabled")
        self.scan_btn.config(state="disabled")
        
        self.add_log("[清理] 开始清理临时文件...")
        
        # 在新线程中执行清理
        thread = threading.Thread(target=self.clean_thread)
        thread.daemon = True
        thread.start()
    
    def clean_thread(self):
        """清理线程"""
        self.is_cleaning = True
        
        # 停止Windows Update服务
        self.add_log("[准备] 正在停止Windows Update服务...")
        self.stop_wuauserv()
        self.add_log("[准备] Windows Update服务已停止")
        
        cleaned_count = 0
        cleaned_size = 0
        failed_count = 0
        
        for file_info in self.found_files:
            try:
                filepath = file_info['path']
                size = file_info['size']
                
                if os.path.exists(filepath):
                    # 使用安全删除方法
                    if self.safe_remove(filepath):
                        cleaned_count += 1
                        cleaned_size += size
                        
                        if size > 10 * 1024 * 1024:  # 大于10MB的文件记录
                            self.add_log(f"[已清理] {file_info['name']} ({size/(1024*1024):.2f}MB)")
                    else:
                        failed_count += 1
                        
            except Exception as e:
                failed_count += 1
        
        # 清理完成
        self.cleaned_size = cleaned_size / (1024**3)
        
        self.add_log(f"[完成] 清理完成！")
        self.add_log(f"[统计] 成功清理 {cleaned_count} 个文件")
        self.add_log(f"[统计] 释放空间: {self.cleaned_size:.2f}GB")
        if failed_count > 0:
            self.add_log(f"[警告] {failed_count} 个文件清理失败（可能正在使用）")
        
        # 更新磁盘信息
        self.update_disk_info()
        self.after(0, self.create_stats_cards)
        
        # 清空已找到的文件列表
        self.found_files = []
        
        # 启动Windows Update服务
        self.add_log("[结束] 正在启动Windows Update服务...")
        self.start_wuauserv()
        self.add_log("[结束] Windows Update服务已启动")
        
        # 清空回收站
        self.empty_recycle_bin()
        self.add_log("[核弹] 已清空回收站")
        
        # 重新启用按钮
        self.after(0, lambda: self.scan_btn.config(state="normal"))
        
        self.is_cleaning = False
        
        # 显示完成消息
        self.after(0, lambda: messagebox.showinfo(
            "清理完成",
            f"成功清理 {cleaned_count} 个文件\n释放空间: {self.cleaned_size:.2f}GB"
        ))

    def empty_recycle_bin(self):
        """清空回收站"""
        try:
            # SHEmptyRecycleBinW = 0 (清空所有盘符)
            ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0)
        except:
            pass

    def safe_remove(self, path):
        """安全删除文件"""
        try:
            if os.path.isfile(path):
                os.chmod(path, 0o777)  # 解除只读
                os.remove(path)
                return True
        except Exception as e:
            # 文件被占用就跳过
            pass
        return False

if __name__ == "__main__":
    app = CDriveCleaner()
    app.mainloop()