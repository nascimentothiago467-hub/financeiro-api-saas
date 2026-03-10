import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from datetime import datetime
import os

app = FastAPI(title="Gestão de Licenças SaaS - Encom")
templates = Jinja2Templates(directory="templates")

# --- CONFIGURAÇÃO DO BANCO DE DATOS ---
# Lembre-se de usar a porta 6543 e o final ?pgbouncer=true
# Substitua o '*' pela sua senha (codifique @ como %40 e # como %23)
DB_URL = "postgresql://postgres.yeteaatmtwzzdsyeyilu:Thiago88106423@aws-0-sa-east-1.pooler.supabase.com:6543/postgres"
def get_db_connection():
    try:
        return psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
    except Exception as e:
        print(f"ERRO CRÍTICO DE CONEXÃO: {e}")
        return None

class LicenseRequest(BaseModel):
    license_key: str
    machine_id: str

# --- ROTA DE VALIDAÇÃO (USADA PELO APP DESKTOP) ---
@app.post("/verify-license")
async def verify_license(data: LicenseRequest):
    conn = get_db_connection()
    if not conn:
        return {"status": "error", "message": "Falha na conexão com o banco remoto."}
    
    cur = conn.cursor()
    cur.execute("SELECT * FROM licenses WHERE key = %s", (data.license_key.upper(),))
    license = cur.fetchone()
    
    if not license:
        return {"status": "invalid", "message": "Chave não encontrada."}
    
    # Verifica se a licença está bloqueada manualmente pelo admin
    if license['status'] == 'blocked':
        return {"status": "blocked", "message": "Acesso suspenso. Entre em contato com o suporte."}
    
    # Vincula ao Hardware ID no primeiro uso
    if not license['machine_id']:
        cur.execute("UPDATE licenses SET machine_id = %s WHERE key = %s", 
                    (data.machine_id, data.license_key.upper()))
        conn.commit()
        license['machine_id'] = data.machine_id

    # Trava de segurança: impede uso em outro PC
    if license['machine_id'] != data.machine_id:
        return {"status": "blocked", "message": "Licença já vinculada a outro computador."}
    
    # Verifica expiração
    if license['expires_at'] < datetime.now().date():
        return {"status": "expired", "message": f"Assinatura vencida em {license['expires_at']}"}
    
    return {"status": "success", "message": "Ativado!", "expires_at": str(license['expires_at'])}

# --- ROTAS DO PAINEL ADMINISTRATIVO (WEB) ---

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request, search: str = ""):
    conn = get_db_connection()
    if not conn:
        return HTMLResponse("<h1>Erro de Conexão</h1><p>Verifique a URI do Supabase no código.</p>")
    
    cur = conn.cursor()
    if search:
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
    try:
        cur.execute(
            "INSERT INTO licenses (key, machine_id, client_name, document, expires_at, status) VALUES (%s, %s, %s, %s, %s, %s)",
            (key.upper(), "", client_name, document, expires_at, "active")
        )
        conn.commit()
    except Exception as e:
        print(f"Erro ao inserir: {e}")
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

@app.post("/admin/delete/{key}")
async def delete_license(key: str):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM licenses WHERE key = %s", (key,))
    conn.commit()
    return RedirectResponse(url="/admin", status_code=303)