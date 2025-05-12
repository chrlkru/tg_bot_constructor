# backend/app/export_utils.py

import sqlite3
import tempfile
import os
from pathlib import Path
from app.database import init_db, DB_PATH

PROJECT_TABLES = [
    "projects", "products", "faq_entries", "cart_items", "bookings",
    "work_intervals", "helper_entries",
    "moderation_settings", "link_whitelist",
    "quiz_questions"
]

def build_single_project_db(project_id: int) -> Path:
    # 1) создаём пустой файл и закрываем дескриптор
    tmp_fd, tmp_path_str = tempfile.mkstemp(suffix=".db")
    os.close(tmp_fd)

    # 2) инициализируем в нём схему
    init_db(Path(tmp_path_str))

    # 3) копируем данные
    src = sqlite3.connect(DB_PATH)
    dst = sqlite3.connect(tmp_path_str)
    sc, dc = src.cursor(), dst.cursor()

    # 3.1 глобальные настройки

    for key, val in sc.execute("SELECT key,value FROM settings"):
        dc.execute(
            "INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",
            (key, val)
        )

    # 3.2 проектно-специфичные таблицы
    # export_utils.py  (фрагмент цикла)
    for tbl in PROJECT_TABLES:
        cols = [r[1] for r in sc.execute(f"PRAGMA table_info({tbl})")]
        collist = ",".join(cols)

        # --- выбираем правильное поле фильтрации ---------------
        if "project_id" in cols:
            rows = sc.execute(
                f"SELECT {collist} FROM {tbl} WHERE project_id=?",
                (project_id,)
            ).fetchall()
        elif tbl == "projects":
            rows = sc.execute(
                f"SELECT {collist} FROM projects WHERE id=?",
                (project_id,)
            ).fetchall()
        else:
            # таблица глобальная или не привязана к проекту
            rows = []
        # --------------------------------------------------------

        if not rows:
            continue

        placeholders = ",".join("?" * len(cols))
        dc.executemany(
            f"INSERT INTO {tbl}({collist}) VALUES ({placeholders})",
            rows
        )

    dst.commit()
    src.close()
    dst.close()

    return Path(tmp_path_str)
