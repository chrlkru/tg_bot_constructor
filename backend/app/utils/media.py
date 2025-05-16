# app/utils/media.py
import os
from pathlib import Path
from typing import Union, List

# Разрешённые расширения и максимальный размер (при желании)
ALLOWED_EXTENSIONS: set[str] = {'.jpg', '.jpeg', '.png', '.gif', '.mp4', '.mp3'}
MAX_FILE_SIZE = 5 * 1024 * 1024   # 5 МБ

# Корень, где лежат media/<project_id>/
MEDIA_ROOT = Path(__file__).resolve().parent.parent / "media"


def is_extension_allowed(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def _resolve_collision(dest_dir: Path, name: str) -> str:
    """
    Если файл с таким именем уже существует, добавляем « _1 », « _2 » … до уникальности.
    """
    stem, ext = os.path.splitext(name)
    counter = 1
    candidate = dest_dir / name
    while candidate.exists():
        candidate = dest_dir / f"{stem}_{counter}{ext}"
        counter += 1
    return candidate.name


def save_media_file(
        project_id: int,
        file_bytes: bytes,
        original_filename: str,
        media_root: Path = MEDIA_ROOT) -> Path:
    """
    Сохраняет файл в media/<project_id>/ под *оригинальным* именем.
    При коллизии дописывает «_1», «_2»…
    Возвращает Path к сохранённому файлу.
    """
    ext = Path(original_filename).suffix.lower()
    if not is_extension_allowed(original_filename):
        raise ValueError(f"Недопустимое расширение файла: {ext}")

    dest_dir = media_root / str(project_id)
    dest_dir.mkdir(parents=True, exist_ok=True)

    # если имя занято — аккуратно делаем уникальное
    final_name = _resolve_collision(dest_dir, original_filename)
    dest_file = dest_dir / final_name
    dest_file.write_bytes(file_bytes)

    return dest_file


def list_media_files(project_id: Union[int, str],
                     media_root: Union[str, Path] = MEDIA_ROOT) -> List[Path]:
    project_dir = Path(media_root) / str(project_id)
    if not project_dir.is_dir():
        return []
    return [p for p in project_dir.iterdir() if p.is_file()]


def delete_media_file(path: Union[str, Path]) -> None:
    try:
        Path(path).unlink(missing_ok=True)
    except Exception:
        pass
