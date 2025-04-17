import io
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


last_send = time.time()

class RemoteDesktopServer:
    def __init__(self, ui):
        super().__init__()

        # UI
        self.root = ui

        # socket 连接
        self.sock = None
        # 存储连接信息和相关组件
        self.connections = []
        self.max_connections = 5
        self.check_interval = 1
        self.buffer_size = 65536
        self.scale = 1.0

        # 设置窗口标题
        self.root.title("远程桌面控制端")

        # 设置窗口大小，在屏幕居中显示
        win_width, win_height = 732, 400
        win_x = (self.root.winfo_screenwidth() - win_width) // 2
        win_y = (self.root.winfo_screenheight() - win_height) // 2
        self.root.geometry(f'{win_width}x{win_height}+{win_x}+{win_y}')
        # 禁止调整窗口大小
        self.root.resizable(False, False)

        # 绑定关闭窗口事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # 窗口组件
        tkinter.Label(self.root, text="监听地址：", ).grid(row=0, column=0, sticky=tkinter.W, padx=5, ipady=5)
        self.local_ip = tkinter.Entry(self.root, textvariable=tkinter.StringVar(value='0.0.0.0'), width=10)
        self.local_ip.grid(row=0, column=1, sticky=tkinter.W, padx=5, pady=5)
        tkinter.Label(self.root, text="监听端口：").grid(row=0, column=2, sticky=tkinter.W, padx=5, pady=5)
        self.local_port = tkinter.Entry(self.root, textvariable=tkinter.StringVar(value='54321'), width=10)
        self.local_port.grid(row=0, column=3, sticky=tkinter.W, padx=5, pady=5)
        self.start_listening_button = tkinter.Button(self.root, text="启动监听", width=10, command=self.start_listening)
        self.start_listening_button.grid(row=0, column=4, sticky=tkinter.E, padx=5, pady=5)
        self.stop_listening_button = tkinter.Button(self.root, text="停止监听", width=10, state="disabled", command=self.stop_listening)
        self.stop_listening_button.grid(row=0, column=5, sticky=tkinter.E, padx=5, pady=5)

        # 显示连接列表
        tkinter.Label(self.root, text="连接会话列表", bd=2, relief="solid", width=102).grid(row=1, column=0, columnspan=6, ipady=5)
        # 表格头部
        header_frame = tkinter.Frame(self.root, bd=1, relief="solid")
        header_frame.grid(row=2, column=0, columnspan=6, sticky="nsew", padx=5)
        headers = ["被控端地址", "端口", "启动监控", "删除连接", "缩放比例"]
        for col, header in enumerate(headers):
            if header == "端口":
                width = 10
            elif header == "缩放比例":
                width = 30
            else:
                width = 20
            tkinter.Label(header_frame, text=header, bd=1, relief="solid", width=width).grid(row=0, column=col, sticky="nsew")
            header_frame.columnconfigure(col, weight=1)

        # 用于显示连接信息的框架
        self.connections_frame = tkinter.Frame(self.root, bd=1, relief="solid")
        self.connections_frame.grid(row=3, column=0, columnspan=6, sticky="nsew", padx=5)

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
            raise

    def accept_connections(self):
        while True:
            conn, addr = self.sock.accept()
            print('Accept new connection from %s:%s ...' % addr)
            # 添加连接记录到列表中显示
            self.add_connection(conn, addr)
            threading.Thread(target=self.check_connection, args=(conn, addr), daemon=True).start()

    def add_connection(self, conn, addr):
        row = len(self.connections)
        ip, port = addr
        connection_frame = tkinter.Frame(self.connections_frame, bd=1, relief="solid")
        connection_frame.grid(row=row, column=0, columnspan=6)
        tkinter.Label(connection_frame, text=ip, bd=0, relief="solid", width=20).grid(row=0, column=0, sticky="ew")
        tkinter.Label(connection_frame, text=port, bd=0, relief="solid", width=10).grid(row=0, column=1, sticky="ew")
        start_button = tkinter.Button(connection_frame, text="启动监控", width=10,
                                      command=lambda: self.start_monitoring(conn, addr))
        start_button.grid(row=0, column=2, sticky="ew", padx=32)
        stop_button = tkinter.Button(connection_frame, text="删除连接", width=10,
                                     command=lambda: self.destroy_connection(conn, addr))
        stop_button.grid(row=0, column=3, sticky="ew", padx=32)
        scale_bar = tkinter.Scale(connection_frame, from_=0.5, to=2.0, resolution=0.1, length=210,
                                  orient=tkinter.HORIZONTAL,
                                  command=lambda _: self.adjust_scale(scale_bar.get(), conn))
        scale_bar.set(1.0)
        scale_bar.grid(row=0, column=4, sticky="ew")
        self.connections.append({
            'conn': conn,
            'addr': addr,
            'start_button': start_button,
            'stop_button': stop_button,
            'scale_bar': scale_bar,
            'frame': connection_frame,
            'monitor_window': None
        })
        for col in range(5):
            connection_frame.columnconfigure(col, weight=1)

    def check_connection(self, conn, addr):
        while True:
            time.sleep(self.check_interval)
            try:
                # 尝试发送一个空字节来检查连接
                conn.sendall(b'')
            except Exception as e:
                self.destroy_connection(conn, addr)
                print(e)
                raise
                # raise

    def start_monitoring(self, conn, addr):
        # 启动后禁用start_button按钮
        for connection in self.connections:
            if connection['conn'] == conn and connection['addr'] == addr:
                connection['start_button'].config(state=tkinter.DISABLED)

        monitor_window = tkinter.Toplevel(self.root)
        monitor_window.title(f"监控 {addr[0]}:{addr[1]}")
        # 这里需要实现画面渲染和控制的逻辑
        canvas = tkinter.Canvas(monitor_window, width=1024, height=768, background="black")
        # canvas.focus_set()
        canvas.pack()
        monitor_window.canvas = canvas
        # 绑定关闭窗口事件
        monitor_window.protocol("WM_DELETE_WINDOW", lambda: self.monitor_window_close(conn, addr))
        for connection in self.connections:
            if connection['conn'] == conn and connection['addr'] == addr:
                connection['monitor_window'] = monitor_window
        threading.Thread(target=self.receive_screen, args=(conn, addr, monitor_window), daemon=True).start()
        threading.Thread(target=self.send_control, args=(conn, addr, canvas), daemon=True).start()

    def monitor_window_close(self, conn, addr):
        # 关闭monitor_window窗口
        for connection in self.connections:
            if connection['conn'] == conn and connection['addr'] == addr:
                if connection['monitor_window']:
                    connection['monitor_window'].destroy()
                    connection['monitor_window'] = None
                connection['start_button'].config(state=tkinter.NORMAL)

    def destroy_connection(self, conn, addr):
        for connection in self.connections:
            if connection['conn'] == conn and connection['addr'] == addr:
                if connection['monitor_window']:
                    connection['monitor_window'].destroy()
                connection['conn'].close()
                connection['frame'].destroy()
                self.connections.remove(connection)
                break

    def adjust_scale(self, new_scale, conn):
        for connection in self.connections:
            if connection['conn'] == conn:
                connection['scale'] = float(new_scale)
                break

    def get_scale(self, conn):
        # 获取当前连接的缩放比例
        scale = 1.0
        for connection in self.connections:
            if connection['conn'] == conn:
                scale = float(connection['scale_bar'].get())
                break
        return scale

    def stop_listening(self):
        # 关闭所有打开的monitor_window窗口、结束已经打开的会话连接
        for connection in self.connections:
            if connection['monitor_window']:
                connection['monitor_window'].destroy()
            connection['conn'].close()
            try:
                connection['frame'].destroy()
            except Exception as e:
                print(e)


        if self.sock:
            self.sock.close()
        self.start_listening_button.config(state=tkinter.NORMAL)
        self.stop_listening_button.config(state=tkinter.DISABLED)

    def receive_screen(self, conn, addr, monitor_window):
        data = b""
        payload_size = struct.calcsize("Q")
        while True:
            while len(data) < payload_size:
                packet = conn.recv(self.buffer_size)
                if not packet:
                    break
                data += packet

            if len(data) < payload_size:
                continue

            packed_msg_size = data[:payload_size]
            data = data[payload_size:]
            msg_size = struct.unpack("Q", packed_msg_size)[0]

            while len(data) < msg_size:
                data += conn.recv(self.buffer_size)

            frame_data = data[:msg_size]
            data = data[msg_size:]

            # 从frame_data解码JPEG图像，然后渲染到monitor_window的canvas中去
            try:
                # 解码 JPEG 图像
                frame_data = np.frombuffer(frame_data, dtype=np.uint8)
                img = cv2.imdecode(frame_data, cv2.IMREAD_COLOR)
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                # 获取当前连接的缩放比例
                scale = 1.0
                for connection in self.connections:
                    if connection['conn'] == conn:
                        scale = float(connection['scale_bar'].get())
                        break

                # 根据缩放比例调整图像大小
                height, width = img.shape[:2]
                new_width = int(width * scale)
                new_height = int(height * scale)
                img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_AREA)
                img = Image.fromarray(img)
                photo = ImageTk.PhotoImage(img)

                # 调整 Canvas 和窗口的大小
                monitor_window.canvas.config(width=new_width, height=new_height)
                monitor_window.geometry(f"{new_width}x{new_height}")

                # 在 Canvas 上显示图像
                monitor_window.canvas.create_image(0, 0, anchor=tkinter.NW, image=photo)
                monitor_window.canvas.image = photo  # 保持对图像的引用，防止被垃圾回收

                monitor_window.canvas.focus_set()

            except Exception as e:
                raise

    def send_control(self, conn, addr, canvas):
        # 平台
        PLAT = b''
        if sys.platform == "win32":
            PLAT = b'win'
        elif sys.platform == "darwin":
            PLAT = b'osx'
        elif platform.system() == "Linux":
            PLAT = b'x11'
        # 发送平台信息
        conn.sendall(PLAT)

        # 画面周期
        IDLE = 0.05

        def EventDo(data):
            conn.sendall(data)

        # 鼠标左键
        def LeftDown(e):
            print('LeftDown')
            # 获取当前连接的缩放比例
            scale = self.get_scale(conn)
            return EventDo(struct.pack('>BBHH', 1, 100, int(e.x / scale), int(e.y / scale)))

        def LeftUp(e):
            print('LeftUp')
            # 获取当前连接的缩放比例
            scale = self.get_scale(conn)
            return EventDo(struct.pack('>BBHH', 1, 117, int(e.x / scale), int(e.y / scale)))

        canvas.bind(sequence="<1>", func=LeftDown)
        canvas.bind(sequence="<ButtonRelease-1>", func=LeftUp)

        # 鼠标右键
        def RightDown(e):
            print('RightDown')
            # 获取当前连接的缩放比例
            scale = self.get_scale(conn)
            return EventDo(struct.pack('>BBHH', 3, 100, int(e.x / scale), int(e.y / scale)))

        def RightUp(e):
            print('RightUp')
            # 获取当前连接的缩放比例
            scale = self.get_scale(conn)
            return EventDo(struct.pack('>BBHH', 3, 117, int(e.x / scale), int(e.y / scale)))

        canvas.bind(sequence="<3>", func=RightDown)
        canvas.bind(sequence="<ButtonRelease-3>", func=RightUp)

        # 鼠标滚轮
        if PLAT == b'win' or PLAT == 'osx':
            # windows/mac
            def Wheel(e):
                # 获取当前连接的缩放比例
                scale = self.get_scale(conn)
                if e.delta < 0:
                    return EventDo(struct.pack('>BBHH', 2, 0, int(e.x / scale), int(e.y / scale)))
                else:
                    return EventDo(struct.pack('>BBHH', 2, 1, int(e.x / scale), int(e.y / scale)))

            canvas.bind(sequence="<MouseWheel>", func=Wheel)
        elif PLAT == b'x11':
            def WheelDown(e):
                # 获取当前连接的缩放比例
                scale = self.get_scale(conn)
                return EventDo(struct.pack('>BBHH', 2, 0, int(e.x / scale), int(e.y / scale)))

            def WheelUp(e):
                # 获取当前连接的缩放比例
                scale = self.get_scale(conn)
                return EventDo(struct.pack('>BBHH', 2, 1, int(e.x / scale), int(e.y / scale)))

            canvas.bind(sequence="<Button-4>", func=WheelUp)
            canvas.bind(sequence="<Button-5>", func=WheelDown)

        # 鼠标滑动
        # 100ms发送一次
        def Move(e):
            print('Move')
            print(e.x, e.y)
            # 获取当前连接的缩放比例
            scale = self.get_scale(conn)
            global last_send
            cu = time.time()
            if cu - last_send > IDLE:
                last_send = cu
                sx, sy = int(e.x / scale), int(e.y / scale)
                return EventDo(struct.pack('>BBHH', 4, 0, sx, sy))

        canvas.bind(sequence="<Motion>", func=Move)

        # 键盘
        def KeyDown(e):
            print('KeyDown')
            # 获取当前连接的缩放比例
            scale = self.get_scale(conn)
            return EventDo(struct.pack('>BBHH', e.keycode, 100, int(e.x / scale), int(e.y / scale)))

        def KeyUp(e):
            print('KeyUp')
            # 获取当前连接的缩放比例
            scale = self.get_scale(conn)
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