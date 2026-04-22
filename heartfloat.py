import asyncio
import threading
import tkinter as tk
from tkinter import messagebox
from bleak import BleakScanner, BleakClient, BleakError

# ================== 蓝牙 UUID 常量 ==================
HEART_RATE_SERVICE_UUID = "0000180d-0000-1000-8000-00805f9b34fb"
HEART_RATE_MEASUREMENT_UUID = "00002a37-0000-1000-8000-00805f9b34fb"

# ================== 全局变量 ==================
root = None               # tkinter 根窗口
label = None              # 显示心率的 Label
status_var = None         # 状态栏文本变量
loop = None               # asyncio 事件循环
client = None             # BleakClient 实例
is_connected = False      # 连接状态标志

# ================== 心率解析函数 ==================
def parse_heart_rate(data):
    """解析心率测量特征的数据，返回心率值 (BPM)"""
    flags = data[0]
    # 检查心率值格式：bit 0 为 0 表示 UINT8，为 1 表示 UINT16
    if flags & 0x01 == 0:
        hr = data[1]
    else:
        hr = int.from_bytes(data[1:3], byteorder='little')
    return hr

# ================== 蓝牙通知回调 ==================
def notification_handler(sender, data):
    """接收到心率数据时的回调"""
    hr = parse_heart_rate(data)
    # 更新 UI（需通过 tkinter 线程安全方式）
    if label:
        label.after(0, lambda: label.config(text=str(hr)))
    print(f"❤️ 心率: {hr} BPM")

# ================== 蓝牙连接任务 ==================
async def scan_and_connect():
    """扫描并连接心率设备"""
    global client, is_connected
    update_status("正在扫描蓝牙设备 (5秒)...")

    # 扫描设备，超时 5 秒
    devices = await BleakScanner.discover(timeout=5.0, return_adv=True)

    # 筛选可能的心率设备（可根据名称关键字调整）
    target_device = None
    for addr, (dev, adv_data) in devices.items():
        name = dev.name if dev.name else ""
        # 常见手环/心率带名称特征
        if any(k in name.lower() for k in ["mi band", "honor band", "huawei band", "hr", "heart", "polar", "wahoo", "tickr"]):
            target_device = dev
            break
    if target_device is None and devices:
        # 若没找到特征名，选择第一个蓝牙设备（不一定正确）
        target_device = list(devices.values())[0][0]

    if target_device is None:
        update_status("未找到任何蓝牙设备，请确保手环已开启心率广播")
        return

    update_status(f"正在连接 {target_device.name} ({target_device.address})...")

    try:
        async with BleakClient(target_device.address, timeout=10.0) as c:
            client = c
            is_connected = True
            update_status(f"已连接 {target_device.name}，等待心率数据...")

            # 启动心率通知
            await client.start_notify(HEART_RATE_MEASUREMENT_UUID, notification_handler)

            # 保持连接直到用户断开或异常
            while is_connected:
                await asyncio.sleep(1)

    except BleakError as e:
        update_status(f"连接失败: {e}")
    except Exception as e:
        update_status(f"未知错误: {e}")
    finally:
        is_connected = False
        client = None
        if label:
            label.after(0, lambda: label.config(text="--"))
        update_status("连接已断开，点击「连接设备」重试")

# ================== UI 更新辅助函数 ==================
def update_status(text):
    """线程安全地更新状态栏"""
    if status_var:
        root.after(0, lambda: status_var.set(text))
    print(f"[状态] {text}")

def start_connection_thread():
    """在新线程中启动 asyncio 事件循环"""
    if is_connected:
        messagebox.showinfo("提示", "设备已连接")
        return

    # 创建新的事件循环（每个线程需要独立的 loop）
    new_loop = asyncio.new_event_loop()
    t = threading.Thread(target=run_async_loop, args=(new_loop,), daemon=True)
    t.start()

def run_async_loop(loop):
    """在新线程中运行 asyncio 事件循环"""
    asyncio.set_event_loop(loop)
    loop.run_until_complete(scan_and_connect())

def disconnect_device():
    """手动断开连接"""
    global is_connected
    if client and is_connected:
        # 在事件循环中执行断开操作
        asyncio.run_coroutine_threadsafe(disconnect_coro(), loop)
        is_connected = False
        update_status("正在断开连接...")

async def disconnect_coro():
    """协程：停止通知并断开连接"""
    try:
        await client.stop_notify(HEART_RATE_MEASUREMENT_UUID)
        await client.disconnect()
    except:
        pass

# ================== 创建悬浮窗 UI ==================
def create_window():
    global root, label, status_var
    root = tk.Tk()
    root.title("心率悬浮窗")
    root.geometry("200x120+100+100")  # 宽x高+X+Y
    root.overrideredirect(True)       # 去掉标题栏，实现无边框
    root.attributes("-topmost", True) # 窗口置顶
    root.configure(bg="black")

    # 允许窗口拖动
    def start_move(event):
        root.x = event.x
        root.y = event.y
    def do_move(event):
        dx = event.x - root.x
        dy = event.y - root.y
        x = root.winfo_x() + dx
        y = root.winfo_y() + dy
        root.geometry(f"+{x}+{y}")
    root.bind("<Button-1>", start_move)
    root.bind("<B1-Motion>", do_move)

    # 大号心率数字
    label = tk.Label(root, text="--", font=("Arial", 48, "bold"),
                     fg="#00FF00", bg="black")
    label.pack(expand=True, fill="both")

    # 状态栏（显示连接状态）
    status_var = tk.StringVar()
    status_var.set("就绪")
    status_bar = tk.Label(root, textvariable=status_var, font=("Arial", 9),
                          fg="gray", bg="black")
    status_bar.pack(side="bottom", fill="x")

    # 右键菜单
    menu = tk.Menu(root, tearoff=0)
    menu.add_command(label="连接设备", command=start_connection_thread)
    menu.add_command(label="断开连接", command=disconnect_device)
    menu.add_separator()
    menu.add_command(label="退出", command=root.quit)
    def show_menu(event):
        menu.post(event.x_root, event.y_root)
    root.bind("<Button-3>", show_menu)

    # 双击切换颜色（可选小功能）
    def toggle_color(event):
        current = label.cget("fg")
        label.config(fg="#FF0000" if current == "#00FF00" else "#00FF00")
    label.bind("<Double-Button-1>", toggle_color)

    # 启动 tkinter 主循环
    root.mainloop()

# ================== 程序入口 ==================
if __name__ == "__main__":
    # 提示用户开启手环心率广播
    print("=" * 50)
    print("请确保手环已开启「心率广播」功能")
    print("（通常在手机 App 的设备设置中）")
    print("=" * 50)
    create_window()