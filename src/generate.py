#!/usr/bin/env python3
"""
Pixel Cat NFT generator — simplified & complete version for your needs.

- No weights (equal probability).
- Uniqueness ensured by SHA256 of selected assets + color.
- Optional palette (if config.json has palette entries they are used; otherwise random RGB).
- Optional masks/ folder. If absent, mask is derived from base or cat layer.
"""

#*********************************** MASK OLMADANKİ HALİNİ DENE BİR ARA****************************************
import os
import json
import random
import hashlib
import argparse
from pathlib import Path
from datetime import datetime, timezone
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

    # Üretilecek hedefe ulaşılmadıysa ve hâlâ benzersiz kombinasyon üretilebiliyorsa devam et
    while generated < target and (i - start_id) < max_possible:
        attempts = 0
        made = False

        # Bu öğe için benzersiz kombinasyon bulmak üzere denemelere başla
        while attempts < max_attempts_per_item:
            attempts += 1
            # Her deneme için farklı ama kontrollü rastgelelik üret
            rng = random.Random((seed or 0)^ i ^ attempts)
            # Seçilen varlıklar ve açılan görselleri tutacak yapılar
            selected={}
            images={}

            # choose asset per layer equally (Her katman için eşit olasılıkla bir görsel seç)
            for layer in layers_order:
                choices = assets_map.get(layer, []) # Katmana ait görsellerin listesi
                chosen = select_asset_equal(rng, choices) if choices else None  # Rastgele seçim yap
                if chosen:
                    selected[layer] = chosen  # Seçilen dosya adını kaydet
                    img = Image.open(assets_root / layer / chosen).convert("RGBA") # Görseli aç ve RGBA formatına çevir
                    if img.size != (resolution, resolution):
                        img = img.resize((resolution, resolution), Image.NEAREST)
                    images[layer]=img # Görseli katmanlar sözlüğüne ekle

            #decide mask: prefer explicit masks folder
            mask = None
            if assets_map.get("masks"):
                mask_choice = select_asset_equal(rng, assets_map["masks"])
                mask = Image.open(assets_root / "masks" / mask_choice).convert("L")
                if mask.size != (resolution,resolution):
                    mask = mask.resize((resolution, resolution), Image.NEAREST)
                selected["mask"] = mask_choice
            else:
                # derive mask from base if exists
                if "base" in images:
                    mask = image_to_mask(images["base"])
                else:
                    mask = Image.new("L", (resolution, resolution), 0)

            # choose color: from palette if provided else random
            if palette:
                color_hex = rng.choice(palette)
                color_rgb = rgb_from_hex(color_hex)
            else:
                color_rgb = (rng.randint(0,255), rng.randint(0,255), rng.randint(0,255))
                color_hex = hex_from_rgb(color_rgb)
            selected["color"] = color_hex

            # Compose: background -> colored body -> cat outline -> other overlays (in order)
            # start canvas
            if "backgrounds" in images:
                canvas = images["backgrounds"].copy()
            else:
                canvas = Image.new("RGBA", (resolution, resolution), (255,255,255,0))

            # colored body layer from mask
            color_layer = color_layer_from_mask((resolution,resolution), mask, color_rgb)
            canvas = Image.alpha_composite(canvas,color_layer)

            if "cat" in images:
                canvas= Image.alpha_composite(canvas,images["cat"])

            # then overlays: after cat in layers_order (outline dan sonra detay katmanları için)
            after_cat = False
            for layer in layers_order:
                if layer == "cat":
                    after_cat = True
                    continue
                if not after_cat:
                    continue
                if layer in ("backgrounds","base"):
                    continue
                if layer in images:
                    canvas = Image.alpha_composite(canvas, images[layer])

            # uniqueness hash
            combo_obj = {"selected": selected}
            combo_str = json.dumps(combo_obj, sort_keys=True, ensure_ascii=False)
            combo_hash = hashlib.sha256(combo_str.encode()).hexdigest()
            if combo_hash in seen_hashes:
                # collision - try again
                continue
            seen_hashes.add(combo_hash)

            # save image + metadata
            filename = f"nft_{i:06d}.png"
            print("Saving:", out_dir / filename)
            canvas.save(out_dir / filename)

            # Metadata için özellikleri (attributes) bir listeye ekle
            attributes = []
            for k,v in selected.items():
                if k == "color":
                    # Renk bilgisi özel bir alan olarak eklenir
                    attributes.append({"trait_type" : "color", "value": v})
                else:
                    # Diğer katmanlar (örneğin: base, eyes, nose) trait olarak eklenir
                    attributes.append({"trait_type" : k, "value": v})

            metadata = {
                "name": f"Pixel Cat #{i}",
                "description": "Programmatically generated Pixel Cat",
                "image": filename,
                "edition": i,
                "attributes": attributes,
                "hash": combo_hash,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

            with open(out_dir / f"nft_{i:06d}.json", "w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)

            metadata_list.append(metadata)
            generated += 1
            i += 1
            made = True
            pbar.update(1)
            break

        if not made:
            # couldn't find a unique combo for this index after attempts
            print(f"Could not produce unique item for id={i} after {max_attempts_per_item} attempts. Stopping..")
            break

    pbar.close()

    # write index
    with open(out_dir / "metadata_index.json", "w", encoding="utf-8") as f:
        json.dump(metadata_list, f, ensure_ascii=False, indent=2)

    print(f"Done. Generated {generated} items. Files saved to: {out_dir}")

# ------------------------------------------------ CLI ------------------------------------------------
def main():
    # Komut satırı argümanlarını tanımlamak için bir parser oluştur
    parser = argparse.ArgumentParser(description="Pixel Cat NFT Generator (equal weights, uniqueness)")
    parser.add_argument("--assets", type=str, default="assets",help="assets root folder")
    parser.add_argument("--config", type=str, default="config.json", help="config json path")
    parser.add_argument("--num", type=int, default=10, help="How many NFTs to generate")
    parser.add_argument("--start", type=int, default=1, help="start edition number")
    parser.add_argument("--resolution", type=int, default=None, help="output resolution (overrides config)")
    parser.add_argument("--seed", type=int, default=None, help="random seed (optional)")
    # Tüm argümanları parse edip `args` nesnesine aktarır
    args = parser.parse_args()
    """
    Bu yapı sayesinde terminalden şöyle komutlar verebilirsin:
        `python generate.py --assets my_assets --num 50 --resolution 400 --seed 42`
    """

    # config dosyasını yükle (yoksa boş sözlük kullan)
    cfg = load_json(Path(args.config)) if Path(args.config).exists() else {}
    # Katman sırasını config’ten al, yoksa varsayılan sırayı kullan
    layers_order = cfg.get("layers_order", ["backgrounds", "base", "cat", "eyes", "nose"])
    # Config’teki çözünürlüğü al
    conf_res = cfg.get("resolution", 400)
    # Komut satırından çözünürlük verildiyse onu kullan, yoksa config’tekini
    resolution = args.resolution if args.resolution else conf_res
    palette = cfg.get("palette") if cfg.get("palette") else None
    # Çıktı klasörünü config’ten al, yoksa "output" klasörünü kullan
    out_dir = Path(cfg.get("output_dir", "output"))

    # NFT koleksiyonunu üret
    generate_collection(
        assets_root=Path(args.assets),
        layers_order=layers_order,
        out_dir=out_dir,
        num=args.num,
        start_id=args.start,
        resolution=resolution,
        seed=args.seed,
        palette=palette,
    )

"""KODU AŞAĞIDAKİ GİBİ ÇALIŞTIRMA SEBEBİ:
    - Kodun hem modül gibi başka projelerde kullanılabilir,
    - Hem de doğrudan çalıştırılabilir hale gelir.
"""
if __name__ == "__main__":
    main()









