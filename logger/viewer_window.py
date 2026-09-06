"""Native window controls for the viewer's Tk backend."""

import ctypes
import sys
from ctypes import wintypes


MONITOR_DEFAULT_TO_NEAREST = 2
ZOOM_MODE = "zoom rect"
ICON_BUTTON_CENTER_Y = 0.9415
ICON_BUTTON_SIZE_INCHES = 0.37
ICON_BUTTON_MARGIN_INCHES = 0.12
DEFAULT_WINDOW_SIZE = (1100, 850)
STARTUP_SCREEN_FRACTION = 0.90
GWL_EXSTYLE = -20
WS_EX_APPWINDOW = 0x00040000
WS_EX_TOOLWINDOW = 0x00000080
GA_ROOT = 2


class MonitorInfo(ctypes.Structure):
    _fields_ = [
        ("size", wintypes.DWORD),
        ("monitor", wintypes.RECT),
        ("work", wintypes.RECT),
        ("flags", wintypes.DWORD),
    ]


def _monitor_rect(user32, monitor, work_area=False) -> tuple[int, int, int, int]:
    user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]
    user32.GetMonitorInfoW.restype = wintypes.BOOL
    info = MonitorInfo()
    info.size = ctypes.sizeof(info)
    if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        raise ctypes.WinError(ctypes.get_last_error())
    rect = info.work if work_area else info.monitor
    return rect.left, rect.top, rect.right, rect.bottom


def current_monitor_bounds(window) -> tuple[int, int, int, int]:
    """Return the Windows monitor containing most of the viewer window."""
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.MonitorFromWindow.restype = wintypes.HANDLE
    monitor = user32.MonitorFromWindow(window.winfo_id(), MONITOR_DEFAULT_TO_NEAREST)
    return _monitor_rect(user32, monitor)


def monitor_work_areas() -> list[tuple[int, int, int, int]]:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(
        wintypes.BOOL, wintypes.HANDLE, wintypes.HDC,
        ctypes.POINTER(wintypes.RECT), wintypes.LPARAM,
    )
    monitors = []

    @callback_type
    def collect(monitor, _dc, _rect, _data):
        monitors.append(monitor)
        return True

    user32.EnumDisplayMonitors.argtypes = [
        wintypes.HDC, ctypes.POINTER(wintypes.RECT), callback_type, wintypes.LPARAM
    ]
    user32.EnumDisplayMonitors.restype = wintypes.BOOL
    if not user32.EnumDisplayMonitors(None, None, collect, 0):
        raise ctypes.WinError(ctypes.get_last_error())
    return [_monitor_rect(user32, monitor, work_area=True) for monitor in monitors]


def startup_window_size() -> tuple[int, int]:
    if sys.platform != "win32":
        return DEFAULT_WINDOW_SIZE
    areas = monitor_work_areas()
    if not areas:
        return DEFAULT_WINDOW_SIZE
    width = min(right - left for left, top, right, bottom in areas)
    height = min(bottom - top for left, top, right, bottom in areas)
    return (
        min(DEFAULT_WINDOW_SIZE[0], int(width * STARTUP_SCREEN_FRACTION)),
        min(DEFAULT_WINDOW_SIZE[1], int(height * STARTUP_SCREEN_FRACTION)),
    )


def ensure_taskbar_entry(window) -> None:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    user32.GetAncestor.restype = wintypes.HWND
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongW.restype = wintypes.LONG
    user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
    user32.SetWindowLongW.restype = wintypes.LONG
    hwnd = user32.GetAncestor(window.winfo_id(), GA_ROOT)
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    taskbar_style = (style | WS_EX_APPWINDOW) & ~WS_EX_TOOLWINDOW
    if style == taskbar_style:
        return
    ctypes.set_last_error(0)
    previous = user32.SetWindowLongW(hwnd, GWL_EXSTYLE, taskbar_style)
    error = ctypes.get_last_error()
    if not previous and error:
        raise ctypes.WinError(error)



class TkViewerWindow:
    def __init__(self, figure):
        self.canvas = figure.canvas
        self.window = self.canvas.manager.window
        self.toolbar = self.canvas.manager.toolbar
        self._native_fullscreen_toggle = self.canvas.manager.full_screen_toggle
        self._restore_geometry = None
        self._restore_state = None
        self._drag_offset = None
        self._theme = None
        self.zoom_button = None
        self.fullscreen_button = None
        self._fullscreen_icon = None
        self.window.overrideredirect(False)
        try:
            width, height = startup_window_size()
        except OSError as exc:
            print(f"Could not determine startup screen size: {exc}", file=sys.stderr)
            width, height = DEFAULT_WINDOW_SIZE
        self.window.geometry(f"{width}x{height}")
        if sys.platform == "win32":
            self.window.bind("<Map>", self._on_window_map, add="+")
        if self.toolbar is not None:
            self._native_draw_rubberband = self.toolbar.draw_rubberband
            self.toolbar.draw_rubberband = self._draw_zoom_selection
            self._create_zoom_button()
        self.fullscreen_button = self._create_icon_button(
            self.toggle_fullscreen, "Toggle fullscreen (F11; Esc to exit)"
        )
        self._resize_icon_buttons(None)
        self.canvas.manager.full_screen_toggle = self.toggle_fullscreen
        self.canvas.mpl_connect("key_press_event", self._on_key)
        self.canvas.mpl_connect("button_press_event", self._start_drag)
        self.canvas.mpl_connect("button_release_event", self._stop_drag)
        self.canvas.mpl_connect("resize_event", self._resize_icon_buttons)
        self.canvas.mpl_connect("motion_notify_event", self._drag_window)

    def _on_window_map(self, event) -> None:
        if event.widget is self.window:
            try:
                ensure_taskbar_entry(self.window)
            except OSError as exc:
                print(f"Could not restore taskbar entry: {exc}", file=sys.stderr)

    def _create_icon_button(self, command, tooltip):
        import tkinter as tk
        from matplotlib.backends._backend_tk import add_tooltip

        button = tk.Button(
            self.canvas.get_tk_widget(), command=command,
            borderwidth=0, highlightthickness=0, relief="flat", takefocus=False,
        )
        add_tooltip(button, tooltip)
        return button

    def _create_zoom_button(self) -> None:
        self.zoom_button = self._create_icon_button(
            self.toggle_zoom, "Zoom: drag a rectangle; right-drag to zoom out"
        )
        self.zoom_button._image_file = self.toolbar._buttons["Zoom"]._image_file

    def icon_buttons_left(self) -> float:
        width = ICON_BUTTON_MARGIN_INCHES + ICON_BUTTON_SIZE_INCHES
        return 1 - width / self.canvas.figure.get_figwidth()

    def zoom_button_right(self) -> float:
        return (ICON_BUTTON_MARGIN_INCHES + ICON_BUTTON_SIZE_INCHES) / self.canvas.figure.get_figwidth()

    def _resize_icon_buttons(self, _event) -> None:
        dpi = self.canvas.figure.dpi
        size = round(ICON_BUTTON_SIZE_INCHES * dpi)
        right_offset = round(ICON_BUTTON_MARGIN_INCHES * dpi)
        for button, side in ((self.fullscreen_button, "right"), (self.zoom_button, "left")):
            if button is not None:
                button.place(
                    relx=1 if side == "right" else 0,
                    x=-right_offset if side == "right" else right_offset,
                    rely=ICON_BUTTON_CENTER_Y,
                    anchor="e" if side == "right" else "w", width=size, height=size,
                )
        self._style_fullscreen_button()

    def apply_theme(self, theme: dict) -> None:
        self._theme = theme
        self.window.configure(background=theme["page"])
        self.canvas.get_tk_widget().configure(
            background=theme["page"], highlightbackground=theme["page"]
        )
        self._style_zoom_button()
        self._style_fullscreen_button()
        self._style_toolbar()

    def _style_toolbar(self) -> None:
        if self.toolbar is None:
            return
        theme = self._theme
        colors = {
            "background": theme["page"],
            "foreground": theme["text"],
            "activebackground": theme["grid"],
            "activeforeground": theme["text"],
            "selectcolor": theme["button_on"],
            "disabledforeground": theme["muted"],
            "highlightbackground": theme["page"],
        }
        for widget in [self.toolbar, *self.toolbar.winfo_children()]:
            widget.configure(**{key: value for key, value in colors.items() if key in widget.keys()})
            if getattr(widget, "_image_file", None):
                self.toolbar._set_image_for_button(widget)

    def _style_zoom_button(self) -> None:
        if self.zoom_button is None or self._theme is None:
            return
        self._style_icon_button(self.zoom_button, self.toolbar.mode == ZOOM_MODE)
        # Reuse Matplotlib's zoom icon and its contrast-aware icon rendering.
        self.toolbar._set_image_for_button(self.zoom_button)

    def _style_icon_button(self, button, enabled: bool) -> None:
        theme = self._theme
        button.configure(
            background=theme["button_on" if enabled else "button_off"],
            foreground=theme["button_text_on" if enabled else "button_text_off"],
            activebackground=theme["button_on"],
            activeforeground=theme["button_text_on"],
        )

    def _style_fullscreen_button(self) -> None:
        if self.fullscreen_button is None or self._theme is None:
            return
        import tkinter as tk

        self._style_icon_button(self.fullscreen_button, self._restore_geometry is not None)
        size = self.fullscreen_button.winfo_pixels("18p")
        inset = round(size * 0.16)
        arm = round(size * 0.28)
        stroke = max(1, round(size * 0.08))
        end = size - inset
        icon = tk.PhotoImage(master=self.fullscreen_button, width=size, height=size)
        color = self.fullscreen_button.cget("foreground")
        for left in (inset, end - arm):
            for top in (inset, end - arm):
                edge_x = inset if left == inset else end - stroke
                edge_y = inset if top == inset else end - stroke
                icon.put(color, to=(left, edge_y, left + arm, edge_y + stroke))
                icon.put(color, to=(edge_x, top, edge_x + stroke, top + arm))
        self._fullscreen_icon = icon
        self.fullscreen_button.configure(image=icon)

    def toggle_zoom(self) -> None:
        self.toolbar.zoom()
        self._style_zoom_button()
        self.canvas.get_tk_widget().focus_set()

    def _draw_zoom_selection(self, event, x0, y0, x1, y1) -> None:
        self._native_draw_rubberband(event, x0, y0, x1, y1)
        if self._theme is None:
            return
        canvas = self.canvas.get_tk_widget()
        background = self.canvas._rubberband_rect_black
        outline = self.canvas._rubberband_rect_white
        color = self._theme["zoom_selection"]
        # A stippled fill keeps the readings visible inside the selection.
        canvas.itemconfigure(
            background, outline=self._theme["plot"], width=4,
            fill=color, stipple="gray12",
        )
        canvas.itemconfigure(outline, outline=color, width=2, dash=())
        canvas.tag_raise(background)
        canvas.tag_raise(outline)

    def _start_drag(self, event) -> None:
        if event.button != 1 or event.inaxes is not None or self._restore_geometry is not None:
            return
        if event.guiEvent is None:
            return
        self._drag_offset = (
            event.guiEvent.x_root - self.window.winfo_x(),
            event.guiEvent.y_root - self.window.winfo_y(),
        )

    def _drag_window(self, event) -> None:
        if self._drag_offset is None or event.guiEvent is None:
            return
        offset_x, offset_y = self._drag_offset
        self.window.geometry(
            f"+{event.guiEvent.x_root - offset_x}+{event.guiEvent.y_root - offset_y}"
        )

    def _stop_drag(self, _event) -> None:
        self._drag_offset = None

    def toggle_fullscreen(self) -> None:
        if self._restore_geometry is not None:
            self.exit_fullscreen()
            return

        monitor_bounds = None
        if sys.platform == "win32":
            try:
                monitor_bounds = current_monitor_bounds(self.window)
            except OSError as exc:
                print(f"Could not enter fullscreen: {exc}", file=sys.stderr)
                return

        self._restore_geometry = self.window.geometry()
        self._restore_state = self.window.state()
        if self.toolbar is not None:
            self.toolbar.pack_forget()

        if monitor_bounds is None:
            self.window.overrideredirect(False)
            self._native_fullscreen_toggle()
        else:
            left, top, right, bottom = monitor_bounds
            self.window.state("normal")
            # Tk's native Windows fullscreen can jump to the primary monitor.
            self.window.overrideredirect(True)
            self.window.update_idletasks()
            # A literal '+' preserves negative virtual-desktop coordinates in Tk.
            self.window.geometry(f"{right - left}x{bottom - top}+{left}+{top}")
        self._style_fullscreen_button()
        self.canvas.get_tk_widget().focus_set()

    def exit_fullscreen(self) -> None:
        if self._restore_geometry is None:
            return

        if sys.platform == "win32":
            self.window.overrideredirect(False)
            self.window.geometry(self._restore_geometry)
            self.window.state(self._restore_state)
        else:
            self._native_fullscreen_toggle()
        if self.toolbar is not None:
            self.toolbar.pack(side="bottom", fill="x", before=self.canvas.get_tk_widget())
        self._restore_geometry = None
        self._restore_state = None
        self._style_fullscreen_button()
        self.canvas.get_tk_widget().focus_set()

    def _on_key(self, event) -> None:
        if event.key == "f11":
            self.toggle_fullscreen()
        elif event.key == "escape":
            self.exit_fullscreen()
            if self.toolbar is not None and self.toolbar.mode == ZOOM_MODE:
                self.toggle_zoom()
        if event.key in ("o", "p"):
            self._style_zoom_button()


def configure_viewer_window(figure):
    if not hasattr(figure.canvas, "get_tk_widget"):
        return None
    return TkViewerWindow(figure)
