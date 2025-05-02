# app/utils/collage.py

import hashlib
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Разметки для коллажей из 1–9 изображений
LAYOUTS = {
    1: [(0, 0, 900, 1200)],
    2: [(0, 0, 450, 1200), (450, 0, 450, 1200)],
    3: [(0, 0, 600, 1200), (600, 0, 300, 600), (600, 600, 300, 600)],
    4: [(0, 0, 450, 600), (450, 0, 450, 600), (0, 600, 450, 600), (450, 600, 450, 600)],
    5: [(0, 0, 900, 600), (0, 600, 300, 600), (300, 600, 300, 600),
        (600, 600, 300, 600), (300, 0, 300, 600)],
    6: [(x * 300, y * 600, 300, 600) for y in range(2) for x in range(3)],
    7: ([(0, 0, 600, 800), (600, 0, 300, 400), (600, 400, 300, 400)]
        + [(x * 300, 800, 300, 400) for x in range(3)]
        + [(0, 800, 300, 400)]),
    8: [(x * 300, y * 400, 300, 400) for y in range(2) for x in range(4)],
    9: [(x * 300, y * 400, 300, 400) for y in range(3) for x in range(3)],
}

def _compute_hash(image_paths: list[str]) -> str:
    """
    Вычисляет SHA256-хэш по путям к картинкам и их метаданным,
    чтобы при повторном вызове с теми же файлами использовать кеш.
    """
    h = hashlib.sha256()
    for p_str in sorted(image_paths):
        p = Path(p_str)
        stat = p.stat()
        h.update(str(p.resolve()).encode())
        h.update(str(stat.st_mtime).encode())
        h.update(str(stat.st_size).encode())
    return h.hexdigest()

def generate_collage(
    image_paths: list[str],
    output_path: str | Path,
    cache_dir: str | Path | None = None
) -> Path:
    """
    Собирает коллаж из 1–9 изображений.
    Если указан cache_dir, перед рендером проверяет кеш по хэшу.
    Возвращает путь к JPEG-файлу коллажа.
    """
    output_path = Path(output_path)
    # если используем кеширование
    if cache_dir:
        cache_dir = Path(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        key = _compute_hash(image_paths)
        cached = cache_dir / f"{key}.jpg"
        if cached.exists():
            return cached
        output_path = cached
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)

    # параметры холста
    W, H = 900, 1200
    collage = Image.new("RGB", (W, H), "white")
    # шрифт для нумерации (надо убедиться, что arial.ttf доступен)
    try:
        font = ImageFont.truetype("arial.ttf", size=40)
    except IOError:
        font = ImageFont.load_default()

    n = len(image_paths)
    layout = LAYOUTS.get(n, LAYOUTS[9])
    for idx, img_path in enumerate(image_paths):
        bbox = layout[idx]
        x, y, w, h = bbox
        with Image.open(img_path) as img:
            img = img.resize((w, h), Image.ANTIALIAS)
            collage.paste(img, (x, y))
        draw = ImageDraw.Draw(collage)
        draw.text((x + 10, y + 10), str(idx + 1), font=font, fill="white")

    collage.save(output_path, format="JPEG")
    return output_path
