"""
Startup splash-screen helpers.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import sys
import time
from pathlib import Path
import tkinter as tk

from PIL import Image, ImageTk

from wifi_pref_manager.paths import AppPaths


DEFAULT_SPLASH_FILENAME = 'polyfi_ranked_splash.png'
TRANSPARENT_KEY_HEX = '#01ff02'
TRANSPARENT_KEY_RGB = (1, 255, 2)


def resolve_splash_image_path(configured_path: str, app_paths: AppPaths) -> Path | None:
    """
    Resolve the splash image path from config and common defaults.

    Parameters:
        configured_path:
            Configured splash image path.
        app_paths:
            Application paths helper.

    Returns:
        Existing splash image path, or ``None`` if no candidate exists.
    """
    configured = configured_path.strip()
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.exists():
            return candidate

    candidates = [
        app_paths.local_data_dir / DEFAULT_SPLASH_FILENAME,
        Path.home() / 'OneDrive' / 'Pictures' / DEFAULT_SPLASH_FILENAME,
        Path.home() / 'Pictures' / DEFAULT_SPLASH_FILENAME,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _prepare_chroma_key_image(rgba_image: Image.Image) -> Image.Image:
    """
    Convert an RGBA splash image into an RGB image keyed for transparent windows.

    Fully transparent pixels are mapped to ``TRANSPARENT_KEY_RGB`` so
    ``wm_attributes('-transparentcolor', ...)`` can punch them out.
    """
    key_rgba = (*TRANSPARENT_KEY_RGB, 255)
    keyed_image = Image.new('RGBA', rgba_image.size, key_rgba)
    keyed_image.paste(rgba_image, (0, 0), rgba_image)
    return keyed_image.convert('RGB')


def _premultiply_bgra_bytes(rgba_image: Image.Image) -> bytes:
    """
    Convert an RGBA image into premultiplied BGRA bytes for UpdateLayeredWindow.
    """
    pixels = bytearray()
    for red, green, blue, alpha in rgba_image.convert('RGBA').getdata():
        pixels.extend(
            (
                (blue * alpha + 127) // 255,
                (green * alpha + 127) // 255,
                (red * alpha + 127) // 255,
                alpha,
            )
        )
    return bytes(pixels)


def _open_splash_rgba(image_path: Path) -> Image.Image:
    """
    Open and resize the splash image to fit sensible desktop bounds.
    """
    with Image.open(image_path) as image:
        rgba_image = image.convert('RGBA')
        max_width = 900
        max_height = 560
        if rgba_image.width > max_width or rgba_image.height > max_height:
            rgba_image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
        return rgba_image.copy()


def _show_tk_fallback_splash(
    rgba_image: Image.Image,
    *,
    fade_in_ms: int,
    hold_ms: int,
    fade_out_ms: int,
) -> None:
    """
    Cross-platform fallback splash for environments without Win32 layered windows.
    """
    root = tk.Tk()
    splash_image = ImageTk.PhotoImage(rgba_image, master=root)
    root.overrideredirect(True)
    root.attributes('-topmost', True)
    root.configure(bg='black')

    label = tk.Label(
        root,
        image=splash_image,
        borderwidth=0,
        highlightthickness=0,
        bg='black',
    )
    label.image = splash_image
    label.pack()

    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() - width) // 2
    y = (root.winfo_screenheight() - height) // 2
    root.geometry(f'{width}x{height}+{x}+{y}')
    root.deiconify()
    root.update()

    del fade_in_ms
    del fade_out_ms

    if hold_ms > 0:
        time.sleep(hold_ms / 1000.0)
    root.destroy()


if sys.platform == 'win32':
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    kernel32 = ctypes.windll.kernel32
    WIN_LRESULT = ctypes.c_ssize_t
    WIN_HCURSOR = wintypes.HANDLE
    WIN_HBRUSH = wintypes.HANDLE

    AC_SRC_OVER = 0x00
    AC_SRC_ALPHA = 0x01
    BI_RGB = 0
    CS_HREDRAW = 0x0002
    CS_VREDRAW = 0x0001
    DIB_RGB_COLORS = 0
    PM_REMOVE = 0x0001
    SW_SHOWNOACTIVATE = 4
    ULW_ALPHA = 0x00000002
    WM_DESTROY = 0x0002
    WS_EX_LAYERED = 0x00080000
    WS_EX_TOOLWINDOW = 0x00000080
    WS_EX_TOPMOST = 0x00000008
    WS_POPUP = 0x80000000

    class POINT(ctypes.Structure):
        _fields_ = [('x', wintypes.LONG), ('y', wintypes.LONG)]

    class SIZE(ctypes.Structure):
        _fields_ = [('cx', wintypes.LONG), ('cy', wintypes.LONG)]

    class MSG(ctypes.Structure):
        _fields_ = [
            ('hwnd', wintypes.HWND),
            ('message', wintypes.UINT),
            ('wParam', wintypes.WPARAM),
            ('lParam', wintypes.LPARAM),
            ('time', wintypes.DWORD),
            ('pt', POINT),
        ]

    class WNDCLASSW(ctypes.Structure):
        _fields_ = [
            ('style', wintypes.UINT),
            ('lpfnWndProc', ctypes.WINFUNCTYPE(WIN_LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)),
            ('cbClsExtra', ctypes.c_int),
            ('cbWndExtra', ctypes.c_int),
            ('hInstance', wintypes.HINSTANCE),
            ('hIcon', wintypes.HICON),
            ('hCursor', WIN_HCURSOR),
            ('hbrBackground', WIN_HBRUSH),
            ('lpszMenuName', wintypes.LPCWSTR),
            ('lpszClassName', wintypes.LPCWSTR),
        ]

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ('biSize', wintypes.DWORD),
            ('biWidth', wintypes.LONG),
            ('biHeight', wintypes.LONG),
            ('biPlanes', wintypes.WORD),
            ('biBitCount', wintypes.WORD),
            ('biCompression', wintypes.DWORD),
            ('biSizeImage', wintypes.DWORD),
            ('biXPelsPerMeter', wintypes.LONG),
            ('biYPelsPerMeter', wintypes.LONG),
            ('biClrUsed', wintypes.DWORD),
            ('biClrImportant', wintypes.DWORD),
        ]

    class RGBQUAD(ctypes.Structure):
        _fields_ = [
            ('rgbBlue', wintypes.BYTE),
            ('rgbGreen', wintypes.BYTE),
            ('rgbRed', wintypes.BYTE),
            ('rgbReserved', wintypes.BYTE),
        ]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [
            ('bmiHeader', BITMAPINFOHEADER),
            ('bmiColors', RGBQUAD * 1),
        ]

    class BLENDFUNCTION(ctypes.Structure):
        _fields_ = [
            ('BlendOp', wintypes.BYTE),
            ('BlendFlags', wintypes.BYTE),
            ('SourceConstantAlpha', wintypes.BYTE),
            ('AlphaFormat', wintypes.BYTE),
        ]

    WNDPROC = ctypes.WINFUNCTYPE(
        WIN_LRESULT,
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    )

    user32.DefWindowProcW.argtypes = (
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    )
    user32.DefWindowProcW.restype = WIN_LRESULT
    user32.PostQuitMessage.argtypes = (ctypes.c_int,)
    user32.PostQuitMessage.restype = None


def _show_windows_layered_splash(
    rgba_image: Image.Image,
    *,
    fade_in_ms: int,
    hold_ms: int,
    fade_out_ms: int,
) -> None:
    """
    Show the splash through a native layered window with per-pixel PNG alpha.
    """
    if sys.platform != 'win32':
        _show_tk_fallback_splash(
            rgba_image,
            fade_in_ms=fade_in_ms,
            hold_ms=hold_ms,
            fade_out_ms=fade_out_ms,
        )
        return

    image = rgba_image.convert('RGBA')
    width, height = image.size
    image_bytes = _premultiply_bgra_bytes(image)

    def window_proc(
        hwnd: wintypes.HWND,
        message: wintypes.UINT,
        w_param: wintypes.WPARAM,
        l_param: wintypes.LPARAM,
    ) -> int:
        if message == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, message, w_param, l_param)

    wndproc = WNDPROC(window_proc)
    class_name = f'PolyFiRankedSplashWindow{time.time_ns()}'
    instance = kernel32.GetModuleHandleW(None)

    window_class = WNDCLASSW()
    window_class.style = CS_HREDRAW | CS_VREDRAW
    window_class.lpfnWndProc = wndproc
    window_class.hInstance = instance
    window_class.lpszClassName = class_name

    if not user32.RegisterClassW(ctypes.byref(window_class)):
        raise ctypes.WinError()

    screen_dc = user32.GetDC(None)
    memory_dc = None
    bitmap = None
    old_bitmap = None
    hwnd = None

    try:
        bitmap_info = BITMAPINFO()
        bitmap_info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bitmap_info.bmiHeader.biWidth = width
        bitmap_info.bmiHeader.biHeight = -height
        bitmap_info.bmiHeader.biPlanes = 1
        bitmap_info.bmiHeader.biBitCount = 32
        bitmap_info.bmiHeader.biCompression = BI_RGB

        bits = ctypes.c_void_p()
        bitmap = gdi32.CreateDIBSection(
            screen_dc,
            ctypes.byref(bitmap_info),
            DIB_RGB_COLORS,
            ctypes.byref(bits),
            None,
            0,
        )
        if not bitmap:
            raise ctypes.WinError()

        ctypes.memmove(bits.value, image_bytes, len(image_bytes))
        memory_dc = gdi32.CreateCompatibleDC(screen_dc)
        if not memory_dc:
            raise ctypes.WinError()

        old_bitmap = gdi32.SelectObject(memory_dc, bitmap)
        if not old_bitmap:
            raise ctypes.WinError()

        x = (user32.GetSystemMetrics(0) - width) // 2
        y = (user32.GetSystemMetrics(1) - height) // 2
        hwnd = user32.CreateWindowExW(
            WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW,
            class_name,
            '',
            WS_POPUP,
            x,
            y,
            width,
            height,
            None,
            None,
            instance,
            None,
        )
        if not hwnd:
            raise ctypes.WinError()

        user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)

        destination = POINT(x, y)
        source = POINT(0, 0)
        size = SIZE(width, height)

        def pump_messages() -> None:
            message = MSG()
            while user32.PeekMessageW(ctypes.byref(message), None, 0, 0, PM_REMOVE):
                user32.TranslateMessage(ctypes.byref(message))
                user32.DispatchMessageW(ctypes.byref(message))

        def update_window(alpha: int) -> None:
            blend = BLENDFUNCTION(AC_SRC_OVER, 0, alpha, AC_SRC_ALPHA)
            if not user32.UpdateLayeredWindow(
                hwnd,
                screen_dc,
                ctypes.byref(destination),
                ctypes.byref(size),
                memory_dc,
                ctypes.byref(source),
                0,
                ctypes.byref(blend),
                ULW_ALPHA,
            ):
                raise ctypes.WinError()
            pump_messages()

        del fade_in_ms
        del fade_out_ms

        update_window(255)
        if hold_ms > 0:
            deadline = time.perf_counter() + (hold_ms / 1000.0)
            while time.perf_counter() < deadline:
                pump_messages()
                time.sleep(0.01)
    finally:
        if hwnd:
            user32.DestroyWindow(hwnd)
        if memory_dc and old_bitmap:
            gdi32.SelectObject(memory_dc, old_bitmap)
        if bitmap:
            gdi32.DeleteObject(bitmap)
        if memory_dc:
            gdi32.DeleteDC(memory_dc)
        if screen_dc:
            user32.ReleaseDC(None, screen_dc)
        user32.UnregisterClassW(class_name, instance)


def show_startup_splash(
    image_path: Path,
    *,
    fade_in_ms: int,
    hold_ms: int,
    fade_out_ms: int,
) -> None:
    """
    Show a startup splash briefly, then close it.
    """
    rgba_image = _open_splash_rgba(image_path)
    _show_windows_layered_splash(
        rgba_image,
        fade_in_ms=fade_in_ms,
        hold_ms=hold_ms,
        fade_out_ms=fade_out_ms,
    )
