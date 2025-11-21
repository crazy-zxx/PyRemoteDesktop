# 基于Python的远程桌面监控软件

---
## 控制端

> 在同一网段的内网中，默认不用做任何配置修改。

> 在互联网环境下，推荐自行购买公网VPS服务器来搭建frp内网穿透服务:
> 
> `FRP服务器地址` 填写`VPS服务器` 的 `公网IP地址`
> 
> `FRP连接token` 填写`VPS服务器` 的 `FRP连接token`
> 
> `远程访问端口`随便填
> 
> `本地监听端口`保持和`监听端口`一致

![](imgs/1.png)


---
## 被控端

> 在同一网段的内网中，`目标地址` 直接填写 `控制端` 的 `内网IP地址` 和 `监听端口`。

> 在互联网环境下，推荐自行购买公网VPS服务器来搭建frp内网穿透服务:
> 
> `目标地址` 填写`VPS服务器` 的 `公网IP地址`
> 
> `目标端口` 填写`VPS服务器` 的 `远程访问端口`

> 启动连接后会如遇到网络问题导致连接断开 `10s` 后会自动重连到控制端，无需人为介入。
> 
> 如果考试使用客户端软件，建议自行修改该被控端的exe文件名来迷惑考试客户端软件的进程扫描行为，如`WindowsUpdate.exe`。
>
> 隐藏窗口后，只能通过任务管理器杀进程来结束程序。
> 


![](imgs/2.png)

---

## 监控界面

可以同时监控多个电脑。

![](imgs/3.png)

---

# 开发环境

```plain
python 3.8
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

---

# 通过内网穿透实现互联网环境下的远程监控

## 前提条件

```plain
一台有公网IP的服务器（如果是国内的云服务器厂商务必记得开放你使用的端口，如默认的54321监听端口、frp的默认监听端口7000）
```

## 服务器部署Frp内网穿透

1. 下载[frp压缩包](https://github.com/fatedier/frp)，解压，如 `frp_0.65.0_linux_amd64.tar.gz`：

```bash
wget https://github.com/fatedier/frp/releases/download/v0.65.0/frp_0.65.0_linux_amd64.tar.gz
tar -xzvf frp_0.65.0_linux_amd64.tar.gz
cd frp_0.65.0_linux_amd64

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
ExecStart = /root/frp_0.65.0_linux_amd64/frps -c /root/frp_0.65.0_linux_amd64/frps.toml

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
             └─746 /root/frp_0.65.0_linux_amd64/frps -c /root/frp_0.65.0_linux_amd64/frps.toml
```



---
# 致谢

控制流数据实现参考了 [L.Chen 的 remote-desktop](https://github.com/pysrc/remote-desktop) 代码。


