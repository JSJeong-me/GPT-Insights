아래 스크립트는 **Playwright Python**으로

* (1) **프레임 탐색(점수화로 타겟 frame 선택)**
* (2) **종목코드 입력칸 locator 폴백(여러 후보 중 “가장 그럴듯한 input” 선택)**
* (3) **Enter 후 갱신 대기(입력값/텍스트 변화 폴링)**
* (4) **“팝업(차트 창)만” 캡처(대화상자/타이틀 기준 부모 컨테이너 추적)**
* (5) **로그인 세션 저장/재사용(storage_state)**

까지 포함한 “바로 실행 가능한” 스켈레톤입니다.
(단, 삼성 POP 화면이 **진짜 DOM input이 아닌 캔버스 기반 가짜 입력창**이면 selector로는 한계가 있어, 코드에 **좌표 폴백 훅**도 넣어놨습니다.)

---

## 설치/실행

```bash
pip install playwright
playwright install chromium
```

실행 예시:

```bash
python pop_capture.py --url "https://samsungpop.com/..." --code 015760 --out "./shots" --headless 0
```

처음 1회 로그인 필요하면:

```bash
python pop_capture.py --url "https://samsungpop.com/..." --code 015760 --out "./shots" --headless 0 --save-storage "./storage_state.json"
```

(브라우저가 뜨면 직접 로그인/차트 화면까지 이동 → 자동으로 storage_state 저장)

---

## pop_capture.py

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
POP chart automation skeleton (Playwright, Python)

Features
- Frame 탐색(점수화)로 차트 화면이 있는 frame 선택
- 종목코드 입력칸 locator 폴백(여러 전략)
- Enter 후 화면 갱신 대기(폴링)
- 팝업/차트 창 컨테이너만 스크린샷 저장
- storage_state로 로그인 세션 재사용(옵션)

주의
- 사이트가 캔버스 기반 가짜 입력창이면 DOM selector가 안 잡힐 수 있음:
  -> coordinate fallback 훅을 제공(오프셋은 환경에 맞게 조정)
"""

import argparse
import os
import sys
import time
from pathlib import Path
from datetime import datetime

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError


# ---------------------------
# Utilities
# ---------------------------

def ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except Exception:
        pass


def pick_largest_visible_locator(locators):
    """
    Given a list of Locator objects, pick the one with the largest visible bounding box area.
    """
    best = None
    best_area = -1
    for loc in locators:
        try:
            if loc.count() == 0:
                continue
            # iterate candidates inside this locator
            for i in range(min(loc.count(), 20)):  # cap to avoid huge loops
                cand = loc.nth(i)
                if not cand.is_visible():
                    continue
                box = cand.bounding_box()
                if not box:
                    continue
                area = box["width"] * box["height"]
                if area > best_area:
                    best_area = area
                    best = cand
        except Exception:
            continue
    return best


def wait_poll(fn, timeout_ms=8000, interval_ms=200, label="condition"):
    """
    Poll until fn() returns a truthy value or timeout.
    Returns last truthy value.
    """
    deadline = time.time() + (timeout_ms / 1000.0)
    last_val = None
    while time.time() < deadline:
        try:
            v = fn()
            if v:
                return v
            last_val = v
        except Exception:
            pass
        time.sleep(interval_ms / 1000.0)
    raise TimeoutError(f"Timeout waiting for {label} (timeout_ms={timeout_ms})")


# ---------------------------
# Frame finding
# ---------------------------

def score_frame(frame, anchors):
    """
    Score a frame by checking:
    - anchor texts presence
    - number of input/textbox elements
    """
    score = 0
    try:
        # Anchor texts (strong signals)
        for text, weight in anchors:
            try:
                cnt = frame.locator(f"text={text}").count()
                if cnt > 0:
                    score += weight
            except Exception:
                continue

        # Input density (weak signals)
        try:
            score += min(frame.locator("input").count(), 30) * 0.5
        except Exception:
            pass
        try:
            score += min(frame.get_by_role("textbox").count(), 30) * 0.5
        except Exception:
            pass

    except Exception:
        return -1
    return score


def find_best_frame(page, anchors):
    """
    Iterate page.frames and pick the frame with the highest score.
    """
    frames = page.frames
    best = page.main_frame
    best_score = -1

    safe_print(f"[DEBUG] Total frames: {len(frames)}")
    for idx, fr in enumerate(frames):
        try:
            sc = score_frame(fr, anchors)
            safe_print(f"[DEBUG] frame[{idx}] name={fr.name!r} url={fr.url[:80]!r} score={sc}")
            if sc > best_score:
                best_score = sc
                best = fr
        except Exception:
            continue

    safe_print(f"[INFO] Best frame score={best_score}, name={best.name!r}, url={best.url[:120]!r}")
    return best


# ---------------------------
# Locator strategies for stock code input
# ---------------------------

def _candidate_inputs(frame):
    """
    Produce candidate locator groups for stock code input.
    """
    loc_groups = []

    # 1) Strict: maxlength=6 (common for stock code)
    loc_groups.append(frame.locator("input[maxlength='6']"))

    # 2) Numeric-ish inputs (pattern)
    loc_groups.append(frame.locator("input[pattern*='0-9'], input[inputmode='numeric']"))

    # 3) Generic text inputs
    loc_groups.append(frame.locator("input[type='text']"))
    loc_groups.append(frame.locator("input:not([type])"))

    # 4) Role textbox (some UIs)
    try:
        loc_groups.append(frame.get_by_role("textbox"))
    except Exception:
        pass

    return loc_groups


def _pick_best_input_from_group(group):
    """
    From a group locator (may match multiple), pick a likely stock-code input:
    - visible
    - near top (small y)
    - small-ish width (code box tends to be compact)
    """
    best = None
    best_rank = None

    try:
        n = min(group.count(), 40)
    except Exception:
        return None

    for i in range(n):
        try:
            loc = group.nth(i)
            if not loc.is_visible():
                continue
            box = loc.bounding_box()
            if not box:
                continue

            # Heuristics: prefer inputs near the top and not too wide
            y = box["y"]
            w = box["width"]
            h = box["height"]

            # Reject super-wide search bars unless nothing else
            wide_penalty = 0
            if w > 300:
                wide_penalty += 1000

            # Rank tuple: (y, abs(w-90), wide_penalty, -h)
            rank = (y, abs(w - 90), wide_penalty, -h)

            if best_rank is None or rank < best_rank:
                best = loc
                best_rank = rank
        except Exception:
            continue

    return best


def locate_stock_code_input(frame, known_symbol_texts=None):
    """
    Try multiple strategies to locate the stock code input.
    known_symbol_texts can include current stock name like "한국전력" etc. to anchor around it.
    """
    known_symbol_texts = known_symbol_texts or []

    # Strategy A: pick from candidate input groups
    for group in _candidate_inputs(frame):
        cand = _pick_best_input_from_group(group)
        if cand:
            safe_print("[INFO] Found input candidate via generic heuristics.")
            return cand

    # Strategy B: anchor around known text (e.g., 종목명 "한국전력") and search nearby input
    for t in known_symbol_texts:
        try:
            anchor = frame.locator(f"text={t}").first
            if anchor.count() == 0:
                continue
            # Try nearest preceding input
            near = frame.locator(f"xpath=({anchor._selector})/preceding::input[1]")  # internal selector; may fail
            # Fallback: search all inputs and pick the one closest in y to anchor
            # We'll do proximity scoring manually:
            anchor_box = anchor.bounding_box()
            if anchor_box:
                best = None
                best_d = None
                inputs = frame.locator("input")
                m = min(inputs.count(), 50)
                for i in range(m):
                    inp = inputs.nth(i)
                    if not inp.is_visible():
                        continue
                    box = inp.bounding_box()
                    if not box:
                        continue
                    d = abs(box["y"] - anchor_box["y"]) + abs(box["x"] - anchor_box["x"])
                    if best_d is None or d < best_d:
                        best = inp
                        best_d = d
                if best:
                    safe_print(f"[INFO] Found input candidate near anchor text: {t}")
                    return best
        except Exception:
            continue

    return None


# ---------------------------
# Popup/container screenshot
# ---------------------------

def find_popup_container_handle(frame, title_text="종합차트"):
    """
    Try to find a container element for the chart popup.
    Preference:
    1) role=dialog (pick largest visible)
    2) climb ancestors from title text node until a large-enough box is found
    """
    # 1) role=dialog
    try:
        dialog = pick_largest_visible_locator([frame.get_by_role("dialog")])
        if dialog:
            h = dialog.element_handle()
            if h:
                safe_print("[INFO] Using role=dialog as popup container.")
                return h
    except Exception:
        pass

    # 2) title text anchor -> climb parents
    try:
        title = frame.locator(f"text={title_text}").first
        if title.count() == 0:
            return None
        title_handle = title.element_handle()
        if not title_handle:
            return None

        container = title_handle.evaluate_handle(
            """
            (el) => {
              function area(r){ return r.width * r.height; }
              let node = el;
              let best = el;
              let bestArea = 0;
              while (node && node !== document.body) {
                const r = node.getBoundingClientRect();
                const a = area(r);
                // Heuristic thresholds: adjust if needed
                if (r.width > 650 && r.height > 450 && a > bestArea) {
                  best = node;
                  bestArea = a;
                }
                node = node.parentElement;
              }
              return best;
            }
            """
        )
        safe_print("[INFO] Using ancestor-climbed container from title text.")
        return container
    except Exception:
        return None


# ---------------------------
# Main action: input code + enter + wait + screenshot
# ---------------------------

def input_code_and_enter(page, frame, code: str, timeout_ms=12000,
                         canvas_click_fallback=False,
                         fallback_click_xy=None):
    """
    Focus stock-code input, type code, press Enter, wait for update.
    If DOM input not found and canvas fallback enabled, click coordinates and type.
    """
    # Try to locate input in the chosen frame
    input_loc = locate_stock_code_input(
        frame,
        known_symbol_texts=["한국전력", "삼성전자", "주식"]  # 필요시 추가/변경
    )

    before_val = None
    if input_loc:
        try:
            # Try to read before value
            before_val = input_loc.input_value()
        except Exception:
            before_val = None

        safe_print(f"[INFO] Before input value: {before_val!r}")

        # Focus + replace content + Enter
        try:
            input_loc.click(force=True)
            # Robust replace:
            try:
                input_loc.press("Control+A")
            except Exception:
                pass
            input_loc.type(code, delay=40)
            input_loc.press("Enter")
        except Exception as e:
            safe_print(f"[WARN] Input via locator failed: {e}")

    else:
        safe_print("[WARN] Could not locate DOM input for stock code.")
        if not canvas_click_fallback:
            raise RuntimeError("Stock code input not found (DOM). Enable --canvas-fallback if needed.")

        # Coordinate fallback: click a configured point then type+enter
        if not fallback_click_xy:
            raise RuntimeError("Canvas fallback requested but no --fallback-click-xy provided.")

        x, y = fallback_click_xy
        safe_print(f"[INFO] Canvas fallback click at ({x},{y}) then type.")
        page.mouse.click(x, y)
        page.keyboard.press("Control+A")
        page.keyboard.type(code, delay=40)
        page.keyboard.press("Enter")

    # Wait for update: prefer input value becomes target code OR text appears
    def changed():
        # 1) If we have input_loc, wait for its value to match code (or at least change)
        if input_loc:
            try:
                v = input_loc.input_value()
                if v and v.strip() == code:
                    return True
                if before_val is not None and v is not None and v != before_val:
                    # some UIs keep code elsewhere; value change is still a good sign
                    return True
            except Exception:
                pass

        # 2) Text existence check (sometimes code appears in header)
        try:
            if frame.locator(f"text={code}").count() > 0:
                return True
        except Exception:
            pass

        return False

    try:
        wait_poll(changed, timeout_ms=timeout_ms, interval_ms=250, label="chart update after Enter")
        safe_print("[INFO] Update detected after Enter.")
    except TimeoutError:
        safe_print("[WARN] Update not detected by heuristics (timeout). Proceeding anyway.")


def capture_popup(frame, out_path: Path, title_text="종합차트"):
    """
    Capture screenshot of the popup/container only.
    If container not found, fallback to full frame viewport screenshot.
    """
    container = find_popup_container_handle(frame, title_text=title_text)
    if container:
        container.scroll_into_view_if_needed()
        container.screenshot(path=str(out_path))
        return True

    # fallback: screenshot visible area of frame (not full page)
    try:
        frame.page.screenshot(path=str(out_path))
        return True
    except Exception:
        return False


# ---------------------------
# CLI / Runner
# ---------------------------

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True, help="Target URL (Samsung POP page after login or entry page).")
    ap.add_argument("--code", required=True, help="Stock code to input (e.g., 015760).")
    ap.add_argument("--out", default="./screenshots", help="Output directory for screenshots.")
    ap.add_argument("--title-text", default="종합차트", help="Popup title text to anchor container search.")
    ap.add_argument("--headless", type=int, default=0, help="1=headless, 0=headed.")
    ap.add_argument("--timeout-ms", type=int, default=15000, help="Default timeout ms.")
    ap.add_argument("--storage-state", default=None, help="Load storage_state.json (reuse login).")
    ap.add_argument("--save-storage", default=None, help="Save storage_state.json after manual login run.")
    ap.add_argument("--debug", type=int, default=0, help="1=extra debug screenshots/logs.")
    ap.add_argument("--canvas-fallback", type=int, default=0, help="1=enable coordinate fallback if input not found.")
    ap.add_argument("--fallback-click-xy", default=None,
                    help="x,y for canvas fallback click, e.g. 120,140 (screen coordinates).")
    return ap.parse_args()


def main():
    args = parse_args()
    out_dir = Path(args.out)
    ensure_dir(out_dir)

    fallback_xy = None
    if args.fallback_click_xy:
        try:
            x_str, y_str = args.fallback_click_xy.split(",")
            fallback_xy = (int(x_str.strip()), int(y_str.strip()))
        except Exception:
            raise ValueError("--fallback-click-xy must be like '120,140'")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=bool(args.headless))
        context_kwargs = {
            "viewport": {"width": 1366, "height": 768},
            "locale": "ko-KR",
        }
        if args.storage_state and Path(args.storage_state).exists():
            context_kwargs["storage_state"] = args.storage_state

        context = browser.new_context(**context_kwargs)
        page = context.new_page()
        page.set_default_timeout(args.timeout_ms)

        safe_print(f"[INFO] Navigating: {args.url}")
        page.goto(args.url, wait_until="domcontentloaded")

        # If this is the first run and user wants to save storage, allow manual login.
        if args.save_storage:
            safe_print("[INFO] save-storage enabled. Please login / navigate to the chart screen, then press Resume.")
            page.pause()
            context.storage_state(path=args.save_storage)
            safe_print(f"[INFO] storage_state saved to: {args.save_storage}")

        if args.debug:
            dbg_path = out_dir / f"debug_full_{ts()}.png"
            page.screenshot(path=str(dbg_path), full_page=True)
            safe_print(f"[DEBUG] Saved debug full screenshot: {dbg_path}")

        # Frame selection anchors (adjust to your UI language/text)
        anchors = [
            (args.title_text, 50),   # "종합차트"
            ("주식", 10),
            ("WILLIAMS", 8),         # indicator label in your screenshot
            ("MACD", 6),
        ]

        target_frame = find_best_frame(page, anchors)

        # Input code + Enter + wait
        input_code_and_enter(
            page=page,
            frame=target_frame,
            code=args.code,
            timeout_ms=max(args.timeout_ms, 12000),
            canvas_click_fallback=bool(args.canvas_fallback),
            fallback_click_xy=fallback_xy,
        )

        # Small stabilization delay (animations / redraw)
        time.sleep(0.4)

        # Capture popup only
        shot_path = out_dir / f"{args.code}_{ts()}.png"
        ok = capture_popup(target_frame, shot_path, title_text=args.title_text)
        if not ok:
            raise RuntimeError("Failed to capture screenshot.")

        safe_print(f"[OK] Saved: {shot_path}")

        if args.debug:
            # Dump frame list info
            frames = page.frames
            info_path = out_dir / f"frames_{ts()}.txt"
            with open(info_path, "w", encoding="utf-8") as f:
                for i, fr in enumerate(frames):
                    f.write(f"frame[{i}] name={fr.name!r}\nurl={fr.url}\n\n")
            safe_print(f"[DEBUG] Saved frames info: {info_path}")

        context.close()
        browser.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        safe_print("\n[INFO] Interrupted.")
        sys.exit(130)
    except Exception as e:
        safe_print(f"[ERROR] {e}")
        sys.exit(1)
```

---

## 빠르게 “내 환경에 맞게” 튜닝하는 포인트 3개

1. `anchors`에 **화면에 확실히 존재하는 텍스트**를 더 넣으면 frame 선택이 빨라집니다.
2. 입력칸이 잘못 잡히면 `_pick_best_input_from_group()`의 **폭/위치 휴리스틱(예: w, y 기준)**을 조정하세요.
3. DOM input이 아예 안 잡히면 `--canvas-fallback 1 --fallback-click-xy "x,y"`로 **좌표 클릭 후 type** 방식으로 전환하세요. (좌표는 `--headless 0`에서 마우스 위치를 확인해 고정)

원하시면, 위 스크립트에 **(a) codegen 기반 “정확한 selector 자동 추출” 모드**, **(b) 캡처 영역을 “차트 캔버스만 크롭”**하는 모드까지 같이 넣어드릴게요.
