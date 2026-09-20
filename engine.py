"""The step model and the thread that runs it.

Simple clicking and full sequences share this one execution path: the Clicker
tab just builds a two-step sequence (click, delay) and repeats it forever.
"""

import os
import random
import time

import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal

import winapi

STEP_LABELS = {
    "click": "Click",
    "move": "Move",
    "delay": "Delay",
    "loop": "Loop",
    "wait_image": "Wait for image",
    "if_image": "If image",
    "if_pixel": "If pixel",
}


def describe(step):
    """One line for the editor tree."""
    kind = step.get("type")
    if kind == "click":
        where = {"cursor": "cursor", "found": "the found image"}.get(
            step.get("target"), f"{step.get('x')}, {step.get('y')}")
        times = step.get("count", 1)
        suffix = f" ×{times}" if times > 1 else ""
        return f"Click {step.get('button', 'left')} at {where}{suffix}"
    if kind == "move":
        return f"Move to {step.get('x')}, {step.get('y')}"
    if kind == "delay":
        low, high = step.get("min", 100), step.get("max", 100)
        return f"Delay {low} ms" if low == high else f"Delay {low}–{high} ms"
    if kind == "loop":
        count = step.get("count", 1)
        return "Loop until stopped" if count == 0 else f"Loop ×{count}"
    if kind == "wait_image":
        return (f"Wait for {os.path.basename(step.get('path', ''))} "
                f"(max {step.get('timeout', 10000)} ms)")
    if kind == "if_image":
        negate = "not found" if not step.get("found", True) else "found"
        return f"If {os.path.basename(step.get('path', ''))} {negate}"
    if kind == "if_pixel":
        negate = "≠" if not step.get("equals", True) else "="
        return f"If pixel {step.get('x')}, {step.get('y')} {negate} {step.get('color', '#ffffff')}"
    return kind or "?"


def children_keys(step):
    """Which nested step lists a step owns, in display order."""
    kind = step.get("type")
    if kind == "loop":
        return ["steps"]
    if kind in ("if_image", "if_pixel"):
        return ["then", "otherwise"]
    return []


# --- image matching -------------------------------------------------------

_template_cache = {}


def load_template(path):
    """cv2.imread cannot open a path with non-ASCII characters on Windows."""
    try:
        stamp = os.path.getmtime(path)
    except OSError:
        return None
    cached = _template_cache.get(path)
    if cached and cached[0] == stamp:
        return cached[1]
    try:
        data = np.fromfile(path, dtype=np.uint8)
    except OSError:
        return None
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        return None
    _template_cache[path] = (stamp, image)
    return image


def find_image(path, confidence=0.85):
    """Return (x, y, score) of the best match on screen, or None."""
    template = load_template(path)
    if template is None:
        return None
    screen = winapi.grab_screen()
    if template.shape[0] > screen.shape[0] or template.shape[1] > screen.shape[1]:
        return None
    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    _, score, _, location = cv2.minMaxLoc(result)
    if score < confidence:
        return None
    origin_x, origin_y = winapi.virtual_screen()[:2]
    height, width = template.shape[:2]
    return origin_x + location[0] + width // 2, origin_y + location[1] + height // 2, score


def pixel_matches(x, y, color, tolerance):
    wanted = (int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16))
    actual = winapi.pixel_color(x, y)
    return all(abs(a - b) <= tolerance for a, b in zip(actual, wanted))


# --- runner ---------------------------------------------------------------

class Runner(QThread):
    counted = Signal(int)      # actions performed so far
    note = Signal(str)         # a line for the status bar
    stopped = Signal()

    def __init__(self, steps, repeat=0, parent=None):
        super().__init__(parent)
        self.steps = steps
        self.repeat = repeat  # 0 = until stopped
        self._stop = False
        self._last_report = 0.0
        self.actions = 0
        self.found = None  # (x, y) where the last Wait for / If image saw its target

    def stop(self):
        self._stop = True

    def run(self):
        winapi.begin_precise_timing()
        try:
            rounds = 0
            while not self._stop and (self.repeat == 0 or rounds < self.repeat):
                self._run(self.steps)
                rounds += 1
        except Exception as error:  # a worker thread's traceback goes nowhere in a windowed exe
            self.note.emit(f"Stopped: {error}")
        finally:
            winapi.end_precise_timing()
            self.stopped.emit()

    # -- helpers
    def _sleep(self, milliseconds):
        deadline = time.perf_counter() + milliseconds / 1000.0
        while not self._stop:
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                return
            time.sleep(min(remaining, 0.02))

    def _run(self, steps):
        for step in steps:
            if self._stop:
                return
            handler = getattr(self, "_do_" + step.get("type", ""), None)
            if handler:
                handler(step)

    # -- steps
    def _do_click(self, step):
        button = step.get("button", "left")
        target = step.get("target")
        if target == "found" and self.found is None:
            self.note.emit("No image found to click on")
            return
        for index in range(max(1, step.get("count", 1))):
            if self._stop:
                return
            if target == "point":
                winapi.move_to(step.get("x", 0), step.get("y", 0))
            elif target == "found":
                winapi.move_to(*self.found)
            winapi.click(button)
            self.actions += 1
            # At a 1 ms interval this fires a thousand times a second; the UI
            # only needs to see a number move.
            now = time.perf_counter()
            if now - self._last_report > 0.05:
                self._last_report = now
                self.counted.emit(self.actions)
            if index:
                self._sleep(30)

    def _do_move(self, step):
        winapi.move_to(step.get("x", 0), step.get("y", 0))

    def _do_delay(self, step):
        low = step.get("min", 100)
        high = step.get("max", low)
        self._sleep(random.randint(min(low, high), max(low, high)))

    def _do_loop(self, step):
        count = step.get("count", 1)
        rounds = 0
        while not self._stop and (count == 0 or rounds < count):
            self._run(step.get("steps", []))
            rounds += 1

    def _do_wait_image(self, step):
        self.found = None
        deadline = time.perf_counter() + step.get("timeout", 10000) / 1000.0
        while not self._stop and time.perf_counter() < deadline:
            hit = find_image(step.get("path", ""), step.get("confidence", 0.85))
            if hit:
                self.found = hit[:2]
                return
            self._sleep(200)
        self.note.emit(f"{os.path.basename(step.get('path', ''))} never appeared")

    def _do_if_image(self, step):
        hit = find_image(step.get("path", ""), step.get("confidence", 0.85))
        self.found = hit[:2] if hit else None
        branch = "then" if (hit is not None) == step.get("found", True) else "otherwise"
        self._run(step.get(branch, []))

    def _do_if_pixel(self, step):
        same = pixel_matches(step.get("x", 0), step.get("y", 0),
                             step.get("color", "#ffffff"), step.get("tolerance", 10))
        branch = "then" if same == step.get("equals", True) else "otherwise"
        self._run(step.get(branch, []))


def simple_steps(profile):
    """Turn the Clicker tab's settings into the same step list the runner eats."""
    interval = profile["interval"]
    low = interval["min"]
    high = interval["max"] if interval.get("random") else interval["min"]
    delay = {"type": "delay", "min": low, "max": high}

    points = profile.get("points") or []
    if profile.get("target") == "points" and points:
        steps = []
        for x, y in points:
            steps.append({"type": "click", "target": "point", "x": x, "y": y,
                          "button": "left", "count": 1})
            steps.append(dict(delay))
        return steps
    return [{"type": "click", "target": "cursor", "button": "left", "count": 1}, delay]
