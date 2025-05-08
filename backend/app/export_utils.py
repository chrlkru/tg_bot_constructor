# backend/app/export_utils.py
import sqlite3, tempfile, shutil
from pathlib import Path
from app.database import init_db

PROJECT_TABLES = [
    "projects","products","faq_entries","cart_items","bookings",
    "work_intervals","helper_entries",
    "moderation_settings","link_whitelist",
    "quiz_questions"           # ← НОВОЕ
]


def build_single_project_db(src_db: Path, schema_db: Path, project_id: int) -> Path:
    # 1. создаём временный файл и копируем чистую схему
    tmp_path = Path(tempfile.mkstemp(suffix=".db")[1])
    shutil.copyfile(schema_db, tmp_path)

    # 2. открываем обе базы
    src, dst = sqlite3.connect(src_db), sqlite3.connect(tmp_path)
    sc, dc = src.cursor(), dst.cursor()

    # 3. копируем settings (глобальная)
    dc.executemany("INSERT INTO settings(key,value) VALUES(?,?)",
                   sc.execute("SELECT key,value FROM settings"))

    # 4. копируем таблицы, связанные с project_id
    for tbl in PROJECT_TABLES:
        cols = [row[1] for row in sc.execute(f"PRAGMA table_info({tbl})")]
        collist = ",".join(cols)
        rows = sc.execute(
            f"SELECT {collist} FROM {tbl} WHERE project_id=?",
            (project_id,)
        )
        if rows.rowcount == 0:
            continue
        placeholders = ",".join("?" * len(cols))
        dc.executemany(
            f"INSERT INTO {tbl}({collist}) VALUES ({placeholders})", rows
        )

    dst.commit()
    src.close(); dst.close()
    return tmp_path
