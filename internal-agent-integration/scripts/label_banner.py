"""圖片正規化與標籤橫幅（需要 Pillow）。

標籤（例如 ``IMG S03-1``）是「判讀結果對應到哪一張圖」的唯一依據，
必須讓模型**從圖片內容本身**讀得到：檔名與 prompt 裡的順序清單都在圖片外面，
平台若沒把檔名交給模型、或沒保持附件順序，結果就會錯位而沒人發現。

所以在圖片**上方接一條橫幅**印上標籤（不覆蓋原圖——工地照片上緣常有日期戳記）。
模型回報它讀到的 ``visible_label``，對應以它為準。

用法::

    from label_banner import stage_image
    path = stage_image("raw/photo.png", "IMG S03-1", out_dir)
    # -> out_dir/IMG_S03-1.jpg，上傳後以 {"type":"file"} 引用
"""
from __future__ import annotations

import io
import logging
import re
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

log = logging.getLogger(__name__)

MAX_EDGE = 1600            # 長邊縮到這個大小，降低上傳量又保留判讀所需細節
JPEG_QUALITY = 85
MIN_PIXELS = 6400          # 低於此面積視為 logo / icon，不送判讀

BANNER_MIN_HEIGHT = 34
BANNER_RATIO = 0.055       # 橫幅高度佔寬度的比例，大圖小圖看起來一致
BANNER_BG = (17, 19, 24)
BANNER_FG = (255, 255, 255)

# 標籤只用 ASCII，不需要 CJK 字型；依序嘗試，全落空就用 Pillow 內建字型
_FONT_CANDIDATES = (
    "DejaVuSans-Bold.ttf", "DejaVuSans.ttf",   # Linux
    "arialbd.ttf", "arial.ttf",                # Windows
    "Helvetica.ttc", "Arial.ttf",              # macOS
)


@lru_cache(maxsize=16)
def _font(size: int) -> ImageFont.ImageFont:
    for name in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    log.warning("找不到 TrueType 字型，標籤橫幅改用 Pillow 內建字型")
    try:
        return ImageFont.load_default(size=size)
    except TypeError:          # Pillow < 10.1
        return ImageFont.load_default()


def draw_label_banner(im: Image.Image, label: str) -> Image.Image:
    """在圖片上方接一條橫幅並印上標籤，回傳新圖片。"""
    src = im if im.mode == "RGB" else im.convert("RGB")
    w, h = src.size
    band = max(BANNER_MIN_HEIGHT, int(w * BANNER_RATIO))
    font = _font(max(12, int(band * 0.62)))
    canvas = Image.new("RGB", (w, h + band), BANNER_BG)
    canvas.paste(src, (0, band))
    draw = ImageDraw.Draw(canvas)
    left, top, right, bottom = draw.textbbox((0, 0), label, font=font)
    x = max(4, (w - (right - left)) // 2) - left
    y = max(0, (band - (bottom - top)) // 2) - top
    draw.text((x, y), label, font=font, fill=BANNER_FG)
    return canvas


def is_too_small(path: str | Path, min_pixels: int = MIN_PIXELS) -> bool:
    with Image.open(path) as im:
        w, h = im.size
    return w * h < min_pixels


def normalise(path: str | Path, max_edge: int = MAX_EDGE) -> Image.Image:
    """依 EXIF 轉正、去透明、縮到長邊 max_edge。"""
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im)
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            bg = Image.new("RGB", im.size, (255, 255, 255))
            bg.paste(im, mask=im.split()[-1])
            im = bg
        else:
            im = im.convert("RGB")
        im.thumbnail((max_edge, max_edge))
        return im.copy()


def label_to_filename(label: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", label).strip("_") + ".jpg"


def stage_image(src: str | Path, label: str, out_dir: str | Path, *,
                max_edge: int = MAX_EDGE, quality: int = JPEG_QUALITY) -> Path:
    """正規化 + 畫橫幅 + 存成以標籤命名的 JPEG，回傳路徑。"""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    img = draw_label_banner(normalise(src, max_edge), label)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality, optimize=True)
    dest = out / label_to_filename(label)
    dest.write_bytes(buf.getvalue())
    return dest


def check_labels(expected: list[str], findings: list[dict]) -> dict:
    """以模型回報的 visible_label 對回送出的標籤。

    回傳 {"matched": {label: finding}, "resend": [label...], "unreported": bool}。
    ``resend`` 裡的那幾張請**一次一張**重送；重送後仍對不上就捨棄並標示「可能錯位」。
    整批都沒有 visible_label 時 unreported=True：沿用模型自報的 label 並註明「本次無法查核」。
    """
    expected_set = set(expected)
    matched: dict[str, dict] = {}
    if findings and not any((f or {}).get("visible_label") for f in findings):
        for f in findings:
            lab = str((f or {}).get("label") or "").strip()
            if lab in expected_set and lab not in matched:
                matched[lab] = f
        return {"matched": matched, "resend": [], "unreported": True}
    for f in findings:
        seen = str((f or {}).get("visible_label") or "").strip()
        if seen in expected_set and seen not in matched:
            matched[seen] = f
    resend = [lab for lab in expected if lab not in matched]
    return {"matched": matched, "resend": resend, "unreported": False}
