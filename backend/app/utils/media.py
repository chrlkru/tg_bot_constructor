# app/utils/media.py

import os
from pathlib import Path
from uuid import uuid4
from typing import Union, List

# Разрешённые расширения и максимальный размер файла
ALLOWED_EXTENSIONS: set[str] = {'.jpg', '.jpeg', '.png', '.gif', '.mp4', '.mp3'}
MAX_FILE_SIZE: int = 5 * 1024 * 1024  # 5 МБ

def is_extension_allowed(filename: str, allowed: set[str] = ALLOWED_EXTENSIONS) -> bool:
    """
    Проверяет, что расширение файла в списке разрешённых.
    """
    return Path(filename).suffix.lower() in allowed

def save_media_file(
    project_id: Union[int, str],
    file_bytes: bytes,
    original_filename: str,
    media_root: Union[str, Path] = "media",
    allowed_extensions: set[str] = ALLOWED_EXTENSIONS,
    max_size: int = MAX_FILE_SIZE
) -> Path:
    """
    Сохраняет байты файла в папку media/<project_id>/, валидируя расширение и размер.
    Возвращает pathlib.Path к сохранённому файлу.
    """
    ext = Path(original_filename).suffix.lower()
    if ext not in allowed_extensions:
        raise ValueError(f"Недопустимое расширение файла: {ext}")
    if len(file_bytes) > max_size:
        raise ValueError(f"Размер файла {len(file_bytes)} превышает лимит {max_size} байт")
    root = Path(media_root)
    project_dir = root / str(project_id)
    project_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}{ext}"
    filepath = project_dir / filename
    with filepath.open("wb") as f:
        f.write(file_bytes)
    return filepath

def list_media_files(
    project_id: Union[int, str],
    media_root: Union[str, Path] = "media"
) -> List[Path]:
    """
    Возвращает список pathlib.Path всех файлов в media/<project_id>/.
    """
    project_dir = Path(media_root) / str(project_id)
    if not project_dir.exists() or not project_dir.is_dir():
        return []
    return [p for p in project_dir.iterdir() if p.is_file()]

def delete_media_file(path: Union[str, Path]) -> None:
    """
    Удаляет указанный медиа-файл, если он существует.
    """
    p = Path(path)
    try:
        p.unlink()
    except FileNotFoundError:
        pass
