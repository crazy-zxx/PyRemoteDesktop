import platform
import socket
import struct
import sys
import threading
import time
import tkinter
from tkinter import messagebox
import subprocess
import os
import configparser

import cv2
import numpy as np
from PIL import Image, ImageTk

# 平台
PLAT = b''
if sys.platform == "win32":
    PLAT = b'win'
elif sys.platform == "darwin":
    PLAT = b'osx'
elif platform.system() == "Linux":
    PLAT = b'x11'

last_send = time.time()


class RemoteDesktopServer:
    def __init__(self, ui):
        super().__init__()

        # UI
        self.root = ui

        # 自定义消息框函数，使其置顶于父窗口并居中显示
        self.messagebox = self._create_messagebox

        # socket 连接
        self.sock = None
        # 存储连接信息和相关组件，改为字典
        self.connections = {}
        self.max_connections = 5
        self.check_interval = 1
        self.buffer_size = 65536

        # frp 相关
        self.frp_process = None
        self.frp_config_path = os.path.join(os.getcwd(), 'frpc.ini')
        self.frp_client_path = os.path.join(os.getcwd(), 'frpc.exe')  # Windows 默认路径，根据系统可调整

        # 设置窗口标题
        self.root.title("远程桌面控制端")

        # 设置窗口大小，在屏幕居中显示
        win_width, win_height = 882, 500
        win_x = (self.root.winfo_screenwidth() - win_width) // 2
        win_y = (self.root.winfo_screenheight() - win_height) // 2
        self.root.geometry(f'{win_width}x{win_height}+{win_x}+{win_y}')
        # 禁止调整窗口大小
        self.root.resizable(False, False)

        # 绑定关闭窗口事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # 窗口组件
        # 监听配置区域
        tkinter.Label(self.root, text="监听地址：").grid(row=0, column=0, sticky=tkinter.EW, padx=10, pady=10)
        self.local_ip = tkinter.Entry(self.root, textvariable=tkinter.StringVar(value='0.0.0.0'), width=10)
        self.local_ip.grid(row=0, column=1, sticky=tkinter.EW, padx=10, pady=10)
        tkinter.Label(self.root, text="监听端口：").grid(row=0, column=2, sticky=tkinter.EW, padx=10, pady=10)
        self.local_port = tkinter.Entry(self.root, textvariable=tkinter.StringVar(value='54321'), width=10)
        self.local_port.grid(row=0, column=3, sticky=tkinter.EW, padx=10, pady=10)
        self.start_listening_button = tkinter.Button(self.root, text="启动监听", width=10, command=self.start_listening)
        self.start_listening_button.grid(row=0, column=4, sticky=tkinter.EW, padx=10, pady=10)
        self.stop_listening_button = tkinter.Button(self.root, text="停止监听", width=10, state="disabled",
                                                    command=self.stop_listening)
        self.stop_listening_button.grid(row=0, column=5, sticky=tkinter.EW, padx=10, pady=10)

        # frp 配置区域
        frp_frame = tkinter.Frame(self.root, bd=2, relief="solid")
        frp_frame.grid(row=1, column=0, columnspan=6, sticky="nsew", padx=5, pady=5)
        tkinter.Label(frp_frame, text="FRP 配置", font=('Arial', 10, 'bold')).grid(row=0, column=0, columnspan=6,
                                                                                   sticky="w", padx=5)

        # FRP 服务端配置
        tkinter.Label(frp_frame, text="FRP 服务器地址：").grid(row=1, column=0, sticky=tkinter.E, padx=5, pady=5)
        self.frp_server_ip = tkinter.Entry(frp_frame, textvariable=tkinter.StringVar(value=''), width=15)
        self.frp_server_ip.grid(row=1, column=1, sticky=tkinter.W, padx=5, pady=5)

        tkinter.Label(frp_frame, text="FRP 服务器端口：").grid(row=1, column=2, sticky=tkinter.E, padx=5, pady=5)
        self.frp_server_port = tkinter.Entry(frp_frame, textvariable=tkinter.StringVar(value='7000'), width=10)
        self.frp_server_port.grid(row=1, column=3, sticky=tkinter.W, padx=5, pady=5)

        tkinter.Label(frp_frame, text="FRP 连接Token：").grid(row=1, column=4, sticky=tkinter.E, padx=5, pady=5)
        self.frp_token = tkinter.Entry(frp_frame, textvariable=tkinter.StringVar(value=''), width=15, show='*')
        self.frp_token.grid(row=1, column=5, sticky=tkinter.W, padx=5, pady=5)

        # FRP 客户端配置
        tkinter.Label(frp_frame, text="本地监听端口：").grid(row=2, column=0, sticky=tkinter.E, padx=5, pady=5)
        self.frp_local_port = tkinter.Entry(frp_frame, textvariable=tkinter.StringVar(value='54321'), width=10)
        self.frp_local_port.grid(row=2, column=1, sticky=tkinter.W, padx=5, pady=5)

        tkinter.Label(frp_frame, text="远程访问端口：").grid(row=2, column=2, sticky=tkinter.E, padx=5, pady=5)
        self.frp_remote_port = tkinter.Entry(frp_frame, textvariable=tkinter.StringVar(value='54321'), width=10)
        self.frp_remote_port.grid(row=2, column=3, sticky=tkinter.W, padx=5, pady=5)

        self.frp_enabled = tkinter.BooleanVar(value=False)
        self.frp_toggle = tkinter.Checkbutton(frp_frame, text="启用FRP连接", variable=self.frp_enabled,
                                              command=self.toggle_frp, indicatoron=True, width=12)
        self.frp_toggle.grid(row=2, column=4, sticky=tkinter.W, padx=5, pady=5)

        self.frp_status_label = tkinter.Label(frp_frame, text="FRP状态: 未连接", fg="red")
        self.frp_status_label.grid(row=2, column=5, sticky=tkinter.W, padx=5, pady=5)

        # 设置frp_frame列宽权重
        for i in range(6):
            frp_frame.columnconfigure(i, weight=1)

        # 显示连接列表
        tkinter.Label(self.root, text="连接会话列表", bd=2, relief="solid", width=123).grid(row=2, column=0,
                                                                                            columnspan=6,
                                                                                            ipady=5)
        # 表格头部
        header_frame = tkinter.Frame(self.root, bd=1, relief="solid")
        header_frame.grid(row=3, column=0, columnspan=6, sticky="nsew", padx=5)
        headers = ["被控端地址", "端口", "启动监控", "开启控制", "删除连接", "缩放比例"]
        for col, header in enumerate(headers):
            if header == "端口":
                width = 10
            elif header == "缩放比例":
                width = 31
            else:
                width = 20
            tkinter.Label(header_frame, text=header, bd=1, relief="solid", width=width).grid(row=0, column=col,
                                                                                             sticky="nsew")
            header_frame.columnconfigure(col, weight=1)

        # 用于显示连接信息的框架
        self.connections_frame = tkinter.Frame(self.root, bd=1, relief="solid")
        self.connections_frame.grid(row=4, column=0, columnspan=6, sticky="nsew", padx=5)

        # 检查连接
        threading.Thread(target=self.check_connections, daemon=True).start()

    def _create_messagebox(self, msg_type, title, message):
        """创建一个置顶于父窗口并居中显示的消息框"""
        # 创建自定义Toplevel窗口作为消息框
        msg_window = tkinter.Toplevel(self.root)
        msg_window.title(title)
        msg_window.transient(self.root)  # 设置为主窗口的子窗口
        msg_window.grab_set()  # 模态窗口，阻止主窗口操作

        # 设置窗口属性
        msg_window.configure(bg="white")

        # 计算窗口大小和位置，使其在父窗口中心
        msg_width = 300
        msg_height = 150

        # 获取父窗口位置
        parent_x = self.root.winfo_x()
        parent_y = self.root.winfo_y()
        parent_width = self.root.winfo_width()
        parent_height = self.root.winfo_height()

        # 计算消息框位置，使其居中于父窗口
        msg_x = parent_x + (parent_width - msg_width) // 2
        msg_y = parent_y + (parent_height - msg_height) // 2

        # 设置窗口位置和大小
        msg_window.geometry(f"{msg_width}x{msg_height}+{msg_x}+{msg_y}")
        msg_window.resizable(False, False)

        # 添加消息标签
        msg_label = tkinter.Label(msg_window, text=message, font=("SimHei", 10), wraplength=msg_width - 40,
                                  justify="center", bg="white")
        msg_label.pack(pady=30)

        # 添加确定按钮
        ok_button = tkinter.Button(msg_window, text="确定", width=10, command=msg_window.destroy)
        ok_button.pack(pady=10)

        # 设置按钮为默认焦点
        ok_button.focus_set()

        # 绑定Enter键关闭窗口
        msg_window.bind("<Return>", lambda event: msg_window.destroy())

        # 等待用户关闭消息框
        self.root.wait_window(msg_window)

        return None  # 自定义消息框没有返回值

    def messagebox_showerror(self, title, message):
        """错误消息框"""
        return self._create_messagebox(messagebox.showerror, title, message)

    def messagebox_showinfo(self, title, message):
        """信息消息框"""
        return self._create_messagebox(messagebox.showinfo, title, message)

    def messagebox_showwarning(self, title, message):
        """警告消息框"""
        return self._create_messagebox(messagebox.showwarning, title, message)

    def start_listening(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            ip = self.local_ip.get()
            port = int(self.local_port.get())
            self.sock.bind((ip, port))
            self.sock.listen(self.max_connections)
            self.start_listening_button.config(state=tkinter.DISABLED)
            self.stop_listening_button.config(state=tkinter.NORMAL)
            # 新线程中持续监听连接
            threading.Thread(target=self.accept_connections, daemon=True).start()
        except Exception as e:
            self.messagebox_showerror('提示', '启动监听失败！')
            print(e)
            # raise

    def accept_connections(self):
        while True:
            conn, addr = self.sock.accept()
            print('Accept new connection from %s:%s ...' % addr)
            # 添加连接记录到列表中显示
            self.add_connection(conn, addr)

    def add_connection(self, conn, addr):
        ip, port = addr
        connection_frame = tkinter.Frame(self.connections_frame, bd=1, relief="solid")
        connection_frame.grid(row=len(self.connections), column=0, columnspan=6)
        tkinter.Label(connection_frame, text=ip, bd=0, relief="solid", width=20).grid(row=0, column=0,
                                                                                      sticky=tkinter.EW)
        tkinter.Label(connection_frame, text=port, bd=0, relief="solid", width=10).grid(row=0, column=1,
                                                                                        sticky=tkinter.EW)
        start_button = tkinter.Button(connection_frame, text="启动监控", width=10,
                                      command=lambda: self.start_monitoring(addr, ))
        start_button.grid(row=0, column=2, sticky=tkinter.EW, padx=32)
        ctl_status = tkinter.BooleanVar(value=False)
        toggle_button = tkinter.Checkbutton(connection_frame, text="开启控制", variable=ctl_status,
                                            command=lambda: self.toggle_control(ctl_status.get(), addr),
                                            indicatoron=True, width=8)
        toggle_button.grid(row=0, column=3, sticky=tkinter.EW, padx=32)
        stop_button = tkinter.Button(connection_frame, text="删除连接", width=10,
                                     command=lambda: self.destroy_connection(addr, ))
        stop_button.grid(row=0, column=4, sticky=tkinter.EW, padx=32)
        scale_bar = tkinter.Scale(connection_frame, from_=0.5, to=2.0, resolution=0.1, length=213,
                                  orient=tkinter.HORIZONTAL,
                                  command=lambda _: self.adjust_scale(scale_bar.get(), addr))
        scale_bar.set(1.0)
        scale_bar.grid(row=0, column=5, sticky=tkinter.EW)
        self.connections[addr] = {
            'conn': conn,
            'addr': addr,
            'start_button': start_button,
            'toggle_button': toggle_button,
            'ctl_status': False,
            'stop_button': stop_button,
            'scale_bar': scale_bar,
            'scale': 1.0,
            'frame': connection_frame,
            'monitor_window': None
        }
        for col in range(6):
            connection_frame.columnconfigure(col, weight=1)

        # 发送平台信息
        self.connections[addr]['conn'].sendall(PLAT)

    def check_connections(self):
        while True:
            time.sleep(self.check_interval)
            for addr in list(self.connections.keys()):
                conn = self.connections[addr]['conn']
                try:
                    conn.sendall(b'')
                except Exception as e:
                    self.destroy_connection(addr)
                    print(e)
                    # raise

    def toggle_frp(self):
        """切换frp客户端的启动和关闭状态"""
        if self.frp_enabled.get():
            self.start_frp()
        else:
            self.stop_frp()

    def start_frp(self):
        """启动frp客户端"""
        try:
            # 检查frp客户端可执行文件是否存在
            if not os.path.exists(self.frp_client_path):
                self.messagebox_showerror('错误',
                                          f'未找到frp客户端程序: {self.frp_client_path}\n请确保frpc.exe已放置在程序目录中')
                self.frp_enabled.set(False)
                return

            # 获取配置信息
            server_ip = self.frp_server_ip.get()
            server_port = self.frp_server_port.get()
            token = self.frp_token.get()
            local_port = self.frp_local_port.get()
            remote_port = self.frp_remote_port.get()

            # 验证必要配置
            if not server_ip or not server_port or not token:
                self.messagebox_showerror('错误', '请填写完整的FRP服务器配置')
                self.frp_enabled.set(False)
                return

            # 创建frp配置文件
            self.create_frp_config(server_ip, server_port, token, local_port, remote_port)

            # 启动frp客户端
            self.frp_process = subprocess.Popen(
                [self.frp_client_path, '-c', self.frp_config_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # 更新状态
            self.frp_status_label.config(text="FRP状态: 已连接", fg="green")
            # self.messagebox_showinfo('成功', 'FRP客户端已启动')

            # 启动监控线程检查frp进程状态
            threading.Thread(target=self.monitor_frp, daemon=True).start()

        except Exception as e:
            self.messagebox_showerror('错误', f'启动FRP客户端失败: {str(e)}')
            self.frp_enabled.set(False)
            self.frp_status_label.config(text="FRP状态: 未连接", fg="red")

    def stop_frp(self):
        """停止frp客户端"""
        try:
            if self.frp_process:
                # 终止进程
                if platform.system() == "Windows":
                    # Windows下使用taskkill确保完全终止进程树
                    subprocess.call(['taskkill', '/F', '/T', '/PID', str(self.frp_process.pid)])
                else:
                    # Unix-like系统
                    self.frp_process.terminate()
                    self.frp_process.wait(timeout=5)

                self.frp_process = None
                self.frp_status_label.config(text="FRP状态: 未连接", fg="red")
                # self.messagebox_showinfo('成功', 'FRP客户端已停止')
        except Exception as e:
            self.messagebox_showerror('错误', f'停止FRP客户端失败: {str(e)}')
            self.frp_status_label.config(text="FRP状态: 错误", fg="orange")

    def create_frp_config(self, server_ip, server_port, token, local_port, remote_port):
        """创建frp客户端配置文件"""
        config = configparser.ConfigParser()

        # 通用配置
        config['common'] = {
            'server_addr': server_ip,
            'server_port': server_port,
            'token': token
        }

        # 远程桌面服务的隧道配置
        config['remote_desktop'] = {
            'type': 'tcp',
            'local_ip': '127.0.0.1',
            'local_port': local_port,
            'remote_port': remote_port
        }

        # 写入配置文件
        with open(self.frp_config_path, 'w', encoding='utf-8') as f:
            config.write(f)

    def monitor_frp(self):
        """监控frp客户端进程状态"""
        if self.frp_process:
            # 等待进程结束
            self.frp_process.wait()

            # 如果进程意外终止，更新UI状态
            if self.frp_enabled.get():
                # 在主线程中更新UI
                self.root.after(0, lambda: self.frp_status_label.config(text="FRP状态: 意外终止", fg="red"))
                self.root.after(0, lambda: self.frp_enabled.set(False))
                self.root.after(0, lambda: self.messagebox_showerror('错误', 'FRP客户端意外终止'))

    def start_monitoring(self, addr):
        # 启动后禁用start_button按钮
        self.connections[addr]['start_button'].config(state=tkinter.DISABLED)
        self.connections[addr]['toggle_button'].config(state=tkinter.DISABLED)

        monitor_window = tkinter.Toplevel(self.root)
        # 禁用窗口置顶
        monitor_window.attributes("-topmost", False)
        # 禁用窗口尺寸手动调整
        monitor_window.resizable(False, False)
        monitor_window.title(f"监控 {addr[0]}:{addr[1]}")
        # 这里需要实现画面渲染和控制的逻辑
        canvas = tkinter.Canvas(monitor_window, width=1024, height=768, background="black")
        canvas.pack()
        monitor_window.canvas = canvas
        # 绑定关闭窗口事件
        monitor_window.protocol("WM_DELETE_WINDOW", lambda: self.monitor_window_close(addr))
        self.connections[addr]['monitor_window'] = monitor_window
        threading.Thread(target=self.receive_screen, args=(addr,), daemon=True).start()
        if self.connections[addr]['ctl_status']:
            self.bind_control(addr)

    def monitor_window_close(self, addr):
        # 关闭monitor_window窗口
        if self.connections[addr]['monitor_window']:
            self.connections[addr]['monitor_window'].destroy()
            self.connections[addr]['monitor_window'] = None
        self.connections[addr]['start_button'].config(state=tkinter.NORMAL)
        self.connections[addr]['toggle_button'].config(state=tkinter.NORMAL)

    def destroy_connection(self, addr):
        if addr in self.connections:
            if self.connections[addr]['monitor_window']:
                self.connections[addr]['monitor_window'].destroy()
            self.connections[addr]['conn'].close()
            self.connections[addr]['frame'].destroy()
            del self.connections[addr]

    def toggle_control(self, new_ctl_status, addr):
        if addr in self.connections:
            self.connections[addr]['ctl_status'] = new_ctl_status

    def adjust_scale(self, new_scale, addr):
        if addr in self.connections:
            self.connections[addr]['scale'] = float(new_scale)

    def stop_listening(self):
        # 关闭所有打开的monitor_window窗口、结束已经打开的会话连接
        for addr in list(self.connections.keys()):
            if self.connections[addr]['monitor_window']:
                self.connections[addr]['monitor_window'].destroy()
            self.connections[addr]['conn'].close()
            try:
                self.connections[addr]['frame'].destroy()
                del self.connections[addr]
            except Exception as e:
                print(e)
                # raise

        if self.sock:
            self.sock.close()
        self.start_listening_button.config(state=tkinter.NORMAL)
        self.stop_listening_button.config(state=tkinter.DISABLED)

    def receive_screen(self, addr):
        data = b""
        payload_size = struct.calcsize("Q")

        while self.connections[addr]['monitor_window']:
            while len(data) < payload_size:
                packet = self.connections[addr]['conn'].recv(self.buffer_size)
                if not packet:
                    break
                data += packet

            if len(data) < payload_size:
                continue

            packed_msg_size = data[:payload_size]
            data = data[payload_size:]
            msg_size = struct.unpack("Q", packed_msg_size)[0]

            while len(data) < msg_size:
                data += self.connections[addr]['conn'].recv(self.buffer_size)

            frame_data = data[:msg_size]
            data = data[msg_size:]

            # 从frame_data解码JPEG图像，然后渲染到monitor_window的canvas中去
            try:
                # 解码 JPEG 图像
                frame_data = np.frombuffer(frame_data, dtype=np.uint8)
                img = cv2.imdecode(frame_data, cv2.IMREAD_COLOR)
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                # 获取当前连接的缩放比例
                scale = self.connections[addr]['scale']

                # 根据缩放比例调整图像大小
                height, width = img.shape[:2]
                new_width = int(width * scale)
                new_height = int(height * scale)
                img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_AREA)
                img = Image.fromarray(img)
                photo = ImageTk.PhotoImage(img)

                # 调整 Canvas 和窗口的大小
                monitor_window = self.connections[addr]['monitor_window']
                monitor_window.canvas.config(width=new_width, height=new_height)
                monitor_window.geometry(f"{new_width}x{new_height}")

                # 在 Canvas 上显示图像
                monitor_window.canvas.create_image(0, 0, anchor=tkinter.NW, image=photo)
                monitor_window.canvas.image = photo  # 保持对图像的引用，防止被垃圾回收

            except Exception as e:
                print(e)

    def bind_control(self, addr):
        canvas = self.connections[addr]['monitor_window'].canvas
        # 设置Canvas获取焦点
        canvas.focus_set()

        def EventDo(data):
            self.connections[addr]['conn'].sendall(data)

        # 鼠标左键
        def LeftDown(e):
            # 获取当前连接的缩放比例
            scale = self.connections[addr]['scale']
            return EventDo(struct.pack('>BBHH', 1, 100, int(e.x / scale), int(e.y / scale)))

        def LeftUp(e):
            # 获取当前连接的缩放比例
            scale = self.connections[addr]['scale']
            return EventDo(struct.pack('>BBHH', 1, 117, int(e.x / scale), int(e.y / scale)))

        canvas.bind(sequence="<1>", func=LeftDown)
        canvas.bind(sequence="<ButtonRelease-1>", func=LeftUp)

        # 鼠标右键
        def RightDown(e):
            # 获取当前连接的缩放比例
            scale = self.connections[addr]['scale']
            return EventDo(struct.pack('>BBHH', 3, 100, int(e.x / scale), int(e.y / scale)))

        def RightUp(e):
            # 获取当前连接的缩放比例
            scale = self.connections[addr]['scale']
            return EventDo(struct.pack('>BBHH', 3, 117, int(e.x / scale), int(e.y / scale)))

        canvas.bind(sequence="<3>", func=RightDown)
        canvas.bind(sequence="<ButtonRelease-3>", func=RightUp)

        # 鼠标滚轮
        if PLAT == b'win' or PLAT == b'osx':
            # windows/mac
            def Wheel(e):
                # 获取当前连接的缩放比例
                scale = self.connections[addr]['scale']
                if e.delta < 0:
                    return EventDo(struct.pack('>BBHH', 2, 0, int(e.x / scale), int(e.y / scale)))
                else:
                    return EventDo(struct.pack('>BBHH', 2, 1, int(e.x / scale), int(e.y / scale)))

            canvas.bind(sequence="<MouseWheel>", func=Wheel)

        elif PLAT == b'x11':
            def WheelDown(e):
                # 获取当前连接的缩放比例
                scale = self.connections[addr]['scale']
                return EventDo(struct.pack('>BBHH', 2, 0, int(e.x / scale), int(e.y / scale)))

            def WheelUp(e):
                # 获取当前连接的缩放比例
                scale = self.connections[addr]['scale']
                return EventDo(struct.pack('>BBHH', 2, 1, int(e.x / scale), int(e.y / scale)))

            canvas.bind(sequence="<Button-4>", func=WheelUp)
            canvas.bind(sequence="<Button-5>", func=WheelDown)

        # 鼠标滑动
        # 画面周期
        IDLE = 0.01

        # 10ms发送一次
        def Move(e):
            # 获取当前连接的缩放比例
            scale = self.connections[addr]['scale']
            global last_send
            cu = time.time()
            if cu - last_send > IDLE:
                last_send = cu
                sx, sy = int(e.x / scale), int(e.y / scale)
                return EventDo(struct.pack('>BBHH', 4, 0, sx, sy))
            return None

        canvas.bind(sequence="<Motion>", func=Move)

        # 键盘
        def KeyDown(e):
            # 获取当前连接的缩放比例
            scale = self.connections[addr]['scale']
            return EventDo(struct.pack('>BBHH', e.keycode, 100, int(e.x / scale), int(e.y / scale)))

        def KeyUp(e):
            # 获取当前连接的缩放比例
            scale = self.connections[addr]['scale']
            return EventDo(struct.pack('>BBHH', e.keycode, 117, int(e.x / scale), int(e.y / scale)))

        canvas.bind(sequence="<KeyPress>", func=KeyDown)
        canvas.bind(sequence="<KeyRelease>", func=KeyUp)

    def on_close(self):
        # 停止frp客户端
        self.stop_frp()
        # 停止监听服务
        self.stop_listening()
        # 销毁窗口
        self.root.destroy()


if __name__ == '__main__':
    root = tkinter.Tk()
    rdc = RemoteDesktopServer(root)
    root.mainloop()