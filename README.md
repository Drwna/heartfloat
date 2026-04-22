# heartfloat

一个基于 `tkinter + bleak` 的 Windows 心率悬浮窗小工具。

程序会扫描并连接蓝牙心率设备（如心率带/手环），在桌面显示实时 BPM。

## 功能特性

- 无边框、置顶悬浮窗
- 右键菜单：连接设备 / 断开连接 / 退出
- 支持意外断开后自动重连
- 鼠标悬停显示状态栏，移出时进入透明展示模式

## 运行环境

- 操作系统：Windows（推荐）
- Python：3.10+
- 蓝牙：设备需支持标准心率服务（GATT Heart Rate Service）

## 安装依赖

在项目根目录执行：

```bash
pip install bleak pyinstaller
```

如果你使用虚拟环境（推荐）：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -U pip
pip install bleak pyinstaller
```

## 开发运行

```bash
python heartfloat.py
```

启动后：

1. 右键悬浮窗，点击“连接设备”
2. 确保手环/心率带已开启心率广播
3. 成功连接后会显示实时 BPM

## 打包命令（PyInstaller）

使用以下命令打包：

```bash
pyinstaller --noconfirm --clean --onefile --windowed --name heartfloat --icon heartfloat.ico heartfloat.py
```

说明：

- `--onefile`：打包为单个 exe 文件
- `--windowed`：隐藏控制台窗口（GUI 程序常用）
- `--icon`：设置程序图标

输出目录：

- `dist/heartfloat.exe`：最终可执行文件
- `build/`：中间构建文件

## 目录说明

- `heartfloat.py`：主程序
- `heartfloat.ico`：应用图标
- `dist/`：打包产物
- `build/`：构建缓存

## 常见问题

### 1) 扫描不到设备

- 检查系统蓝牙是否开启
- 检查设备是否支持心率广播
- 先在手机 App 中开启心率广播功能

### 2) 连接后没有心率数据

- 确认设备正在佩戴并有心率输出
- 尝试断开后重新连接
- 避免被其他 App 长时间独占蓝牙连接

### 3) 打包后运行失败

- 先在本机直接运行 `python heartfloat.py` 确认逻辑正常
- 重新打包前清理缓存：

```bash
rmdir /s /q build
pyinstaller --noconfirm --clean --onefile --windowed --name heartfloat --icon heartfloat.ico heartfloat.py
```

## 许可

如需开源发布，请补充你的许可证（例如 MIT）。
