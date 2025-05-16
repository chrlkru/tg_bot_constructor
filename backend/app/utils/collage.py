# utils/collage.py

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps
import hashlib
import logging

# ─── Новые раскладки 1–9 изображений на холсте 900×1200 ────────────────
LAYOUTS = {
    1: [(0, 0, 900, 1200)],

    2: [(0,   0, 450, 1200),
        (450, 0, 450, 1200)],

    3: [(0,   0, 600, 1200),
        (600, 0, 300, 600),
        (600, 600, 300, 600)],

    4: [(0,   0, 450, 600),  (450,   0, 450, 600),
        (0, 600, 450, 600),  (450, 600, 450, 600)],

    # **5**: две крупные сверху и три поменьше снизу
    5: [
        (0,   0, 450, 600),  (450,   0, 450, 600),
        (0, 600, 300, 600),  (300, 600, 300, 600),  (600, 600, 300, 600)
    ],

    6: [(x * 300, y * 600, 300, 600) for y in range(2) for x in range(3)],

    7: ([(0,   0, 600, 800),   (600,   0, 300, 400),   (600, 400, 300, 400)]
        + [(x * 300, 800, 300, 400) for x in range(3)]
        + [(0, 800, 300, 400)]),

    # **8**: два столбца по четыре ряда
    8: [(x * 450, y * 300, 450, 300) for y in range(4) for x in range(2)],

    9: [(x * 300, y * 400, 300, 400) for y in range(3) for x in range(3)],
}

# ─── Resampling для Pillow 9.x и 10.x+ ──────────────────────────────
try:
    RESAMPLE = Image.Resampling.LANCZOS     # Pillow ≥ 10
except AttributeError:
    RESAMPLE = Image.LANCZOS               # Pillow ≤ 9.x

def _compute_hash(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for p in sorted(paths):
        try:
            st = p.stat()
            h.update(str(p.resolve()).encode())
            h.update(str(st.st_mtime).encode())
            h.update(str(st.st_size).encode())
        except FileNotFoundError:
            continue
    return h.hexdigest()

def generate_collage(
    image_paths: list[str],
    output_path: str | Path,
    cache_dir: str | Path | None = None,
    placeholder: str | Path | None = None
) -> Path:
    """
    Собирает коллаж 900×1200 из 1–9 изображений:
      • отбрасывает несуществующие пути;
      • если valid == 0, берёт placeholder из utils/;
      • сохраняет пропорции через ImageOps.fit;
      • нумерует ячейки с чёрной обводкой для читаемости;
      • опционально кэширует по SHA-256.
    """
    # 1) Фильтруем только существующие файлы
    candidates = [Path(p) for p in image_paths]
    valid = [p for p in candidates if p.is_file()]
    logging.info(f"[collage] valid images: {len(valid)}/{len(candidates)}")

    # 2) Если нет ни одной картинки — используем placeholder
    if not valid:
        if placeholder:
            ph = Path(__file__).parent / placeholder
            if ph.is_file():
                valid = [ph]
                logging.info(f"[collage] placeholder used: {ph.name}")
            else:
                raise FileNotFoundError(f"Placeholder not found: {ph}")
        else:
            raise RuntimeError("No valid images and no placeholder specified")

    # 3) Подготовка кеша
    out_path = Path(output_path)
    if cache_dir:
        cache_dir = Path(cache_dir)
        cache_dir.mkdir(parents=True, exist_ok=True)
        key = _compute_hash(valid)
        cached = cache_dir / f"{key}.jpg"
        if cached.exists():
            return cached
        out_path = cached
    else:
        out_path.parent.mkdir(parents=True, exist_ok=True)

    # 4) Рисуем холст
    W, H = 900, 1200
    collage = Image.new("RGB", (W, H), "white")

    # 5) Шрифт для нумерации
    try:
        font = ImageFont.truetype("arial.ttf", size=40)
    except IOError:
        font = ImageFont.load_default()

    # 6) Выбираем layout
    layout = LAYOUTS.get(len(valid), LAYOUTS[9])

    # 7) Заполняем ячейки
    for idx, img_path in enumerate(valid):
        x, y, w, h = layout[idx]
        with Image.open(img_path) as img:
            frame = ImageOps.fit(img, (w, h), RESAMPLE, centering=(0.5, 0.5))
            collage.paste(frame, (x, y))
        # рисуем номер с обводкой
        draw = ImageDraw.Draw(collage)
        text = str(idx + 1)
        draw.text((x + 10, y + 10), text,
                  font=font, fill="white",
                  stroke_width=2, stroke_fill="black")

    # 8) Сохраняем и возвращаем путь
    collage.save(out_path, format="JPEG")
    logging.info(f"[collage] saved to {out_path}")
    return out_path
