import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            template_type TEXT,
            description TEXT,
            token TEXT,       -- добавляем токен сюда
            content TEXT
        )
    """)
    conn.commit()
    conn.close()

def create_project(project):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO projects (name, template_type, description, token, content)
        VALUES (?, ?, ?, ?, ?)
    """, (
        project.name,
        project.template_type,
        project.description,
        project.token,
        json.dumps(project.content)
    ))
    conn.commit()
    project_id = cur.lastrowid
    conn.close()
    return project_id

def get_projects(project_id=None):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    if project_id:
        cur.execute("SELECT * FROM projects WHERE id=?", (project_id,))
        row = cur.fetchone()
        conn.close()
        if row:
            return {
                "id": row[0],
                "name": row[1],
                "template_type": row[2],
                "description": row[3],
                "token": row[4],  # <--- добавлено
                "content": json.loads(row[5])  # индекс сдвинулся
            }
        return None
    else:
        cur.execute("SELECT * FROM projects")
        rows = cur.fetchall()
        conn.close()
        return [
            {
                "id": row[0],
                "name": row[1],
                "template_type": row[2],
                "description": row[3],
                "token": row[4],  # <--- добавлено
                "content": json.loads(row[5])  # индекс сдвинулся
            } for row in rows
        ]
