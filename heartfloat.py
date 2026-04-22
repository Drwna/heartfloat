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
icon_label = None         # 心率图标 Label
bpm_label = None          # BPM 文本 Label
status_var = None         # 状态栏文本变量
status_view_var = None    # 状态栏显示文本变量（用于悬停显示控制）
loop = None               # asyncio 事件循环
client = None             # BleakClient 实例
is_connected = False      # 连接状态标志
is_connecting = False     # 正在连接状态标志
is_hovering = False       # 鼠标是否悬停在窗口上
manual_disconnect_requested = False  # 是否由用户手动触发断开
AUTO_RECONNECT_DELAY_MS = 3000       # 意外断开后的自动重连延时
TRANSPARENT_COLOR = "#fefefe"       # Windows 透明色键（白色背景下可避免黑边）

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

    def update_hr_ui():
        if label:
            label.config(text=str(hr))

    # 更新 UI（需通过 tkinter 线程安全方式）
    if root and root.winfo_exists():
        root.after(0, update_hr_ui)

# ================== 蓝牙连接任务 ==================
async def scan_and_connect():
    """扫描并连接心率设备"""
    global client, is_connected, manual_disconnect_requested
    manual_disconnect_requested = False
    was_connected_once = False
    update_status("正在扫描蓝牙设备(5秒)")

    # 扫描设备，超时 5 秒
    devices = await BleakScanner.discover(timeout=5.0, return_adv=True)
    print(f"扫描完成，找到 {len(devices)} 个设备")

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

    if target_device.name is None:
        update_status("请重试")
        return

    update_status(f"正在连接 {target_device.name}...")

    def on_disconnected(_):
        """设备断开时回调（由 Bleak 在线程中触发）"""
        global is_connected
        is_connected = False
        if label:
            label.after(0, lambda: label.config(text="--"))
        if manual_disconnect_requested:
            update_status("设备已断开")
        else:
            update_status("意外断开，准备自动重连")

    try:
        client = BleakClient(
            target_device.address,
            timeout=10.0,
            disconnected_callback=on_disconnected,
        )
        await client.connect()
        is_connected = True
        was_connected_once = True
        update_status(f"已连接 {target_device.name}")

        # 启动心率通知
        await client.start_notify(HEART_RATE_MEASUREMENT_UUID, notification_handler)

        # 保持连接直到用户断开或设备断连
        while is_connected and client.is_connected:
            await asyncio.sleep(1)

    except BleakError as e:
        update_status(f"连接失败: {e}")
    except Exception as e:
        update_status(f"未知错误: {e}")
    finally:
        if client:
            try:
                await client.stop_notify(HEART_RATE_MEASUREMENT_UUID)
            except Exception:
                pass
            try:
                if client.is_connected:
                    await client.disconnect()
            except Exception:
                pass
        is_connected = False
        client = None
        if label:
            label.after(0, lambda: label.config(text="--"))
        if (was_connected_once and not manual_disconnect_requested and root and root.winfo_exists()):
            update_status(f"{AUTO_RECONNECT_DELAY_MS // 1000} 秒后自动重连...")
            root.after(AUTO_RECONNECT_DELAY_MS, start_connection_thread)
        else:
            update_status("已断开，点击「连接设备」重试")

# ================== UI 更新辅助函数 ==================
def update_status(text):
    """线程安全地更新状态栏"""
    if status_var and root and root.winfo_exists():
        def update_status_text():
            status_var.set(text)
            if status_view_var:
                status_view_var.set(text if is_hovering else "")
        root.after(0, update_status_text)
    print(f"[状态] {text}")

def start_connection_thread():
    """在新线程中启动 asyncio 事件循环"""
    global loop, is_connecting
    if is_connected:
        messagebox.showinfo("提示", "设备已连接")
        return
    if is_connecting:
        messagebox.showinfo("提示", "正在连接中，请稍候")
        return

    # 创建新的事件循环（每个线程需要独立的 loop）
    new_loop = asyncio.new_event_loop()
    loop = new_loop
    is_connecting = True
    t = threading.Thread(target=run_async_loop, args=(new_loop,), daemon=True)
    t.start()

def run_async_loop(loop):
    """在新线程中运行 asyncio 事件循环"""
    global is_connecting
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(scan_and_connect())
    finally:
        is_connecting = False
        loop.close()

def disconnect_device():
    """手动断开连接"""
    global is_connected, manual_disconnect_requested
    if client and is_connected and loop and not loop.is_closed():
        manual_disconnect_requested = True
        # 在事件循环中执行断开操作
        asyncio.run_coroutine_threadsafe(disconnect_coro(), loop)
        is_connected = False
        update_status("正在断开连接...")

async def disconnect_coro():
    """协程：停止通知并断开连接"""
    try:
        await client.stop_notify(HEART_RATE_MEASUREMENT_UUID)
        await client.disconnect()
    except Exception:
        pass

# ================== 创建悬浮窗 UI ==================
def create_window():
    global root, label, icon_label, bpm_label, status_var, status_view_var, is_hovering
    root = tk.Tk()
    root.title("heartfloat")
    root.geometry("200x80+100+100")  # 宽x高+X+Y
    root.overrideredirect(True)       # 去掉标题栏，实现无边框
    root.attributes("-topmost", True) # 窗口置顶
    normal_bg = "#171a24"
    status_bg = "#121520"
    root.configure(bg=normal_bg)

    card = tk.Frame(root, bg=normal_bg, highlightthickness=0, bd=0)
    card.pack(expand=True, fill="both")

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
    card.bind("<Button-1>", start_move)
    card.bind("<B1-Motion>", do_move)

    center_row = tk.Frame(card, bg=normal_bg)
    center_row.pack(expand=True)

    icon_box = tk.Frame(center_row, width=30, height=30, bg=normal_bg)
    icon_box.pack(side="left")
    icon_box.pack_propagate(False)

    icon_label = tk.Label(icon_box, text="❤", font=("Segoe UI Emoji", 16, "bold"), fg="#ff2d55", bg=normal_bg)
    icon_label.place(relx=0.5, rely=0.5, anchor="center")

    # 大号心率数字
    label = tk.Label(center_row, text="--", font=("Segoe UI", 28, "bold"),
                     fg="#49f08f", bg=normal_bg)
    label.pack(side="left", padx=(6, 0))

    # 状态栏（显示连接状态）
    status_var = tk.StringVar()
    status_var.set("就绪")
    status_view_var = tk.StringVar()
    status_view_var.set("就绪")
    status_container = tk.Frame(card, bg=status_bg, height=20)
    status_container.pack(side="bottom", fill="x", padx=6, pady=(0, 6))
    status_container.pack_propagate(False)

    status_bar = tk.Label(status_container, textvariable=status_view_var, font=("Consolas", 9, "bold"),
                          fg="#c8d1dc", bg=status_bg, anchor="w")
    status_bar.pack(fill="both", padx=5)

    def set_hover_state(hovered):
        global is_hovering
        is_hovering = hovered
        if hovered:
            root.wm_attributes("-transparentcolor", "")
            root.configure(bg=normal_bg)
            card.configure(bg=normal_bg)
            center_row.configure(bg=normal_bg)
            icon_box.configure(bg=normal_bg)
            icon_label.configure(bg=normal_bg)
            label.configure(bg=normal_bg)
            status_container.configure(bg=status_bg)
            status_bar.configure(bg=status_bg, fg="#c8d1dc")
            status_view_var.set(status_var.get())
        else:
            root.configure(bg=TRANSPARENT_COLOR)
            card.configure(bg=TRANSPARENT_COLOR)
            center_row.configure(bg=TRANSPARENT_COLOR)
            icon_box.configure(bg=TRANSPARENT_COLOR)
            icon_label.configure(bg=TRANSPARENT_COLOR)
            label.configure(bg=TRANSPARENT_COLOR)
            status_container.configure(bg=TRANSPARENT_COLOR)
            status_bar.configure(bg=TRANSPARENT_COLOR, fg=TRANSPARENT_COLOR)
            status_view_var.set("")
            root.wm_attributes("-transparentcolor", TRANSPARENT_COLOR)

    def on_mouse_enter(_event):
        set_hover_state(True)

    def on_mouse_leave(_event):
        set_hover_state(False)

    root.bind("<Enter>", on_mouse_enter)
    root.bind("<Leave>", on_mouse_leave)

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
        label.config(fg="#ff6b7d" if current == "#49f08f" else "#49f08f")
    label.bind("<Double-Button-1>", toggle_color)

    # 启动时默认隐藏背景与状态栏，鼠标移入再显示
    set_hover_state(False)

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