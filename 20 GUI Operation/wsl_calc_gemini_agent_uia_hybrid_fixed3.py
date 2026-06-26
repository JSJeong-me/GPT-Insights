#!/usr/bin/env python3
"""
wsl_calc_gemini_agent_uia_hybrid.py

Robust Windows Calculator GUI Operation Agent for WSL.

Problem fixed
-------------
Previous Gemini-only coordinate versions could input digits but often failed
on operators such as +, -, ×, ÷, =.

Why?
- Operator buttons are visually close in the right-side column.
- Symbols may appear as +, −, ×, ÷, = and are easy to confuse.
- Full-screen/crop-local coordinate localization can be slightly off.
- A small coordinate error may still hit a number button or blank area.

Solution
--------
Use a hybrid strategy:

1. Open and position Windows Calculator.
2. For each Calculator button, first use Windows UI Automation:
      num7Button, plusButton, multiplyButton, equalButton, ...
   This is much more reliable for operators.
3. If UI Automation fails, fall back to Gemini crop-local coordinate clicking.
4. Verify the display first with UI Automation, then with Gemini if needed.

Default mission:
    C 1 2 + 3 4 =  -> expected display 46

Run:
    pip install pillow google-genai
    export GEMINI_API_KEY="your_api_key"
    python3 wsl_calc_gemini_agent_uia_hybrid.py

Recommended tests:
    python3 wsl_calc_gemini_agent_uia_hybrid.py
    python3 wsl_calc_gemini_agent_uia_hybrid.py --sequence "C 7 * 8 =" --expected 56
    python3 wsl_calc_gemini_agent_uia_hybrid.py --sequence "C 100 - 25 =" --expected 75
    python3 wsl_calc_gemini_agent_uia_hybrid.py --sequence "C 144 / 12 =" --expected 12

Strict visual mode:
    python3 wsl_calc_gemini_agent_uia_hybrid.py --strategy gemini

Most reliable mode:
    python3 wsl_calc_gemini_agent_uia_hybrid.py --strategy uia
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image

try:
    from google import genai
except Exception:
    genai = None


# ---------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------

TARGET_SCREEN_WIDTH = 1600
TARGET_SCREEN_HEIGHT = 1200
TARGET_SCALE_PERCENT = 100

CALC_WINDOW_X = 80
CALC_WINDOW_Y = 80
CALC_WINDOW_W = 520
CALC_WINDOW_H = 760

WIN_TMP_SCREEN = r"C:\Windows\Temp\wsl_calc_screen.png"
WSL_TMP_SCREEN = Path("current_calc_screen.png")
WSL_CALC_CROP = Path("current_calc_crop.png")

DEFAULT_SEQUENCE = ["C", "1", "2", "+", "3", "4", "="]
DEFAULT_EXPECTED = "46"
DEFAULT_MODEL = "gemini-2.5-flash"

BUTTON_ACTION_DELAY_SEC = 0.45
AFTER_OPEN_DELAY_SEC = 2.0


@dataclass
class WindowRect:
    left: int
    top: int
    right: int
    bottom: int
    source: str = "unknown"

    @property
    def width(self) -> int:
        return max(0, self.right - self.left)

    @property
    def height(self) -> int:
        return max(0, self.bottom - self.top)

    def padded(self, pad: int, screen_w: int, screen_h: int) -> "WindowRect":
        return WindowRect(
            left=max(0, self.left - pad),
            top=max(0, self.top - pad),
            right=min(screen_w, self.right + pad),
            bottom=min(screen_h, self.bottom + pad),
            source=self.source,
        )


def fixed_calculator_rect() -> WindowRect:
    return WindowRect(
        left=CALC_WINDOW_X,
        top=CALC_WINDOW_Y,
        right=CALC_WINDOW_X + CALC_WINDOW_W,
        bottom=CALC_WINDOW_Y + CALC_WINDOW_H,
        source="fixed_fallback",
    )


# ---------------------------------------------------------------------
# Windows command helpers
# ---------------------------------------------------------------------

def decode_windows_output(data: Optional[bytes]) -> str:
    if data is None:
        return ""

    for enc in ("utf-8", "cp949", "euc-kr", "utf-16", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue

    return data.decode("utf-8", errors="replace")


def run_process(
    args: List[str],
    *,
    timeout: int = 30,
    quiet: bool = False,
) -> Tuple[int, str, str]:
    try:
        completed = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        msg = f"Command timed out after {timeout}s: {' '.join(args)}"
        if not quiet:
            print(f"[오류] {msg}")
        return 124, "", msg

    stdout = decode_windows_output(completed.stdout)
    stderr = decode_windows_output(completed.stderr)

    if not quiet and stdout.strip():
        print(stdout.strip())
    if not quiet and stderr.strip():
        print(f"[stderr] {stderr.strip()}")

    return completed.returncode, stdout, stderr


def run_windows_cmd(cmd: str, *, timeout: int = 30, quiet: bool = False) -> Tuple[int, str, str]:
    return run_process(["cmd.exe", "/c", cmd], timeout=timeout, quiet=quiet)


def run_powershell_cmd(ps_cmd: str, *, timeout: int = 30, quiet: bool = False) -> Tuple[int, str, str]:
    preamble = (
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
        "$OutputEncoding = [System.Text.Encoding]::UTF8; "
    )
    return run_process(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", preamble + ps_cmd],
        timeout=timeout,
        quiet=quiet,
    )


# ---------------------------------------------------------------------
# GUI primitives
# ---------------------------------------------------------------------

def take_screenshot() -> str:
    ps_screenshot = rf"""
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms

$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height
$graphics = [System.Drawing.Graphics]::FromImage($bmp)
$graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)
$bmp.Save("{WIN_TMP_SCREEN}", [System.Drawing.Imaging.ImageFormat]::Png)
$graphics.Dispose()
$bmp.Dispose()

Write-Output "$($bounds.Width)x$($bounds.Height)"
"""
    rc, stdout, stderr = run_powershell_cmd(ps_screenshot, timeout=15, quiet=True)
    if rc != 0:
        print("[오류] 화면 캡처 실패")
        if stderr.strip():
            print(stderr.strip())
        raise RuntimeError("Failed to capture Windows screen.")

    win_wsl_path = "/mnt/c/Windows/Temp/wsl_calc_screen.png"
    if not Path(win_wsl_path).exists():
        raise FileNotFoundError(f"Screenshot not found at {win_wsl_path}")

    shutil.copyfile(win_wsl_path, WSL_TMP_SCREEN)

    img = Image.open(WSL_TMP_SCREEN)
    width, height = img.size
    print(f"[시스템] 화면 캡처 완료 -> {WSL_TMP_SCREEN} ({width}x{height})")

    if (width, height) != (TARGET_SCREEN_WIDTH, TARGET_SCREEN_HEIGHT):
        print(
            f"⚠️ 경고: 현재 캡처 해상도는 {width}x{height}입니다. "
            f"설계 기준은 {TARGET_SCREEN_WIDTH}x{TARGET_SCREEN_HEIGHT}, "
            f"배율 {TARGET_SCALE_PERCENT}%입니다. 계속 진행합니다."
        )

    return str(WSL_TMP_SCREEN)


def mouse_click(x: int, y: int) -> None:
    x = int(x)
    y = int(y)
    print(f"[액션] mouse_click 직접 실행 -> ({x}, {y})")

    ps_click = f"""
$signature = @'
[DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y);
[DllImport("user32.dll")] public static extern void mouse_event(int dwFlags, int dx, int dy, int dwData, int dwExtraInfo);
'@

$type = Add-Type -MemberDefinition $signature -Name "Win32Mouse" -Namespace "Win32" -PassThru
$type::SetCursorPos({x}, {y}) | Out-Null
Start-Sleep -Milliseconds 100
$type::mouse_event(0x0002, 0, 0, 0, 0)
Start-Sleep -Milliseconds 100
$type::mouse_event(0x0004, 0, 0, 0, 0)
"""
    rc, stdout, stderr = run_powershell_cmd(ps_click, timeout=10, quiet=True)
    if rc != 0:
        print("[오류] mouse_click PowerShell 실행 실패")
        if stderr.strip():
            print(stderr.strip())
        raise RuntimeError("mouse_click failed.")


def close_calculator(silent: bool = False) -> None:
    ps_close = r"""
$pattern = "Calculator|계산기"
$procs = Get-Process -ErrorAction SilentlyContinue |
    Where-Object { $_.MainWindowTitle -match $pattern -and $_.MainWindowHandle -ne 0 }

foreach ($p in $procs) {
    try { $p.CloseMainWindow() | Out-Null } catch {}
}

Start-Sleep -Milliseconds 500

Get-Process -Name "CalculatorApp" -ErrorAction SilentlyContinue |
    Stop-Process -Force -ErrorAction SilentlyContinue

Write-Output "CLOSED"
"""
    run_powershell_cmd(ps_close, timeout=10, quiet=True)
    if not silent:
        print("[시스템] Calculator 종료 요청 완료")


def bring_calculator_to_front() -> bool:
    ps_front = r"""
$signature = @'
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
[DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
'@

$User32 = Add-Type -MemberDefinition $signature -Name "Win32Foreground" -Namespace "Win32" -PassThru
$pattern = "Calculator|계산기"

$proc = Get-Process -ErrorAction SilentlyContinue |
    Where-Object { $_.MainWindowTitle -match $pattern -and $_.MainWindowHandle -ne 0 } |
    Select-Object -First 1

if ($proc) {
    $User32::ShowWindow($proc.MainWindowHandle, 9) | Out-Null
    Start-Sleep -Milliseconds 120
    $User32::SetForegroundWindow($proc.MainWindowHandle) | Out-Null
    Write-Output "FOUND:$($proc.ProcessName):$($proc.MainWindowTitle)"
} else {
    Write-Output "NOT_FOUND"
}
"""
    rc, stdout, stderr = run_powershell_cmd(ps_front, timeout=10, quiet=True)
    found = "FOUND:" in stdout
    if found:
        print(f"[시스템] Calculator foreground 설정: {stdout.strip()}")
    else:
        print("[경고] Calculator 창을 foreground로 찾지 못했습니다.")
    return found


def open_calculator_at_fixed_position(close_existing: bool = True) -> None:
    print("[액션] Windows Calculator 실행")

    if close_existing:
        close_calculator(silent=True)
        time.sleep(0.5)

    run_windows_cmd("start calc.exe", timeout=10, quiet=True)
    time.sleep(AFTER_OPEN_DELAY_SEC)

    ps_move = f"""
$signature = @'
[DllImport("user32.dll", SetLastError = true)] public static extern bool MoveWindow(IntPtr hWnd, int X, int Y, int nWidth, int nHeight, bool bRepaint);
[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
[DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
'@

$User32 = Add-Type -MemberDefinition $signature -Name "Win32CalcMove" -Namespace "Win32" -PassThru
$pattern = "Calculator|계산기"

$deadline = (Get-Date).AddSeconds(8)
$proc = $null

while ((Get-Date) -lt $deadline) {{
    $proc = Get-Process -ErrorAction SilentlyContinue |
        Where-Object {{ $_.MainWindowTitle -match $pattern -and $_.MainWindowHandle -ne 0 }} |
        Select-Object -First 1
    if ($proc) {{ break }}
    Start-Sleep -Milliseconds 300
}}

if ($proc) {{
    $hwnd = $proc.MainWindowHandle
    $User32::ShowWindow($hwnd, 9) | Out-Null
    Start-Sleep -Milliseconds 150
    $User32::MoveWindow($hwnd, {CALC_WINDOW_X}, {CALC_WINDOW_Y}, {CALC_WINDOW_W}, {CALC_WINDOW_H}, $true) | Out-Null
    Start-Sleep -Milliseconds 400
    $User32::SetForegroundWindow($hwnd) | Out-Null
    Write-Output "MOVED:$($proc.ProcessName):$($proc.MainWindowTitle)"
}} else {{
    Write-Output "NOT_FOUND"
}}
"""
    rc, stdout, stderr = run_powershell_cmd(ps_move, timeout=12, quiet=True)
    if "MOVED:" in stdout:
        print(f"[시스템] Calculator 창 위치 고정 완료: ({CALC_WINDOW_X}, {CALC_WINDOW_Y}, {CALC_WINDOW_W}, {CALC_WINDOW_H})")
    else:
        print("[경고] Calculator 창 위치 고정 실패. 고정 crop fallback으로 계속 진행할 수 있습니다.")
        if stderr.strip():
            print(f"[PowerShell stderr] {stderr.strip()}")

    time.sleep(1.0)


# ---------------------------------------------------------------------
# UI Automation
# ---------------------------------------------------------------------

UIA_BUTTONS: Dict[str, Tuple[str, str]] = {
    "0": ("num0Button", r"^0$|Zero|영|0"),
    "1": ("num1Button", r"^1$|One|일|1"),
    "2": ("num2Button", r"^2$|Two|이|2"),
    "3": ("num3Button", r"^3$|Three|삼|3"),
    "4": ("num4Button", r"^4$|Four|사|4"),
    "5": ("num5Button", r"^5$|Five|오|5"),
    "6": ("num6Button", r"^6$|Six|육|6"),
    "7": ("num7Button", r"^7$|Seven|칠|7"),
    "8": ("num8Button", r"^8$|Eight|팔|8"),
    "9": ("num9Button", r"^9$|Nine|구|9"),
    ".": ("decimalSeparatorButton", r"\.|Decimal|소수"),
    "+": ("plusButton", r"\+|Plus|Add|더하기|더하기 단추"),
    "-": ("minusButton", r"−|-|Minus|Subtract|빼기|빼기 단추"),
    "*": ("multiplyButton", r"×|\*|Multiply|곱하기|곱하기 단추"),
    "/": ("divideButton", r"÷|/|Divide|나누기|나누기 단추"),
    "=": ("equalButton", r"=|Equals|Equal|같음|계산|같음 단추"),
    "C": ("clearButton", r"^C$|Clear|지우기|초기화"),
    "CE": ("clearEntryButton", r"CE|Clear Entry|입력 지우기"),
}


def normalize_button_label(label: str) -> str:
    label = label.strip()
    replacements = {
        "plus": "+",
        "add": "+",
        "minus": "-",
        "subtract": "-",
        "mul": "*",
        "multiply": "*",
        "times": "*",
        "×": "*",
        "x": "*",
        "X": "*",
        "divide": "/",
        "÷": "/",
        "equals": "=",
        "equal": "=",
        "clear": "C",
    }
    return replacements.get(label.lower(), label)


def parse_sequence(sequence_text: str) -> List[str]:
    tokens = sequence_text.strip().split()
    buttons: List[str] = []

    for token in tokens:
        token = normalize_button_label(token)
        if re.fullmatch(r"\d+", token):
            buttons.extend(list(token))
        else:
            buttons.append(token)

    return buttons


def invoke_calculator_button_uia(button_label: str) -> bool:
    """
    Invoke a Calculator button by UI Automation.

    This is the most reliable path for operator buttons because it does not
    depend on visual coordinate localization.
    """
    button_label = normalize_button_label(button_label)

    if button_label not in UIA_BUTTONS:
        print(f"[UIA] 지원하지 않는 버튼 label: {button_label}")
        return False

    automation_id, name_regex = UIA_BUTTONS[button_label]

    # Escape single quotes for PowerShell single-quoted strings.
    automation_id_ps = automation_id.replace("'", "''")
    name_regex_ps = name_regex.replace("'", "''")
    label_ps = button_label.replace("'", "''")

    ps_uia = f"""
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$patternTitle = "Calculator|계산기"
$automationId = '{automation_id_ps}'
$nameRegex = '{name_regex_ps}'
$buttonLabel = '{label_ps}'

$proc = Get-Process -ErrorAction SilentlyContinue |
    Where-Object {{ $_.MainWindowTitle -match $patternTitle -and $_.MainWindowHandle -ne 0 }} |
    Select-Object -First 1

if (-not $proc) {{
    Write-Output "UIA_NOT_FOUND:CALC_WINDOW"
    exit 1
}}

$root = [System.Windows.Automation.AutomationElement]::FromHandle($proc.MainWindowHandle)
if (-not $root) {{
    Write-Output "UIA_NOT_FOUND:ROOT"
    exit 1
}}

$buttonTypeCond = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
    [System.Windows.Automation.ControlType]::Button
)

$buttons = $root.FindAll(
    [System.Windows.Automation.TreeScope]::Descendants,
    $buttonTypeCond
)

$target = $null

# 1st pass: AutomationId exact match.
foreach ($b in $buttons) {{
    $aid = $b.Current.AutomationId
    if ($aid -eq $automationId) {{
        $target = $b
        break
    }}
}}

# 2nd pass: Name regex fallback.
if (-not $target) {{
    foreach ($b in $buttons) {{
        $name = $b.Current.Name
        if ($name -match $nameRegex) {{
            $target = $b
            break
        }}
    }}
}}

if (-not $target) {{
    $available = @()
    foreach ($b in $buttons) {{
        $available += "[$($b.Current.AutomationId)|$($b.Current.Name)]"
    }}
    Write-Output "UIA_NOT_FOUND:BUTTON:${{buttonLabel}}"
    Write-Output ($available -join " ")
    exit 2
}}

try {{
    $invoke = $target.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
    $invoke.Invoke()
    Write-Output "UIA_INVOKED:${{buttonLabel}}:$($target.Current.AutomationId):$($target.Current.Name)"
    exit 0
}} catch {{
    $rect = $target.Current.BoundingRectangle
    if ($rect.Width -gt 0 -and $rect.Height -gt 0) {{
        $cx = [int]($rect.Left + $rect.Width / 2)
        $cy = [int]($rect.Top + $rect.Height / 2)
        Write-Output "UIA_RECT_CLICK:${{buttonLabel}}:${{cx}},${{cy}}:$($target.Current.AutomationId):$($target.Current.Name)"
        exit 3
    }} else {{
        Write-Output "UIA_INVOKE_FAILED:${{buttonLabel}}:$($_.Exception.Message)"
        exit 4
    }}
}}
"""
    rc, stdout, stderr = run_powershell_cmd(ps_uia, timeout=15, quiet=True)
    out = stdout.strip()

    if stderr.strip():
        print(f"[UIA stderr] {stderr.strip()}")

    if "UIA_INVOKED:" in out:
        print(f"[UIA] 버튼 Invoke 성공: {out}")
        time.sleep(BUTTON_ACTION_DELAY_SEC)
        return True

    m = re.search(r"UIA_RECT_CLICK:[^:]+:(-?\d+),(-?\d+):", out)
    if m:
        x = int(m.group(1))
        y = int(m.group(2))
        print(f"[UIA] InvokePattern 실패 → BoundingRectangle 중심 클릭 fallback: ({x}, {y})")
        mouse_click(x, y)
        time.sleep(BUTTON_ACTION_DELAY_SEC)
        return True

    print(f"[UIA] 버튼 Invoke 실패: {out}")
    return False


def read_calculator_display_uia() -> Optional[str]:
    """
    Read Calculator display by UI Automation.

    Windows Calculator commonly uses AutomationId 'CalculatorResults'.
    The Name may be:
      - 'Display is 46'
      - Korean localized text containing the value
    """
    ps_read = r"""
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$patternTitle = "Calculator|계산기"

$proc = Get-Process -ErrorAction SilentlyContinue |
    Where-Object { $_.MainWindowTitle -match $patternTitle -and $_.MainWindowHandle -ne 0 } |
    Select-Object -First 1

if (-not $proc) {
    Write-Output "UIA_DISPLAY_NOT_FOUND:CALC_WINDOW"
    exit 1
}

$root = [System.Windows.Automation.AutomationElement]::FromHandle($proc.MainWindowHandle)
if (-not $root) {
    Write-Output "UIA_DISPLAY_NOT_FOUND:ROOT"
    exit 1
}

$cond = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::AutomationIdProperty,
    "CalculatorResults"
)

$el = $root.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $cond)

if ($el) {
    Write-Output "UIA_DISPLAY:$($el.Current.Name)"
    exit 0
}

# Fallback: collect text elements.
$textCond = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
    [System.Windows.Automation.ControlType]::Text
)

$texts = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, $textCond)

foreach ($t in $texts) {
    $name = $t.Current.Name
    if ($name -and $name.Trim().Length -gt 0) {
        Write-Output "UIA_DISPLAY_FALLBACK:$name"
        exit 0
    }
}

Write-Output "UIA_DISPLAY_NOT_FOUND"
exit 2
"""
    rc, stdout, stderr = run_powershell_cmd(ps_read, timeout=10, quiet=True)
    out = stdout.strip()

    if stderr.strip():
        print(f"[UIA display stderr] {stderr.strip()}")

    if "UIA_DISPLAY" not in out:
        print(f"[UIA] display 읽기 실패: {out}")
        return None

    # Keep only the text after the first colon.
    display_text = out.split(":", 1)[1].strip()
    print(f"[UIA] display raw: {display_text}")

    return extract_number_from_display_text(display_text)


def extract_number_from_display_text(text: str) -> Optional[str]:
    """
    Extract a likely numeric result from localized Calculator display text.
    """
    if not text:
        return None

    normalized = (
        text.replace(",", "")
            .replace("\u2212", "-")
            .replace("−", "-")
            .strip()
    )

    # Find last number-like token.
    matches = re.findall(r"-?\d+(?:\.\d+)?", normalized)
    if matches:
        return matches[-1]

    return normalized if normalized else None


# ---------------------------------------------------------------------
# Crop + Gemini fallback
# ---------------------------------------------------------------------

def get_calculator_window_rect() -> WindowRect:
    # This hybrid version deliberately uses the fixed rect for Gemini crop.
    # The window was moved to this location just before.
    return fixed_calculator_rect()


def crop_calculator_window(screenshot_path: str, rect: WindowRect) -> Tuple[str, WindowRect]:
    img = Image.open(screenshot_path)
    screen_w, screen_h = img.size
    used_rect = rect.padded(pad=4, screen_w=screen_w, screen_h=screen_h)

    crop = img.crop((used_rect.left, used_rect.top, used_rect.right, used_rect.bottom))
    crop.save(WSL_CALC_CROP)

    print(
        f"[시스템] Calculator crop 생성 -> {WSL_CALC_CROP} "
        f"origin=({used_rect.left},{used_rect.top}), crop_size={crop.size[0]}x{crop.size[1]}"
    )

    return str(WSL_CALC_CROP), used_rect


def capture_calculator_crop() -> Tuple[str, WindowRect]:
    bring_calculator_to_front()
    screenshot_path = take_screenshot()
    return crop_calculator_window(screenshot_path, get_calculator_window_rect())


BUTTON_HINTS: Dict[str, str] = {
    "C": "Clear button. Usually labeled C. If C is not visible, CE is acceptable.",
    "CE": "Clear Entry button. Usually labeled CE.",
    "+": "Plus / Add button, usually labeled +.",
    "-": "Minus / Subtract button, may be labeled - or −.",
    "*": "Multiply button, may be labeled ×.",
    "/": "Divide button, may be labeled ÷.",
    "=": "Equals button, labeled =.",
    ".": "Decimal point button, labeled .",
}

LOCATE_BUTTON_SYSTEM_INSTRUCTION = """
You are a vision-based Windows Calculator button locator.

You receive a cropped image containing ONLY the Windows Calculator window.
Return ONLY one JSON object with crop-local pixel coordinates.

Required JSON:
{
  "x": 120,
  "y": 560,
  "confidence": 0.95,
  "reason": "center of the button"
}

Rules:
- x and y are crop-local coordinates.
- Top-left of the cropped image is (0, 0).
- Do not return full-screen coordinates.
- Do not write prose.
- Do not use Markdown.
- Do not call tools.

Button equivalence:
- '+' means plus/add.
- '-' means minus/subtract/−.
- '*' means multiply/×.
- '/' means divide/÷.
- '=' means equals.
- 'C' means Clear. If C is not visible, CE is acceptable.
"""

READ_DISPLAY_SYSTEM_INSTRUCTION = """
You receive a cropped image containing ONLY Windows Calculator.

Read the Calculator display area.

Return ONLY one JSON object:
{
  "display": "46",
  "confidence": 0.95
}
"""


def ensure_gemini_available() -> bool:
    if genai is None:
        print("[Gemini] google-genai import 실패. pip install google-genai 필요")
        return False

    if "GEMINI_API_KEY" not in os.environ:
        print("[Gemini] GEMINI_API_KEY가 없어 Gemini fallback을 사용할 수 없습니다.")
        return False

    return True


def extract_json_object(text: str) -> Optional[dict]:
    if not text:
        return None

    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        obj = json.loads(cleaned)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = cleaned[start:end + 1]
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass

    return None


def gemini_click_button_fallback(button_label: str, model: str) -> bool:
    if not ensure_gemini_available():
        return False

    client = genai.Client()
    button_label = normalize_button_label(button_label)

    try:
        crop_path, crop_rect = capture_calculator_crop()
    except Exception as exc:
        print(f"[Gemini fallback] crop 생성 실패: {exc}")
        return False

    img = Image.open(crop_path)
    w, h = img.size
    hint = BUTTON_HINTS.get(button_label, f"Button labeled '{button_label}'.")

    prompt = f"""
Target Calculator button: {button_label}

Visual hint:
{hint}

The attached image is a cropped Calculator window only.
Cropped image size: {w} x {h} pixels.
Return crop-local coordinates only.

Return only JSON:
{{"x": <int>, "y": <int>, "confidence": <float>, "reason": "<short reason>"}}
"""

    response = client.models.generate_content(
        model=model,
        contents=[img, prompt],
        config={
            "system_instruction": LOCATE_BUTTON_SYSTEM_INSTRUCTION,
            "temperature": 0.0,
        },
    )

    text = (getattr(response, "text", "") or "").strip()
    print(f"[Gemini fallback 좌표 응답] {text}")

    obj = extract_json_object(text)
    if not obj:
        print("[Gemini fallback] JSON 파싱 실패")
        return False

    try:
        crop_x = int(float(obj["x"]))
        crop_y = int(float(obj["y"]))
        confidence = float(obj.get("confidence", 0.0))
    except Exception as exc:
        print(f"[Gemini fallback] 좌표 파싱 실패: {exc}")
        return False

    if confidence < 0.30:
        print(f"[Gemini fallback] confidence 낮음: {confidence:.2f}")
        return False

    if not (0 <= crop_x < w and 0 <= crop_y < h):
        print(f"[Gemini fallback] crop 좌표 범위 초과: ({crop_x}, {crop_y})")
        return False

    abs_x = crop_rect.left + crop_x
    abs_y = crop_rect.top + crop_y
    print(f"[Gemini fallback 좌표 변환] crop({crop_x},{crop_y}) -> screen({abs_x},{abs_y})")
    mouse_click(abs_x, abs_y)
    time.sleep(BUTTON_ACTION_DELAY_SEC)
    return True


def gemini_read_display_fallback(model: str) -> Optional[str]:
    if not ensure_gemini_available():
        return None

    client = genai.Client()

    try:
        crop_path, _ = capture_calculator_crop()
    except Exception as exc:
        print(f"[Gemini display fallback] crop 생성 실패: {exc}")
        return None

    img = Image.open(crop_path)

    response = client.models.generate_content(
        model=model,
        contents=[
            img,
            'Read the Calculator display value. Return only JSON: {"display": "<value>", "confidence": <float>}',
        ],
        config={
            "system_instruction": READ_DISPLAY_SYSTEM_INSTRUCTION,
            "temperature": 0.0,
        },
    )

    text = (getattr(response, "text", "") or "").strip()
    print(f"[Gemini display fallback 응답] {text}")

    obj = extract_json_object(text)
    if obj and "display" in obj:
        return str(obj["display"])

    return None


# ---------------------------------------------------------------------
# Button execution strategy
# ---------------------------------------------------------------------

OPERATOR_BUTTONS = {"+", "-", "*", "/", "="}


def click_calculator_button(button_label: str, *, strategy: str, model: str) -> bool:
    """
    Execute a Calculator button.

    strategy:
      - uia:    UI Automation only
      - gemini: Gemini visual coordinate only
      - hybrid: UIA first, Gemini fallback

    In hybrid mode, operators are especially protected by UIA.
    """
    button_label = normalize_button_label(button_label)

    print(f"\n--- [버튼 실행] target='{button_label}' | strategy={strategy} ---")

    bring_calculator_to_front()

    if strategy == "uia":
        return invoke_calculator_button_uia(button_label)

    if strategy == "gemini":
        return gemini_click_button_fallback(button_label, model=model)

    # hybrid
    ok = invoke_calculator_button_uia(button_label)
    if ok:
        return True

    print(f"[hybrid] UIA 실패 → Gemini visual fallback 시도: {button_label}")
    return gemini_click_button_fallback(button_label, model=model)


def normalize_number_text(value: str) -> str:
    value = value.strip()
    value = value.replace(",", "")
    value = value.replace(" ", "")
    value = value.replace("DISPLAY=", "")
    value = value.replace("\u2212", "-")
    value = value.replace("−", "-")

    if re.fullmatch(r"-?\d+\.0+", value):
        value = value.split(".")[0]

    return value


def read_and_verify_display(expected_result: str, *, model: str) -> Tuple[str, bool]:
    display_value = read_calculator_display_uia()

    if display_value is None:
        print("[검증] UIA display 읽기 실패 → Gemini fallback")
        display_value = gemini_read_display_fallback(model=model)

    if display_value is None:
        return "", False

    normalized_display = normalize_number_text(display_value)
    normalized_expected = normalize_number_text(expected_result)

    return display_value, normalized_display == normalized_expected


# ---------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------

def run_calculator_workflow_agent(
    *,
    sequence: List[str],
    expected_result: str,
    model: str,
    keep_open: bool,
    close_existing: bool,
    strategy: str,
    debug_screenshots: bool,
) -> bool:
    if strategy in {"gemini", "hybrid"} and not ensure_gemini_available():
        if strategy == "gemini":
            return False
        print("[시스템] Gemini fallback 없이 UIA 중심 hybrid로 계속 진행합니다.")

    print("[시스템] Windows Calculator GUI Agent 시작")
    print(f"[시스템] 버튼 시퀀스: {sequence}")
    print(f"[시스템] 기대 결과: {expected_result}")
    print(f"[시스템] strategy={strategy}")

    open_calculator_at_fixed_position(close_existing=close_existing)

    if debug_screenshots:
        take_screenshot()
        capture_calculator_crop()

    for button in sequence:
        ok = click_calculator_button(button, strategy=strategy, model=model)
        if not ok:
            print(f"❌ 실패: 버튼 '{button}' 실행에 실패했습니다.")
            if debug_screenshots:
                try:
                    capture_calculator_crop()
                    print(f"[디버그] 마지막 crop 이미지 확인: {WSL_CALC_CROP}")
                except Exception:
                    pass
            if not keep_open:
                close_calculator()
            return False

    display_value, success = read_and_verify_display(expected_result, model=model)

    if success:
        print(f"🎉 성공: Calculator 결과가 기대값과 일치합니다. DISPLAY={display_value}")
    else:
        print(f"❌ 실패: Calculator 결과가 기대값과 다릅니다. DISPLAY={display_value}, EXPECTED={expected_result}")
        if debug_screenshots:
            try:
                capture_calculator_crop()
                print(f"[디버그] 마지막 crop 이미지 확인: {WSL_CALC_CROP}")
            except Exception:
                pass

    if not keep_open:
        print("[시스템] 계산 결과 확인을 위해 7초 대기합니다.")
        time.sleep(7.0)
        close_calculator()

    return success


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Robust Windows Calculator GUI Agent using UI Automation + optional Gemini fallback",
    )
    parser.add_argument(
        "--sequence",
        default=" ".join(DEFAULT_SEQUENCE),
        help='Calculator button sequence. Example: "C 1 2 + 3 4 ="',
    )
    parser.add_argument(
        "--expected",
        default=DEFAULT_EXPECTED,
        help='Expected display value. Default: "46"',
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Gemini model name. Default: {DEFAULT_MODEL}",
    )
    parser.add_argument(
        "--strategy",
        choices=["hybrid", "uia", "gemini"],
        default="hybrid",
        help="Button execution strategy. Default: hybrid",
    )
    parser.add_argument(
        "--keep-open",
        action="store_true",
        help="Keep Calculator open after the workflow.",
    )
    parser.add_argument(
        "--no-close-existing",
        action="store_true",
        help="Do not close existing Calculator windows before starting.",
    )
    parser.add_argument(
        "--debug-screenshots",
        action="store_true",
        help="Capture full screen and calculator crop images for debugging.",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    sequence = parse_sequence(args.sequence)

    success = run_calculator_workflow_agent(
        sequence=sequence,
        expected_result=args.expected,
        model=args.model,
        keep_open=args.keep_open,
        close_existing=not args.no_close_existing,
        strategy=args.strategy,
        debug_screenshots=args.debug_screenshots,
    )

    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
