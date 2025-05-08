from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from zipfile import ZipFile
from typing import List
from app.database import init_db, create_project, get_projects, DB_PATH
from app.export_utils import build_single_project_db

import shutil
import os
import json


from app.schemas import ProjectCreate

from app.utils.media import save_media_file, list_media_files

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI()

# CORS для фронтенда
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Инициализируем БД
init_db()

@app.get("/")
def root():
    return {"message": "Сервер конструктора Telegram-ботов запущен"}

@app.post("/projects")
async def create_new_project(
    project: str = Form(...)
):
    """
    Ожидает JSON-представление проекта в поле Form 'project'.
    """
    try:
        data = json.loads(project)
        bot_project = ProjectCreate(**data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка парсинга проекта: {e}")

    project_id = create_project(bot_project)
    return {"status": "created", "project_id": project_id}

@app.post("/projects/{project_id}/media")
async def upload_media(
    project_id: int,
    files: List[UploadFile] = File(...)
):
    """
    Загружает медиа-файлы для проекта через общую утилиту save_media_file.
    Кладёт их в media/{project_id}/, возвращает список имён сохранённых файлов.
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
    Возвращает список загруженных для проекта media-файлов.
    """
    project = get_projects(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")
    files = list_media_files(project_id, media_root=BASE_DIR / "media")
    return {"files": [f.name for f in files]}

@app.get("/projects/{project_id}/export")
def export_bot(project_id: int):
    """
    Генерирует исходники бота из шаблона + медиа + служебные файлы,
    упаковывает в ZIP и возвращает FileResponse.
    """
    project = get_projects(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")

    template_type = project["template_type"]
    template_path = BASE_DIR / "templates" / template_type

    if not template_path.exists():
        raise HTTPException(status_code=404, detail="Шаблон не найден")

    export_dir = BASE_DIR / "exports" / f"project_{project_id}"
    if export_dir.exists():
        shutil.rmtree(export_dir)
    export_dir.mkdir(parents=True)

    # 1) Рендер .j2 → .py
    env = Environment(loader=FileSystemLoader(str(template_path)))
    for tpl in template_path.glob("*.j2"):
        tpl_obj = env.get_template(tpl.name)
        rendered = tpl_obj.render(project=project)
        out_name = tpl.name[:-3]
        (export_dir / out_name).write_text(rendered, encoding="utf-8")

    # 2) .env
    (export_dir / ".env").write_text(f"TOKEN={project['token']}\n", encoding="utf-8")

    # 3) requirements.txt
    deps = [
        "aiogram",
        "python-dotenv",
        "Pillow",
        "openpyxl",
        "apscheduler"
    ]
    (export_dir / "requirements.txt").write_text("\n".join(deps), encoding="utf-8")

    # 4) README.md
    readme = export_dir / "README.md"
    readme.write_text(
        f"# {project['name']}\n\n"
        f"{project['description']}\n\n"
        "## Как запустить бота:\n"
        "```bash\n"
        "pip install -r requirements.txt\n"
        "python bot.py\n"
        "```\n",
        encoding="utf-8"
    )

    # 5) run.py
    run_py = export_dir / "run.py"
    run_py.write_text(
        "\n".join([
            "import os",
            "import subprocess",
            "import sys",
            "",
            "def install_requirements():",
            "    try:",
            "        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])",
            "    except subprocess.CalledProcessError as e:",
            "        print('Ошибка при установке зависимостей:', e)",
            "        sys.exit(1)",
            "",
            "def run_bot():",
            "    from aiogram import Bot, Dispatcher, executor, types",
            "    from dotenv import load_dotenv",
            "",
            "    load_dotenv()",
            "    bot = Bot(token=os.getenv('TOKEN'))",
            "    dp = Dispatcher(bot)",
            "",
            "    @dp.message_handler(commands=['start'])",
            "    async def start(message: types.Message):",
            "        await message.answer('Бот запущен и готов к работе!')",
            "",
            "    executor.start_polling(dp)",
            "",
            "if __name__ == '__main__':",
            "    install_requirements()",
            "    run_bot()",
        ]),
        encoding="utf-8"
    )

    # 6) Копируем медиа через shutil (util используется при загрузке)
    media_src = BASE_DIR / "media" / str(project_id)
    if media_src.exists():
        shutil.copytree(media_src, export_dir / "media")

    # 7) Добавляем Windows-скрипты для удобства запуск/остановки
    start_bat = export_dir / "start_bot.bat"
    start_bat.write_text(r'''@echo off
pip install -r requirements.txt
start "" /B python bot.py > bot.log 2>&1
for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq python.exe" /FO LIST /V ^| findstr /R /C:"Window Title: bot.py"') do set BOT_PID=%%a
echo %BOT_PID% > bot.pid
echo Bot started. PID=%BOT_PID%, logs→bot.log
pause
''', encoding="utf-8")

    stop_bat = export_dir / "stop_bot.bat"
    stop_bat.write_text(r'''@echo off
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

    # 6-bis) Копируем все утилиты (включая dp.py) из app/utils → export_dir/utils
    shutil.copytree(
        BASE_DIR / "app" / "utils",
        export_dir / "utils",
    )
    (export_dir / "utils" / "__init__.py").touch(exist_ok=True)

    # 6-ter) Генерируем базу для бота с записями только этого проекта
    tmp_db = build_single_project_db(
        src_db=DB_PATH,
        schema_db=BASE_DIR / "app" / "schema.db",
        project_id=project_id
    )
    shutil.copy(tmp_db, export_dir / "utils" / "database.db")
    tmp_db.unlink()

    # 8) Упаковка в ZIP
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
