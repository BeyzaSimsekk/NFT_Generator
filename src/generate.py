#!/usr/bin/env python3
"""
Pixel Cat NFT generator — simplified & complete version for your needs.

- No weights (equal probability).
- Uniqueness ensured by SHA256 of selected assets + color.
- Optional palette (if config.json has palette entries they are used; otherwise random RGB).
- Optional masks/ folder. If absent, mask is derived from base or cat layer.
"""

import os
import json
import random
import hashlib
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List
from PIL import Image
from tqdm import tqdm

# ------------------ Utilities ------------------
# klasörün varlığını garanti et
def ensure_dir(p: Path):
    p.mkdir(parents=True,exist_ok=True)

# JSON dosyasını güvenli bir şekilde yükle
def load_json(path:Path) -> Dict:
    if not path.exists():
        return {}
    #with bloğu sayesinde dosya otomatik olarak kapanır
    with path.open("r",encoding="utf-8") as f: #encoding="utf-8" : türkçe karakterli düzgün okusun diye
        return json.load(f)

# klasör içeriğini filtrele
def list_images(folder: Path) -> List[str]:
    if not folder.exists() or not folder.is_dir(): #klasörün içindeki tüm dosya ve klasörleri tek tek döner
        return []
    # Filtrelenen dosyaların (png | webp) sadece adlarını (f.name) alır.
    return [f.name for f in sorted(folder.iterdir()) if f.suffix.lower() in (".png", ".webp")]

# RGB -> HEX
# "{:02x}" → Bu bir formatlama ifadesi:
    # : → Format başlıyor.
    # 02 → Sayı 2 karakter uzunluğunda olacak. Gerekirse başına 0 koyar.
    # x → Sayıyı hexadecimal (onaltılık) olarak yaz.
        # Örneğin: 255 → ff, 0 → 00, 128 → 80
def hex_from_rgb(rgb):
    return "#{:02x}{:02x}{:02x}".format(*rgb)

# HEX -> RGB
def rgb_from_hex(hexstr):
    hs = hexstr.lstrip("#")
    return tuple(int(hs[i:i+2], 16) for i in (0,2,4)) #Her parçayı onaltılık sayıdan normal sayıya çevirir, Sonuçları bir tuple içine alır






