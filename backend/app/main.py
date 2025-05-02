# main.py

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

    # 6) Копируем медиа через shutil (util используется при загрузке)
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
