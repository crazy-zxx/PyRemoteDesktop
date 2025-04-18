import platform
import socket
import struct
import sys
import threading
import time
import tkinter
from tkinter import messagebox

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

        # socket 连接
        self.sock = None
        # 存储连接信息和相关组件，改为字典
        self.connections = {}
        self.max_connections = 5
        self.check_interval = 1
        self.buffer_size = 65536

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

        # 显示连接列表
        tkinter.Label(self.root, text="连接会话列表", bd=2, relief="solid", width=123).grid(row=1, column=0,
                                                                                            columnspan=6,
                                                                                            ipady=5)
        # 表格头部
        header_frame = tkinter.Frame(self.root, bd=1, relief="solid")
        header_frame.grid(row=2, column=0, columnspan=6, sticky="nsew", padx=5)
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
        self.connections_frame.grid(row=3, column=0, columnspan=6, sticky="nsew", padx=5)

        # 检查连接
        threading.Thread(target=self.check_connections, daemon=True).start()

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
            messagebox.showerror('提示', '启动监听失败！')
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
                    self.destroy_connection(conn, addr)
                    print(e)
                    # raise

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

                # monitor_window.canvas.focus_set()

            except Exception as e:
                print(e)
                # raise

    def bind_control(self, addr):
        canvas = self.connections[addr]['monitor_window'].canvas

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
        self.stop_listening()
        self.root.destroy()


if __name__ == '__main__':
    root = tkinter.Tk()
    rdc = RemoteDesktopServer(root)
    root.mainloop()
