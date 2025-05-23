# 基于Python的远程桌面监控软件


## 控制端

> 默认无需修改监听地址和端口

![](imgs/1.png)


## 被控端

> 填写`控制端的`内网`IP地址`和监听`端口`，启动连接后会如遇到网络问题导致连接断开10s后会自动重连，无需人为介入。
> 
> 如果使用考试客户端软件，建议自行修改该被控端的exe文件的名字来迷惑考试客户端软件的进程扫描行为，如`SoftwareUpdate.exe`。
>
> 隐藏窗口后，用完了可以通过任务管理器杀进程来结束程序。
> 
> 如需在互联网环境下使用内网穿透软件，如frp，可以参考最下面的教程。
>

![](imgs/2.png)


## 监控界面

可以同时监控多个电脑。

![](imgs/3.png)


# 开发环境

```plain
python 3.8.20
```

```bash
pip install -r requirements.txt
```

```plain
# 依赖包如下
auto-py-to-exe==2.46.0
keyboard==0.13.5
mouse==0.7.1
mss==9.0.2
numpy==1.22.1
opencv-python==4.5.5.62
Pillow==9.0.0
PyAutoGUI==0.9.54
pyinstaller==6.13.0
```

# 通过内网穿透实现互联网环境下的远程监控

## 前提条件

```plain
一台有公网IP的服务器（如果是国内的云服务器厂商务必记得开放你使用的端口，如默认的54321监听端口、frp的默认监听端口7000）
```

## 服务器部署Frp内网穿透

1. 下载[frp压缩包](https://github.com/fatedier/frp)，解压，如 `frp_0.62.1_linux_amd64.tar.gz`：

```bash
wget https://github.com/fatedier/frp/releases/download/v0.62.1/frp_0.62.1_linux_amd64.tar.gz
tar -xzvf frp_0.62.1_linux_amd64.tar.gz
cd frp_0.62.1_linux_amd64

```

2. 修改frp服务端配置文件`frps.toml`：

```bash
# frp服务端口
bindPort = 7000
# 连接的密码
auth.token = "xxxxxxxxxxxxxxxxx"
```

3. 添加systemd管理的启动服务frps.service

```bash
vim /etc/systemd/system/frps.service
```

frps.service文件内容：
```
[Unit]
# 服务名称，可自定义
Description = frp server
After = network.target syslog.target
Wants = network.target

[Service]
Type = simple
# 启动frps的命令，需修改为您的frps的文件夹路径
ExecStart = /root/frp_0.62.1_linux_amd64/frps -c /root/frp_0.62.1_linux_amd64/frps.toml

[Install]
WantedBy = multi-user.target

```

4. 启动frp服务

```bash
systemctl start frps
```

5. 查看frp运行状态

```bash
systemctl status frps
```

```plain
● frps.service - frp server
     Loaded: loaded (/etc/systemd/system/frps.service; enabled; vendor preset: enabled)
     Active: active (running) since Wed 2025-05-07 20:14:58 CST; 2 weeks 1 day ago
   Main PID: 746 (frps)
      Tasks: 6 (limit: 976)
     Memory: 14.0M
        CPU: 1min 45.006s
     CGroup: /system.slice/frps.service
             └─746 /root/frp_0.62.1_linux_amd64/frps -c /root/frp_0.62.1_linux_amd64/frps.toml
```


## 本地安装FrpDesktop客户端连接服务器

1. 下载[FrpDesktop客户端](https://github.com/luckjiawei/frpc-desktop) 到本地电脑安装。

2. 下载frp，版本要和服务器一致。

![image](https://github.com/user-attachments/assets/dfb0ab4f-a44d-4ef4-9744-4394c9c3860e)

3. 配置frp服务。

![image](https://github.com/user-attachments/assets/bdafef2c-686e-474f-bcf1-e9492eb3bafc)

![image](https://github.com/user-attachments/assets/3c402434-0337-4987-aea3-9ca9446bbb85)


4. 添加一个连接监听配置。

![image](https://github.com/user-attachments/assets/acba201a-2275-4550-99dc-2553a1e98d1d)

![image](https://github.com/user-attachments/assets/0d74908e-48c5-4795-bde7-1f274cedb1fc)

5. 启动，连接服务器

![image](https://github.com/user-attachments/assets/18b2057c-93a1-4805-9150-39549517baa5)

![image](https://github.com/user-attachments/assets/47687fba-5970-4180-9a09-8ff91f9b4aa6)


## 使用

此时，`被控端`需要填写`服务器`的`IP地址`和监听`端口`。


# 参考

控制流数据实现参考了 [L.Chen 的 remote-desktop](https://github.com/pysrc/remote-desktop) 代码。


# 注意

控制功能并不完善，仅鼠标点击正常，键盘控制输入目前仍待改进。
