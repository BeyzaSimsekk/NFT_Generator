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

# ----------------------------------------- Utilities -----------------------------------------
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

# ----------------------------------------- Image helpers -----------------------------------------
def image_to_mask(img: Image.Image, threshold=10) -> Image.Image:
    """
    Return an 'L' mask where area > threshold becomes 255 (paintable).
    If image has alpha channel, use alpha. Otherwise convert to grayscale and threshold.
    """
    if "A" in img.getbands(): #şeffaflık (alpha: son kanal) bilgisi var mı? yok mu?
        alpha = img.split()[-1].convert("L") # Alpha kanalını al ve gri tonlamaya çevir
        return alpha.point(lambda p: 255 if p > threshold else 0) #point() fonksiyonu, bu işlemi tüm piksellere uygular.
    gray = img.convert("L")
    return gray.point(lambda p: 255 if p > threshold else 0)

def color_layer_from_mask(size, mask: Image.Image, color_rgb: tuple) -> Image.Image:
    """
    Create an RGBA image filled with color_rgb where mask is 255 (alpha from mask).
    Maske görseline göre belirli alanları renklendiren RGBA formatında bir görsel oluşturur.
    Beyaz (255) olan yerler görünür, siyah (0) olan yerler şeffaf olur.
    """
    if mask.mode != "L":
        mask = mask.convert("L")
    # Belirtilen boyutta, seçilen renkle dolu bir RGBA görsel oluştur
    # (255,) → alfa kanalı, başlangıçta tam opak
    color_img = Image.new("RGBA", size, color_rgb + (255,))
    # Maske görselini alfa (şeffaflık) kanalı olarak uygula
    color_img.putalpha(mask)
    # Sonuç olarak sadece maskede beyaz olan yerler renkli görünür
    return color_img

# ----------------------------------------- Core generation -----------------------------------------
# görsel katmanları (layers) toplamak için
def gather_assets(assets_root: Path, layers_order: List[str]) -> Dict[str, List[str]]:
    assets = {}
    for layer in layers_order:
        assets[layer] = list_images(assets_root / layer)
    # mask folder is special (optional): varsa eklenir, yoksa boş liste olur
    assets["masks"] = list_images(assets_root / "masks")
    return assets

def compute_max_combinations(assets_map: Dict[str, List[str]], layers_order: List[str]) -> int:
    counts = [max(1, len(assets_map.get(layer, []))) for layer in layers_order ]
    # If any layer has 0 assets, treat its count as 1 (it will be skipped)
    total = 1
    for c in counts:
        total *= c
    return total

# rastgele bir öğe seçmek için
def select_asset_equal(rng: random.Random, choices: List[str]) -> str: #choices: Seçeneklerin listesi. Örneğin: ["blue.png", "green.png", "red.png"]
    if not choices:
        return None
    # Liste doluysa, rastgele bir öğe seç ve döndür
    return rng.choice(choices)

def generate_collection(
        assets_root: Path, #Ana varlık (assets) klasörünün yolu
        layers_order: List[str], #hangi katmanların hangi sırayla kullanılacağını belirleyen isim listesi
        out_dir: Path, #çıktı klasörü
        num: int, # Üretilmek istenen toplam öğe sayısı
        start_id: int = 1, #Dosya isimlendirme ve edition numarası için başlangıç id’si
        resolution: int = 400, #Üretilen görüntülerin piksel cinsinden kare boyutu.
        seed: int = None, #her çalışmada farklı rastgelelik
        palette: List[str] = None, #rastgele RGB renkler üretilir
        max_attempts_per_item: int = 200 #Her öğe için benzersiz bir kombinasyon yakalanana kadar yapılacak deneme sayısı sınırı.
        # Çakışma (aynı kombinasyonun tekrar üretilmesi) olursa yeniden deniyor; bu parametre sonsuz döngüyü önler.
):
    """
    çıktı klasörünü hazırlar, rastgelelik kaynağını başlatır, varlıkları toplar, olası benzersiz kombinasyon sayısını
    hesaplar ve kullandığın katmanlarda kaç varlık olduğunu kullanıcıya bildirir.
    """
    ensure_dir(out_dir) #out_dir klasörünü oluşturursa oluşturur, varsa hata vermez.
    rng_global = random.Random(seed)
    assets_map = gather_assets(assets_root,layers_order)
    max_possible = compute_max_combinations(assets_map, layers_order)
    print(f"Detected assets (per layer):")
    for layer in layers_order:
        #Her bir layer için assets_map.get(layer, []) uzunluğunu yazdırır; böylece hangi katmanda kaç dosya olduğunu konsolda hızlıca görürsün.
        print(f" {layer}: {len(assets_map.get(layer, []))}")
    if assets_map.get("masks"):
        print(f" masks: {len(assets_map.get('masks'))} (will use masks)")
    print(f"Max unique combinations (theoretical) : {max_possible}")

    if num + start_id - 1 > max_possible:
        print(f"WARNING: Requested {num} items but only {max_possible} unique combinations possible. Will generate at most {max_possible - (start_id - 1)} items.")

    # Daha önce üretilen kombinasyonların özet hashlerini saklar.
    seen_hashes = set()
    # Her üretilen öğe için oluşturulan metadata sözlüklerini toplar. Sonunda index dosyası olarak kaydedilir.
    metadata_list = []
    generated = 0
    target = num
    i = start_id

    # toplam ilerleme hedefini belirler.
    pbar = tqdm(total=min(target, max_possible - (start_id - 1)), desc="Generating")

    # while loopunda kaldım!!!********************************

# ------------------------------------------------ CLI ------------------------------------------------
# def main():