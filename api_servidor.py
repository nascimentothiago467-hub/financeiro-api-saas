import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from datetime import datetime

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# COLE SUA URI DO SUPABASE AQUI ABAIXO:
DB_URL = "postgresql://postgres:Thiago88106423@db.yeteaatmtwzzdsyeyilu.supabase.co:5432/postgres"

def get_db_connection():
    return psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)

class LicenseRequest(BaseModel):
    license_key: str
    machine_id: str

@app.post("/verify-license")
async def verify_license(data: LicenseRequest):
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT * FROM licenses WHERE key = %s", (data.license_key,))
    license = cur.fetchone()
    
    if not license:
        return {"status": "invalid", "message": "Chave não encontrada."}
    
    # Se a licença está vazia, vincula ao hardware do primeiro que usar
    if not license['machine_id']:
        cur.execute("UPDATE licenses SET machine_id = %s, status = 'active' WHERE key = %s", 
                    (data.machine_id, data.license_key))
        conn.commit()
        license['machine_id'] = data.machine_id

    if license['machine_id'] != data.machine_id:
        return {"status": "blocked", "message": "Licença em uso em outro computador."}
    
    expires_at = license['expires_at']
    if expires_at < datetime.now().date():
        return {"status": "expired", "message": f"Vencida em {expires_at}"}
    
    return {"status": "success", "message": "Ativado!", "expires_at": str(expires_at)}

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM licenses")
    licenses = cur.fetchall()
    return templates.TemplateResponse("admin.html", {"request": request, "licenses": licenses})

@app.post("/admin/generate")
async def generate_license(key: str = Form(...), client_name: str = Form(...), expires_at: str = Form(...)):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO licenses (key, machine_id, client_name, expires_at, status) VALUES (%s, %s, %s, %s, %s)",
            (key, "", client_name, expires_at, "pending")
        )
        conn.commit()
    except:
        pass
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/admin/delete/{key}")
async def delete_license(key: str):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM licenses WHERE key = %s", (key,))
    conn.commit()
    return RedirectResponse(url="/admin", status_code=303)