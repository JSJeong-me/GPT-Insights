# toggle_switch.py
# -*- coding: utf-8 -*-
"""
Computer Use (preview) + Playwright demo
- Visits the Control Panel URL
- Lets the model operate the UI to toggle a switch once
- Uses Responses API with truncation="auto" (required by computer-use-preview)
Requirements:
  pip install openai playwright pillow
  python -m playwright install chromium
Environment:
  OPENAI_API_KEY=...
  Optional: HEADFUL=1 to see a visible browser (GUI/Xvfb required). Default is headless.
"""

import os
import time
import base64
from typing import Any, Dict, List, Tuple

from openai import OpenAI
from playwright.sync_api import sync_playwright

TARGET_URL = os.environ.get("TARGET_URL", "https://jsjeong-me.github.io/ControPanel/")
INSTRUCTION = (
    "Open the page and toggle the switch button exactly once. "
    "If it's ON, turn it OFF; if it's OFF, turn it ON. Then stop."
)

# ---------- Utilities ----------
def png_bytes_to_data_url(png_bytes: bytes) -> str:
    b64 = base64.b64encode(png_bytes).decode("utf-8")
    return f"data:image/png;base64,{b64}"


# ---------- Playwright runner ----------
class BrowserComputer:
    def __init__(self, width: int = 1280, height: int = 800):
        self.width = width
        self.height = height
        self.play = None
        self.browser = None
        self.page = None

    def start(self, start_url: str):
        self.play = sync_playwright().start()
        headful = os.getenv("HEADFUL", "0") == "1"
        self.browser = self.play.chromium.launch(headless=not headful)
        self.page = self.browser.new_page(viewport={"width": self.width, "height": self.height})
        self.page.goto(start_url, wait_until="domcontentloaded")

    def stop(self):
        try:
            if self.browser:
                self.browser.close()
        finally:
            if self.play:
                self.play.stop()

    # Computer Use actions
    def screenshot(self) -> str:
        img = self.page.screenshot(full_page=False)
        return png_bytes_to_data_url(img)

    def click(self, x: float, y: float, button: str = "left"):
        self.page.mouse.click(x, y, button=button)

    def double_click(self, x: float, y: float):
        self.page.mouse.dblclick(x, y)

    def move(self, x: float, y: float):
        self.page.mouse.move(x, y)

    def drag(self, path: List[Tuple[float, float]]):
        if not path or len(path) < 2:
            return
        (x0, y0) = path[0]
        self.page.mouse.move(x0, y0)
        self.page.mouse.down()
        for (x, y) in path[1:]:
            self.page.mouse.move(x, y)
        self.page.mouse.up()

    def scroll(self, scroll_x: float, scroll_y: float):
        self.page.evaluate("(dx, dy) => { window.scrollBy(dx, dy); }", scroll_x, scroll_y)

    def keypress(self, keys: List[str]):
        if not keys:
            return
        # Simple: press the last key; extend as needed for modifiers
        self.page.keyboard.press(keys[-1])

    def type(self, text: str):
        if text:
            self.page.keyboard.type(text)

    def wait(self, ms: int = 1000):
        time.sleep(ms / 1000.0)


def _item_get(item: Any, key: str, default=None):
    """Safely extract both from attrs (SDK objects) or dicts."""
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _as_list(x):
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]


# ---------- Computer Use main loop ----------
def main():
    client = OpenAI()

    computer = BrowserComputer(width=1280, height=800)
    computer.start(TARGET_URL)

    tools_block = [{
        "type": "computer_use_preview",
        "display_width": computer.width,
        "display_height": computer.height,
        "environment": "linux",
    }]

    try:
        # 1) Initial request: describe the task; don't send screenshot yet.
        response = client.responses.create(
            model="computer-use-preview",
            tools=tools_block,
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": INSTRUCTION},
                    {"type": "input_text", "text": f"Start URL: {TARGET_URL}"},
                    # The model will typically ask for a screenshot via a computer_call.
                ]
            }],
            store=True,
            truncation="auto",
        )

        turn = 0
        max_turns = int(os.getenv("MAX_TURNS", "16"))

        while turn < max_turns:
            turn += 1
            did_any = False

            # Collect follow-up inputs corresponding to each computer_call
            followup_inputs: List[dict] = []

            output_items = getattr(response, "output", None) or []
            for item in output_items:
                item_type = _item_get(item, "type", "")
                if item_type in ("computer_call", "tool_call"):
                    call_id = _item_get(item, "call_id")
                    actions = _item_get(item, "actions") or _item_get(item, "action")
                    actions = _as_list(actions)

                    for action in actions:
                        a_type = _item_get(action, "type", "")
                        did_any = True

                        x = _item_get(action, "x")
                        y = _item_get(action, "y")

                        if a_type == "click":
                            computer.click(float(x), float(y), _item_get(action, "button", "left"))
                        elif a_type == "double_click":
                            computer.double_click(float(x), float(y))
                        elif a_type == "move":
                            computer.move(float(x), float(y))
                        elif a_type == "drag":
                            raw_path = _item_get(action, "path", [])
                            path: List[Tuple[float, float]] = []
                            for node in raw_path:
                                if isinstance(node, (list, tuple)) and len(node) >= 2:
                                    path.append((float(node[0]), float(node[1])))
                                elif isinstance(node, dict):
                                    path.append((float(node.get("x", 0)), float(node.get("y", 0))))
                            computer.drag(path)
                        elif a_type == "scroll":
                            sx = _item_get(action, "scroll_x", None)
                            sy = _item_get(action, "scroll_y", None)
                            if sx is None: sx = _item_get(action, "dx", 0)
                            if sy is None: sy = _item_get(action, "dy", 0)
                            computer.scroll(float(sx or 0), float(sy or 0))
                        elif a_type == "type":
                            computer.type(_item_get(action, "text", ""))
                        elif a_type == "keypress":
                            keys = _item_get(action, "keys", [])
                            if isinstance(keys, str):
                                keys = [keys]
                            computer.keypress(keys)
                        elif a_type == "wait":
                            computer.wait(int(_item_get(action, "ms", 1000)))
                        elif a_type == "screenshot":
                            pass  # We'll just send a fresh screenshot below
                        else:
                            print(f"[warn] unknown action: {a_type}")

                    # For each computer_call, append a 'computer_call_output' input with a fresh screenshot
                    if call_id:
                        followup_inputs.append({
                            "type": "computer_call_output",
                            "call_id": call_id,
                            "output": {
                                "type": "input_image",
                                "image_url": computer.screenshot(),
                            },
                            "status": "completed",
                        })

            if not did_any:
                break

            # 2) Continue the loop: pass the computer_call outputs in 'input'
            response = client.responses.create(
                model="computer-use-preview",
                previous_response_id=response.id,
                tools=tools_block,  # include again for safety
                input=followup_inputs,
                truncation="auto",
            )

        output_text = getattr(response, "output_text", None)
        if output_text:
            print("\n=== MODEL SAYS ===")
            print(output_text)

    finally:
        computer.stop()


if __name__ == "__main__":
    main()
