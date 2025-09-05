import sys
import os

import pyocr
import pyocr.builders
import pyautogui
import cv2

from PIL import Image

from time import sleep
from pynput import mouse

TESSERACT_PATH = 'C:\Program Files\Tesseract-OCR'
TESSDATA_PATH = 'C:\Program Files\Tesseract-OCR\\tessdata'

os.environ["PATH"] += os.pathsep + TESSERACT_PATH
os.environ["TESSDATA_PREFIX"] = TESSDATA_PATH


tools = pyocr.get_available_tools()
if len(tools) == 0:
    print("No OCR tool found")
    sys.exit(1)
# The tools are returned in the recommended order of usage
tool = tools[0]
print("Will use tool '%s'" % (tool.get_name()))
# Ex: Will use tool 'libtesseract'

langs = tool.get_available_languages()
print("Available languages: %s" % ", ".join(langs))
lang = langs[0]
print("Will use lang '%s'" % (lang))
# Ex: Will use lang 'fra'
# Note that languages are NOT sorted in any way. Please refer
# to the system locale settings for the default language
# to use.

# ↑PyOCR使う時の呪文、おまじない。

# 範囲指定のためのマウスカーソル座標取得関数。メッセージボックスの左上隅と右下隅で囲まれた範囲をスクリーンショット
def get_click_position(message):
    print(message + " クリックしてください...")
    pos = []

    def on_click(x, y, button, pressed):
        if pressed:
            pos.extend([x, y])
            return False  # Stop listener

    with mouse.Listener(on_click=on_click) as listener:
        listener.join()
    return pos

def PosGet():
    x1, y1 = get_click_position("左上隅の座標")
    print(f"{x1},{y1}")
    x2, y2 = get_click_position("右下隅の座標")
    print(f"{x2},{y2}")

    # PyAutoGuiのregionの仕様のため、相対座標を求める
    x2 -= x1
    y2 -= y1

    return (x1, y1, x2, y2)

# スクリーンショット撮影 → グレースケール → 画像を拡大
def ScreenShot(x1, y1, x2, y2):
    sc = pyautogui.screenshot(region=(x1, y1, x2, y2)) # PosGet関数で取得した座標を使用
    sc.save('TransActor.jpg')
    # あとは画像拡大してみましょうか グレースケールも有効？ OpenCVにも頼ってみよう
    img = cv2.imread('TransActor.jpg')
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    tmp = cv2.resize(gray, (gray.shape[1]*2, gray.shape[0]*2), interpolation=cv2.INTER_LINEAR)
    cv2.imwrite('TransActor.jpg', tmp)

# Image.openメソッドで画像が開かれる。PyOCRで文字認識、文字起こし
# 関数名は翻訳実装の名残
def TranslationActors():
    txt = tool.image_to_string(
        Image.open('TransActor.jpg'),
        lang="jpn",
        builder=pyocr.builders.TextBuilder(tesseract_layout=6)
    ) # 英文を読み取る時はlang="eng"
    print("【原文】\n------------------------------------")
    print(txt)

    '''
    ここまでが文字認識→出力のゾーン
    '''

# 読み取る範囲を決める
x1, y1, x2, y2 = PosGet()

while True:
    ScreenShot(x1, y1, x2, y2)

    TranslationActors()
    sleep(3)                   # 3秒ごとに繰り返す
