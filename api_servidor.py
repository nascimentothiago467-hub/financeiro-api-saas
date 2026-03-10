import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from datetime import datetime

app = FastAPI(title="Gestão de Licenças Pro")
templates = Jinja2Templates(directory="templates")

DB_URL = "postgresql://postgres:Thiago88106423@db.yeteaatmtwzzdsyeyilu.supabase.co:5432/postgres"

def get_db_connection():
    return psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)

# --- ROTAS ADMIN ---

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request, search: str = ""):
    conn = get_db_connection()
    cur = conn.cursor()
    if search:
        # Busca por nome, documento ou chave
        query = "SELECT * FROM licenses WHERE client_name ILIKE %s OR document ILIKE %s OR key ILIKE %s"
        cur.execute(query, (f'%{search}%', f'%{search}%', f'%{search}%'))
    else:
        cur.execute("SELECT * FROM licenses ORDER BY expires_at DESC")
    
    licenses = cur.fetchall()
    return templates.TemplateResponse("admin.html", {"request": request, "licenses": licenses, "search": search})

@app.post("/admin/generate")
async def generate_license(key: str = Form(...), client_name: str = Form(...), 
                           document: str = Form(...), expires_at: str = Form(...)):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO licenses (key, machine_id, client_name, document, expires_at, status) VALUES (%s, %s, %s, %s, %s, %s)",
        (key.upper(), "", client_name, document, expires_at, "active")
    )
    conn.commit()
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/admin/update-status/{key}")
async def toggle_status(key: str, current_status: str = Form(...)):
    new_status = "blocked" if current_status == "active" else "active"
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE licenses SET status = %s WHERE key = %s", (new_status, key))
    conn.commit()
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/admin/extend/{key}")
async def extend_license(key: str, new_date: str = Form(...)):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE licenses SET expires_at = %s WHERE key = %s", (new_date, key))
    conn.commit()
    return RedirectResponse(url="/admin", status_code=303)