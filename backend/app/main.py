from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from zipfile import ZipFile
from typing import List
import shutil
import os
import json

from app.database import init_db, create_project, get_projects
from app.schemas import BotProject

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
        bot_project = BotProject(**data)
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
    Загружает медиа-файлы для проекта.
    Кладёт их в папку media/{project_id}/
    """
    project = get_projects(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Проект не найден")

    media_dir = BASE_DIR / "media" / str(project_id)
    media_dir.mkdir(parents=True, exist_ok=True)

    for upload in files:
        dest = media_dir / upload.filename
        with open(dest, "wb") as f:
            f.write(await upload.read())

    return {"status": "media_uploaded", "count": len(files)}

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

    # 1) Сгенерировать все .j2 → .py (и другие) из шаблона
    env = Environment(loader=FileSystemLoader(str(template_path)))
    for tpl in template_path.glob("*.j2"):
        tpl_obj = env.get_template(tpl.name)
        rendered = tpl_obj.render(project=project)
        out_name = tpl.name[:-3]  # убираем '.j2'
        (export_dir / out_name).write_text(rendered, encoding="utf-8")

    # 2) .env
    (export_dir / ".env").write_text(f"TOKEN={project['token']}\n", encoding="utf-8")

    # 3) requirements.txt
    deps = [
        "aiogram",
        "python-dotenv",
        "Pillow",
        "openpyxl"
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

    # 6) Копируем медиа, если они есть
    media_src = BASE_DIR / "media" / str(project_id)
    if media_src.exists():
        shutil.copytree(media_src, export_dir / "media")

    # 7) Упаковка в ZIP
    zip_path = BASE_DIR / "exports" / f"project_{project_id}.zip"
    with ZipFile(zip_path, "w") as zipf:
        for file in export_dir.rglob("*"):
            zipf.write(file, arcname=file.relative_to(export_dir))

    # 8) Удаляем временную папку
    shutil.rmtree(export_dir)

    return FileResponse(
        path=str(zip_path),
        filename=f"{project['name']}.zip",
        media_type="application/zip"
    )
