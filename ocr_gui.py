#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GUI wrapper for periodic on-screen OCR using pyocr + Tesseract.
Features:
- 「キャプチャ位置の設定」: 左上→右下の順に画面上をクリックして領域を更新
- 出力領域: 最新の認識結果を表示
- 「Copy」: 出力テキストをクリップボードにコピー
- 3秒ごとに自動でOCR（Tkinter.after で実装）

必要なパッケージ:
  pip install pyocr pyautogui opencv-python pillow pynput

Tesseractのインストールが必要です。
  Windows既定パス例:
    C:\Program Files\Tesseract-OCR
"""

import os
import sys
import traceback
import tkinter as tk
from tkinter import messagebox
from tkinter import scrolledtext
from time import strftime
from typing import Optional, Tuple

import pyocr
import pyocr.builders
import pyautogui
import cv2
import numpy as np
from PIL import Image
from pynput import mouse

# --- Tesseract path settings (edit if your install path differs) ---
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR"
TESSDATA_PATH = r"C:\Program Files\Tesseract-OCR\tessdata"

if os.path.isdir(TESSERACT_PATH):
    os.environ["PATH"] += os.pathsep + TESSERACT_PATH
if os.path.isdir(TESSDATA_PATH):
    os.environ["TESSDATA_PREFIX"] = TESSDATA_PATH

# --- OCR tool initialization ---
tools = pyocr.get_available_tools()
if not tools:
    messagebox.showerror("OCR初期化エラー", "Tesseract/pyocr が見つかりません。Tesseract のインストールと PATH 設定を確認してください。")
    sys.exit(1)

tool = tools[0]
available_langs = set(tool.get_available_languages() or [])
# 優先は日本語、なければ英語
OCR_LANG = "jpn" if "jpn" in available_langs else ("eng" if "eng" in available_langs else None)
if OCR_LANG is None:
    messagebox.showerror("OCR言語エラー", "利用可能なOCR言語が見つかりません。Tesseractの言語データを確認してください。")
    sys.exit(1)


def get_click_position(message: str) -> Tuple[int, int]:
    """Block until the next mouse down; return (x, y)."""
    pos: list[int] = []

    def on_click(x, y, button, pressed):
        if pressed:
            pos.extend([int(x), int(y)])
            return False  # stop listener

    # 小さな案内を出す（非モーダルだと背後に回るのでメッセージのみ印字）
    print(message + " をクリックしてください...")
    with mouse.Listener(on_click=on_click) as listener:
        listener.join()
    return pos[0], pos[1]


def pos_get() -> Tuple[int, int, int, int]:
    """Ask user to click top-left and bottom-right; return (x, y, w, h)."""
    x1, y1 = get_click_position("左上隅")
    x2, y2 = get_click_position("右下隅")
    w = max(1, x2 - x1)
    h = max(1, y2 - y1)
    return x1, y1, w, h


def grab_and_preprocess_region(region: Tuple[int, int, int, int]) -> Optional[Image.Image]:
    """Screenshot region -> grayscale -> enlarge (2x) -> return PIL Image (single channel)."""
    try:
        x, y, w, h = region
        sc_pil = pyautogui.screenshot(region=(x, y, w, h))  # PIL Image RGB
        # Convert to OpenCV for processing
        img = cv2.cvtColor(np.array(sc_pil), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # enlarge 2x
        resized = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_LINEAR)
        return Image.fromarray(resized)  # single-channel PIL image
    except Exception:
        traceback.print_exc()
        return None


def ocr_image(pil_img: Image.Image) -> str:
    """Run OCR using pyocr + Tesseract with layout suitable for a text block (6)."""
    try:
        text = tool.image_to_string(
            pil_img,
            lang=OCR_LANG,
            builder=pyocr.builders.TextBuilder(tesseract_layout=6),
        )
        return text or ""
    except Exception:
        traceback.print_exc()
        return ""


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("スクリーンOCR (pyocr/Tesseract)")
        self.geometry("760x520")
        self.minsize(640, 420)

        # State
        self.region: Optional[Tuple[int, int, int, int]] = None  # (x, y, w, h)
        self.interval_ms = 3000
        self.after_id: Optional[str] = None

        # --- UI ---
        top = tk.Frame(self)
        top.pack(fill=tk.X, padx=10, pady=10)

        self.region_label = tk.Label(top, text="領域: 未設定", anchor="w")
        self.region_label.pack(side=tk.LEFT, expand=True, fill=tk.X)

        self.btn_set_region = tk.Button(top, text="キャプチャ位置の設定", command=self.on_set_region)
        self.btn_set_region.pack(side=tk.RIGHT, padx=5)

        mid = tk.Frame(self)
        mid.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0,10))

        self.output = scrolledtext.ScrolledText(mid, wrap=tk.WORD, height=18)
        self.output.pack(fill=tk.BOTH, expand=True)

        bottom = tk.Frame(self)
        bottom.pack(fill=tk.X, padx=10, pady=(0,10))

        self.status = tk.Label(bottom, text="準備完了", anchor="w")
        self.status.pack(side=tk.LEFT, expand=True, fill=tk.X)

        self.btn_copy = tk.Button(bottom, text="Copy", width=10, command=self.copy_output)
        self.btn_copy.pack(side=tk.RIGHT, padx=5)

        # Auto-start OCR loop (will idle until region is set)
        self.schedule_ocr()

    # --- UI handlers ---
    def on_set_region(self):
        messagebox.showinfo("キャプチャ位置の設定", "左上隅 → 右下隅 の順に、画面上でクリックしてください。")
        # minimize briefly so the user can click behind the window
        try:
            self.withdraw()
            self.after(200, self._do_set_region)
        except Exception:
            # fallback
            self._do_set_region()

    def _do_set_region(self):
        try:
            region = pos_get()
            self.region = region
            x, y, w, h = region
            self.region_label.config(text=f"領域: x={x}, y={y}, w={w}, h={h}")
            self.status.config(text="領域を更新しました")
        except Exception as e:
            messagebox.showerror("領域取得エラー", f"領域の設定に失敗しました: {e}")
        finally:
            # restore window
            try:
                self.deiconify()
                self.lift()
                self.focus_force()
            except Exception:
                pass

    def copy_output(self):
        text = self.output.get("1.0", tk.END).rstrip("\n")
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status.config(text="出力をクリップボードにコピーしました")

    # --- OCR loop ---
    def schedule_ocr(self):
        """Schedule periodic OCR. If region is None, it just reschedules."""
        self.after_id = self.after(self.interval_ms, self.run_ocr_once)

    def run_ocr_once(self):
        if self.region is None:
            self.status.config(text="領域が未設定です。「キャプチャ位置の設定」を押してください。")
        else:
            pil_img = grab_and_preprocess_region(self.region)
            if pil_img is None:
                self.status.config(text="キャプチャ/前処理に失敗しました")
            else:
                text = ocr_image(pil_img)
                ts = strftime("%H:%M:%S")
                if text.strip():
                    self.output.delete("1.0", tk.END)
                    self.output.insert(tk.END, text)
                    self.status.config(text=f"更新 {ts}")
                else:
                    self.status.config(text=f"更新 {ts}（文字なし）")
        # reschedule
        self.schedule_ocr()


if __name__ == "__main__":
    # Improve PyAutoGUI performance on high-DPI displays (optional)
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-Monitor v2
    except Exception:
        pass

    app = App()
    app.mainloop()
