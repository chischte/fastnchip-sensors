import sys
import ctypes
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import matplotlib
from matplotlib.backend_bases import KeyEvent, MouseEvent

from logger.viewer import DARK_THEME, LIGHT_THEME
from logger.viewer_window import (
    GA_ROOT, GWL_EXSTYLE, WS_EX_APPWINDOW, WS_EX_TOOLWINDOW, ZOOM_MODE,
    configure_viewer_window, current_monitor_bounds, startup_window_size,
)


@unittest.skipUnless(sys.platform == "win32", "Windows Tk window integration")
class ViewerWindowTests(unittest.TestCase):
    def setUp(self):
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, FigureManagerTk
        from matplotlib.figure import Figure

        with matplotlib.rc_context({"toolbar": "toolbar2"}):
            self.manager = FigureManagerTk.create_with_canvas(
                FigureCanvasTkAgg, Figure(figsize=(7, 5)), 1
            )
        self.canvas = self.manager.canvas
        self.controls = configure_viewer_window(self.canvas.figure)
        self.window = self.manager.window
        self.window.deiconify()
        self.window.geometry("700x500+150+120")
        self.window.update()

    def tearDown(self):
        self.window.destroy()

    def press_key(self, key):
        self.canvas.callbacks.process(
            "key_press_event", KeyEvent("key_press_event", self.canvas, key=key)
        )
        self.window.update()

    def test_fullscreen_hides_toolbar_and_escape_restores_window(self):
        original_geometry = self.window.geometry()
        left, top, right, bottom = current_monitor_bounds(self.window)

        self.press_key("ctrl+f")

        self.assertTrue(self.window.overrideredirect())
        self.assertEqual(self.window.geometry(), f"{right-left}x{bottom-top}+{left}+{top}")
        self.assertFalse(self.controls.toolbar.winfo_manager())

        self.press_key("escape")

        self.assertFalse(self.window.overrideredirect())
        self.assertEqual(self.window.geometry(), original_geometry)
        self.assertEqual(self.controls.toolbar.winfo_manager(), "pack")

    def test_secondary_monitor_coordinates_are_not_replaced_by_primary(self):
        for bounds in [(2560, 0, 3840, 1024), (-1920, -1080, 0, 0)]:
            with self.subTest(bounds=bounds), patch(
                "logger.viewer_window.current_monitor_bounds", return_value=bounds
            ):
                self.press_key("f11")
                left, top, right, bottom = bounds
                self.assertEqual(
                    self.window.geometry(), f"{right-left}x{bottom-top}+{left}+{top}"
                )
                self.press_key("f11")
                self.assertFalse(self.window.overrideredirect())

    def test_windowed_bars_are_visible_and_zoom_button_toggles_zoom(self):
        self.assertFalse(self.window.overrideredirect())
        self.assertEqual(self.controls.toolbar.winfo_manager(), "pack")
        self.assertTrue(self.controls.zoom_button.winfo_ismapped())
        self.controls.apply_theme(DARK_THEME)
        self.controls.zoom_button.invoke()
        self.assertEqual(self.controls.toolbar.mode, ZOOM_MODE)
        self.assertEqual(self.controls.zoom_button.cget("background"), DARK_THEME["button_on"])
        self.controls.zoom_button.invoke()
        self.assertFalse(self.controls.toolbar.mode)

    def test_fullscreen_button_toggles_and_tracks_keyboard_state(self):
        self.controls.apply_theme(DARK_THEME)
        original_geometry = self.window.geometry()
        self.controls.fullscreen_button.invoke()
        self.window.update()
        self.assertEqual(
            self.controls.fullscreen_button.cget("background"), DARK_THEME["button_on"]
        )
        self.press_key("escape")
        self.assertEqual(self.window.geometry(), original_geometry)
        self.assertEqual(
            self.controls.fullscreen_button.cget("background"), DARK_THEME["button_off"]
        )
        self.press_key("f11")
        self.controls.fullscreen_button.invoke()
        self.window.update()
        self.assertEqual(self.window.geometry(), original_geometry)

    def test_icon_buttons_have_matching_sizes_and_do_not_overlap(self):
        zoom = self.controls.zoom_button
        fullscreen = self.controls.fullscreen_button
        self.assertEqual(zoom.winfo_width(), fullscreen.winfo_width())
        self.assertEqual(zoom.winfo_height(), fullscreen.winfo_height())
        self.assertEqual(zoom.winfo_y(), fullscreen.winfo_y())
        self.assertLess(zoom.winfo_x() + zoom.winfo_width(), fullscreen.winfo_x())
        self.assertLess(zoom.winfo_x(), self.window.winfo_width() * 0.05)

    def test_startup_size_fits_smallest_monitor_work_area(self):
        with patch("logger.viewer_window.monitor_work_areas", return_value=[
            (0, 0, 2560, 1400), (2560, 0, 3560, 800),
        ]):
            self.assertEqual(startup_window_size(), (900, 720))

    def test_taskbar_entry_survives_fullscreen_and_restore(self):
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        user32.GetAncestor.restype = wintypes.HWND
        user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetWindowLongW.restype = wintypes.LONG
        for key in (None, "f11", "escape"):
            if key:
                self.press_key(key)
            handle = user32.GetAncestor(self.window.winfo_id(), GA_ROOT)
            style = user32.GetWindowLongW(handle, GWL_EXSTYLE)
            self.assertTrue(style & WS_EX_APPWINDOW)
            self.assertFalse(style & WS_EX_TOOLWINDOW)

    def test_theme_and_shortcuts_preserve_zoom_icon_state(self):
        self.press_key("o")
        for theme in (DARK_THEME, LIGHT_THEME):
            with self.subTest(theme=theme["page"]):
                self.controls.apply_theme(theme)
                self.assertEqual(self.controls.toolbar.mode, ZOOM_MODE)
                self.assertEqual(self.controls.zoom_button.cget("background"), theme["button_on"])
                self.assertTrue(self.controls.zoom_button.cget("image"))
        self.press_key("escape")
        self.assertFalse(self.controls.toolbar.mode)
        self.assertEqual(self.controls.zoom_button.cget("background"), LIGHT_THEME["button_off"])

    def test_zoom_icon_enables_rectangle_zoom_on_chart(self):
        self.controls.apply_theme(DARK_THEME)
        axis = self.canvas.figure.add_subplot()
        axis.plot([0, 10], [0, 10])
        self.canvas.draw()
        self.controls.zoom_button.invoke()
        for name, point in [
            ("button_press_event", (2, 2)),
            ("motion_notify_event", (6, 6)),
            ("button_release_event", (6, 6)),
        ]:
            x, y = axis.transData.transform(point)
            buttons = {1} if name == "motion_notify_event" else None
            self.canvas.callbacks.process(
                name, MouseEvent(name, self.canvas, x, y, button=1, buttons=buttons)
            )
            if name == "motion_notify_event":
                widget = self.canvas.get_tk_widget()
                outline = self.canvas._rubberband_rect_white
                background = self.canvas._rubberband_rect_black
                self.assertEqual(widget.itemcget(outline, "outline"), DARK_THEME["zoom_selection"])
                self.assertEqual(widget.itemcget(outline, "width"), "2.0")
                self.assertEqual(widget.itemcget(background, "fill"), DARK_THEME["zoom_selection"])
                self.assertEqual(widget.find_all()[-1], outline)
        self.assertAlmostEqual(axis.get_xlim()[0], 2, delta=0.1)
        self.assertAlmostEqual(axis.get_xlim()[1], 6, delta=0.1)
        self.assertEqual(self.controls.toolbar.winfo_manager(), "pack")
        self.assertIsNone(self.canvas._rubberband_rect_white)
        self.assertIsNone(self.canvas._rubberband_rect_black)

    def test_background_drag_moves_window_but_chart_drag_does_not(self):
        x, y = self.window.winfo_x(), self.window.winfo_y()
        press = SimpleNamespace(
            button=1, inaxes=None, guiEvent=SimpleNamespace(x_root=x+20, y_root=y+20)
        )
        self.controls._start_drag(press)
        self.controls._drag_window(SimpleNamespace(
            guiEvent=SimpleNamespace(x_root=x+120, y_root=y+70)
        ))
        self.window.update()
        self.assertEqual((self.window.winfo_x(), self.window.winfo_y()), (x+100, y+50))
        self.controls._stop_drag(None)
        geometry = self.window.geometry()
        press.inaxes = self.canvas.figure.add_subplot()
        self.controls._start_drag(press)
        self.controls._drag_window(SimpleNamespace(
            guiEvent=SimpleNamespace(x_root=x+220, y_root=y+170)
        ))
        self.window.update()
        self.assertEqual(self.window.geometry(), geometry)

    def test_native_mouse_drag_shows_zoom_rectangle_in_both_themes(self):
        axis = self.canvas.figure.add_subplot()
        axis.plot([0, 10], [0, 10])
        widget = self.canvas.get_tk_widget()
        for theme in (DARK_THEME, LIGHT_THEME):
            with self.subTest(theme=theme["page"]):
                axis.set_xlim(0, 10)
                axis.set_ylim(0, 10)
                self.controls.apply_theme(theme)
                self.canvas.draw()
                self.window.update()
                self.controls.zoom_button.invoke()
                start_x, start_y = axis.transData.transform((2, 2))
                end_x, end_y = axis.transData.transform((6, 6))
                height = widget.winfo_height()
                widget.event_generate(
                    "<ButtonPress-1>", x=int(start_x), y=height-int(start_y)
                )
                widget.event_generate(
                    "<Motion>", x=int(end_x), y=height-int(end_y), state=0x0100
                )
                self.window.update()
                self.assertIsNotNone(self.canvas._rubberband_rect_white)
                self.assertEqual(
                    widget.itemcget(self.canvas._rubberband_rect_white, "outline"),
                    theme["zoom_selection"],
                )
                widget.event_generate(
                    "<ButtonRelease-1>", x=int(end_x), y=height-int(end_y)
                )
                self.window.update()
                self.assertAlmostEqual(axis.get_xlim()[0], 2, delta=0.1)
                self.assertAlmostEqual(axis.get_xlim()[1], 6, delta=0.1)
                self.assertIsNone(self.canvas._rubberband_rect_white)
                self.controls.zoom_button.invoke()

    def test_monitor_lookup_failure_keeps_window_usable(self):
        original_geometry = self.window.geometry()
        with patch("logger.viewer_window.current_monitor_bounds", side_effect=OSError("Unavailable")):
            with patch("sys.stderr"):
                self.press_key("f11")
        self.assertEqual(self.window.geometry(), original_geometry)
        self.assertFalse(self.window.overrideredirect())
        self.assertEqual(self.controls.toolbar.winfo_manager(), "pack")


if __name__ == "__main__":
    unittest.main()
