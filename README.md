# 基于Python的远程桌面监控软件


## 控制端

![](imgs/1.png)


## 被控端

![](imgs/2.png)


## 监控界面

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


# 参考

控制流数据实现参考了 [L.Chen 的 remote-desktop](https://github.com/pysrc/remote-desktop) 代码。
