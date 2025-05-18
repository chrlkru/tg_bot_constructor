# backend/app/main.py
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from zipfile import ZipFile
from typing import List
from app.seeders import apply_seed
from app.database      import init_db, create_project, get_projects, DB_PATH
from app.export_utils  import build_single_project_db
from app.schemas       import ProjectCreate
from app.utils.media   import save_media_file, list_media_files
import logging
import traceback
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("uvicorn.error")
import shutil
import os
import json

# вместо "from utils import order_db" и пр.:
from app.utils         import order_db as db
from app.utils.collage import generate_collage

# --- какие utils нужны какому боту ---------------------------------
BOT_UTILS = {
    "order_bot": [
        "utils/order_db.py",
        "utils/collage.py",
        "utils/media.py",
    ],
    "faq_bot": [
        "utils/faq_db.py",
        "utils/media.py",
    ],
    "helper_bot": [
        "utils/helper_db.py",
        "utils/media.py",
    ],
    "feedback_bot": [
        "utils/feedback_db.py",
    ],
    "moderator_bot": [
        "utils/moderator_db.py",
    ],
    "quiz_bot": [                     # у квиза БД нет
        "utils/media.py",             # только скачивание картинок для вопросов
    ],
    "smart_booking_crm": [
        "utils/booking_db.py",
        "utils/inline_calendar.py",
        "utils/media.py",
    ],
}

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(debug=False)


# CORS для фронтенда
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173","http://172.20.10.3:5173","http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# инициализируем основную БД конструктора
init_db()
@app.exception_handler(Exception)
async def all_exception_handler(request: Request, exc: Exception):
    # Логируем полный traceback
    tb = traceback.format_exc()
    logger.error(f"Unhandled error at {request.url}:\n{tb}")
    # Отдаём клиенту JSON с сообщением (можно убрать текст исключения в проде)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error", "error": str(exc)}
    )
@app.get("/")
def root():
    return {"message": "Сервер конструктора Telegram-ботов запущен"}

@app.post("/projects")
async def create_new_project(project: str = Form(...)):
    """
    Ожидает JSON-строку проекта в multipart-form поле `project`.
    """
    try:
        data = json.loads(project)
        bot_project = ProjectCreate(**data)
    except Exception as e:
        raise HTTPException(status_code=400,
                            detail=f"Ошибка парсинга проекта: {e}")

    # 1) создаём запись и получаем ID
    project_id = create_project(bot_project)

    # 2) если seed передан — применяем его
    if bot_project.seed is not None:
        apply_seed(project_id, bot_project.seed)

    return {"status": "created", "project_id": project_id}

@app.post("/projects/{project_id}/media")
async def upload_media(
    project_id: int,
    files: List[UploadFile] = File(...)
):
    """
    Загружает медиа-файлы для проекта через save_media_file.
    Кладёт их в media/{project_id}/, возвращает список имён.
    """
    project = get_projects(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")

    saved = []
    for upload in files:
        data = await upload.read()
        try:
            path = save_media_file(
                project_id=project_id,
                file_bytes=data,
                original_filename=upload.filename,
                media_root=BASE_DIR / "media"
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        saved.append(path.name)

    return {"status": "media_uploaded", "files": saved}

@app.get("/projects/{project_id}/media")
def list_media(project_id: int):
    """
    Возвращает список загруженных для проекта медиа-файлов.
    """
    project = get_projects(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    files = list_media_files(project_id, media_root=BASE_DIR / "media")
    return {"files": [f.name for f in files]}

@app.get("/projects/{project_id}/export")
def export_bot(project_id: int):
    """
    Генерирует исходники бота, запаковывает в ZIP и возвращает FileResponse.
    """
    project = get_projects(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")

    template_type = project["template_type"]
    template_path = BASE_DIR / "templates" / template_type
    if not template_path.exists():
        raise HTTPException(status_code=404, detail="Шаблон не найден")

    # временная папка для сборки
    export_dir = BASE_DIR / "exports" / f"project_{project_id}"
    if export_dir.exists():
        shutil.rmtree(export_dir)
    export_dir.mkdir(parents=True)

    # 1) Рендерим все *.j2 → *.py
    env = Environment(loader=FileSystemLoader(str(template_path)))
    jinja_ctx = {
        "project_id": project_id,
        "admin_chat_id": project["content"].get("admin_chat_id", 0),
        "project": project,
    }
    for tpl in template_path.glob("*.j2"):
        rendered = env.get_template(tpl.name).render(**jinja_ctx)
        (export_dir / tpl.stem).write_text(rendered, encoding="utf-8")


    # 2) .env
    (export_dir / ".env").write_text(f"TOKEN={project['token']}\n", encoding="utf-8")

    # 3) requirements.txt
    deps = ["aiogram", "python-dotenv", "Pillow", "openpyxl", "apscheduler"]
    (export_dir / "requirements.txt").write_text("\n".join(deps), encoding="utf-8")

    # 4) README.md
    (export_dir / "README.md").write_text(
        f"# {project['name']}\n\n"
        f"{project.get('description','')}\n\n"
        "## Как запустить бота:\n"
        "```bash\n"
        "pip install -r requirements.txt\n"
        "python run.py\n"
        "```\n",
        encoding="utf-8"
    )

    # 5) run.py — единый entry-point для всех шаблонов
    run_py = export_dir / "run.py"
    run_py.write_text(
        "\n".join([
    "#!/usr/bin/env python3",
    "import logging",
    "import asyncio",
    "from dotenv import load_dotenv",
    "",
    f"from {template_type} import bot, dp, setup_bot_commands",
    "",
    "# 1) Логирование — формат даты через datefmt",
    'logging.basicConfig(',
    '    level=logging.INFO,',
    '    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",',
    '    datefmt="%Y-%m-%d %H:%M:%S"',
    ')',
    'logging.getLogger("aiogram").setLevel(logging.DEBUG)',
    "",
    "async def main():",
    "    load_dotenv()",
    "    await setup_bot_commands(bot)",
    "    await dp.start_polling(bot, skip_updates=True)",
    "",
    "if __name__ == '__main__':",
    "    asyncio.run(main())",
]
),
        encoding="utf-8"
    )

    # 6) Копируем медиа
    media_src = BASE_DIR / "media" / str(project_id)
    if media_src.exists():
        shutil.copytree(media_src, export_dir / "media"/ str(project_id))

    # 7) Генерируем Windows-скрипты
    # 7.1) start_bot.bat
    (export_dir / "start_bot.bat").write_text(r'''@echo off
pushd %~dp0
pip install -r requirements.txt
start "" /B python run.py > bot.log 2>&1
for /f "tokens=2" %%a in ('
    tasklist /FI "IMAGENAME eq python.exe" /FO LIST /V 
    ^| findstr /R /C:"Window Title: run.py"
') do set BOT_PID=%%a
echo %BOT_PID% > bot.pid
echo Bot started. PID=%BOT_PID%, logs→bot.log
cmd /k rem
''', encoding="utf-8")

    # 7.2) stop_bot.bat
    (export_dir / "stop_bot.bat").write_text(r'''@echo off
if not exist bot.pid (
  echo bot.pid not found. Bot may not be running.
  pause
  exit /b
)
set /p BOT_PID=<bot.pid
taskkill /PID %BOT_PID% /F >nul 2>&1
if errorlevel 1 (
  echo Could not find process %BOT_PID%. It may have already exited.
) else (
  echo Process %BOT_PID% stopped.
)
del bot.pid
pause
''', encoding="utf-8")

    # 8) Копируем утилиты конструктора только нужные файлы
    bot_name = template_type  # или project["template_name"], если ты действительно так называешь
    utils_dir = export_dir / "utils"
    utils_dir.mkdir(parents=True, exist_ok=True)

    for rel_path in BOT_UTILS.get(bot_name, []):
        src = BASE_DIR / rel_path
        dst = export_dir / rel_path
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dst)

    # 9) Генерируем отдельную БД только для этого проекта
    tmp_db = build_single_project_db(project_id)

    db_name = {
        "order_bot": "order_bot.db",
        "faq_bot": "faq_bot.db",
        "helper_bot": "helper_bot.db",
        "moderator_bot": "moderator_bot.db",
        "feedback_bot": "feedback_bot.db",
        "smart_booking_crm": "booking_bot.db",
    }.get(template_type, "database.db")  # fallback для старых шаблонов

    shutil.copy(tmp_db, export_dir / "utils" / db_name)
    tmp_db.unlink()

    # 10) Упаковываем в ZIP и возвращаем
    zip_path = BASE_DIR / "exports" / f"project_{project_id}.zip"
    with ZipFile(zip_path, "w") as zipf:
        for file in export_dir.rglob("*"):
            zipf.write(file, arcname=file.relative_to(export_dir))

    shutil.rmtree(export_dir)

    return FileResponse(
        path=str(zip_path),
        filename=f"{project['name']}.zip",
        media_type="application/zip"
    )
