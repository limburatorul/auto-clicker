"""Everything that talks to Windows directly: input, hotkeys, window effects,
screen capture. Kept in one place so the rest of the app stays plain Qt/Python."""

import ctypes
from ctypes import wintypes

import numpy as np

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
dwmapi = ctypes.windll.dwmapi
winmm = ctypes.windll.winmm

ULONG_PTR = ctypes.c_uint64 if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_uint32

INPUT_MOUSE = 0
BUTTON_FLAGS = {
    "left": (0x0002, 0x0004),
    "right": (0x0008, 0x0010),
    "middle": (0x0020, 0x0040),
}

WM_HOTKEY = 0x0312
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN = 0x1, 0x2, 0x4, 0x8
MOD_NOREPEAT = 0x4000

SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN = 76, 77
SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 78, 79
SRCCOPY = 0x00CC0020
CAPTUREBLT = 0x40000000
DIB_RGB_COLORS = 0


# --- input ----------------------------------------------------------------

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT)]
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT
user32.RegisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT)
user32.UnregisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int)


def _mouse_event(flags):
    event = INPUT()
    event.type = INPUT_MOUSE
    event.mi = MOUSEINPUT(0, 0, 0, flags, 0, 0)
    return event


# A down/up pair with no coordinates clicks wherever the cursor already is.
_CLICKS = {name: (INPUT * 2)(_mouse_event(down), _mouse_event(up))
           for name, (down, up) in BUTTON_FLAGS.items()}


def click(button="left"):
    pair = _CLICKS[button]
    user32.SendInput(2, pair, ctypes.sizeof(INPUT))


def move_to(x, y):
    user32.SetCursorPos(int(x), int(y))


def cursor_pos():
    point = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y


def begin_precise_timing():
    """Without this a sleep rounds up to the ~15.6 ms scheduler tick."""
    winmm.timeBeginPeriod(1)


def end_precise_timing():
    winmm.timeEndPeriod(1)


# --- hotkeys --------------------------------------------------------------

def register_hotkey(hwnd, hotkey_id, mods, vk):
    handle = wintypes.HWND(hwnd)
    user32.UnregisterHotKey(handle, hotkey_id)
    return bool(user32.RegisterHotKey(handle, hotkey_id, mods | MOD_NOREPEAT, vk))


def unregister_hotkey(hwnd, hotkey_id):
    user32.UnregisterHotKey(wintypes.HWND(hwnd), hotkey_id)


# --- window effects -------------------------------------------------------
# Acrylic is a DWM effect: it has to be asked of the window, QSS cannot reach
# behind the window surface. See vault note "Styling".

class ACCENT_POLICY(ctypes.Structure):
    _fields_ = [("AccentState", ctypes.c_int), ("AccentFlags", ctypes.c_int),
                ("GradientColor", ctypes.c_uint), ("AnimationId", ctypes.c_int)]


class WINDOWCOMPOSITIONATTRIBDATA(ctypes.Structure):
    _fields_ = [("Attribute", ctypes.c_int), ("Data", ctypes.POINTER(ACCENT_POLICY)),
                ("SizeOfData", ctypes.c_size_t)]


def apply_acrylic(hwnd, gradient=0x3826221C):
    """gradient is AABBGGRR - a near-black tint over the blurred desktop."""
    accent = ACCENT_POLICY(4, 0, gradient, 0)  # ACCENT_ENABLE_ACRYLICBLURBEHIND
    data = WINDOWCOMPOSITIONATTRIBDATA(19, ctypes.pointer(accent), ctypes.sizeof(accent))
    user32.SetWindowCompositionAttribute(wintypes.HWND(hwnd), ctypes.byref(data))
    dwmapi.DwmSetWindowAttribute(  # DWMWA_WINDOW_CORNER_PREFERENCE = round
        wintypes.HWND(hwnd), 33, ctypes.byref(ctypes.c_int(2)), 4)


# --- screen capture -------------------------------------------------------

class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


def virtual_screen():
    """Physical pixel bounds covering every monitor."""
    return (user32.GetSystemMetrics(SM_XVIRTUALSCREEN),
            user32.GetSystemMetrics(SM_YVIRTUALSCREEN),
            user32.GetSystemMetrics(SM_CXVIRTUALSCREEN),
            user32.GetSystemMetrics(SM_CYVIRTUALSCREEN))


def grab_screen(region=None):
    """Return a BGR numpy array of the screen, or of (x, y, w, h)."""
    x, y, width, height = region if region else virtual_screen()
    width, height = max(1, int(width)), max(1, int(height))

    screen_dc = user32.GetDC(0)
    mem_dc = gdi32.CreateCompatibleDC(screen_dc)
    bitmap = gdi32.CreateCompatibleBitmap(screen_dc, width, height)
    old = gdi32.SelectObject(mem_dc, bitmap)
    try:
        gdi32.BitBlt(mem_dc, 0, 0, width, height, screen_dc,
                     int(x), int(y), SRCCOPY | CAPTUREBLT)
        info = BITMAPINFO()
        info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        info.bmiHeader.biWidth = width
        info.bmiHeader.biHeight = -height  # negative: top-down rows
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        buffer = (ctypes.c_ubyte * (width * height * 4))()
        gdi32.GetDIBits(mem_dc, bitmap, 0, height, buffer,
                        ctypes.byref(info), DIB_RGB_COLORS)
    finally:
        gdi32.SelectObject(mem_dc, old)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(0, screen_dc)

    frame = np.frombuffer(buffer, dtype=np.uint8).reshape(height, width, 4)
    return frame[:, :, :3].copy()


def pixel_color(x, y):
    """(r, g, b) at a physical screen coordinate."""
    frame = grab_screen((x, y, 1, 1))
    blue, green, red = frame[0, 0]
    return int(red), int(green), int(blue)
