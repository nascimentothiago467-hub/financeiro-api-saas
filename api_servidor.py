from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import sqlite3
from datetime import datetime
import secrets # Biblioteca nativa para gerar códigos aleatórios seguros

# Cria a API
app = FastAPI(title="Painel de Licenças - SaaS")

# ==========================================
# MODELOS DE DADOS (O que a API espera receber)
# ==========================================
class LicenseCheck(BaseModel):
    license_key: str
    machine_id: str

class NewLicense(BaseModel):
    client_name: str
    expires_at: str # Formato esperado: YYYY-MM-DD

# ==========================================
# BANCO DE DADOS
# ==========================================
def init_db():
    with sqlite3.connect("licencas_nuvem.sqlite3") as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS licenses (
                key TEXT PRIMARY KEY,
                machine_id TEXT,
                client_name TEXT,
                expires_at DATE,
                status TEXT
            )
        """)
        conn.execute("""
            INSERT OR IGNORE INTO licenses (key, machine_id, client_name, expires_at, status) 
            VALUES ('JUNINHO-PRO-123', '', 'Cliente VIP', '2026-12-31', 'active')
        """)

init_db()

# ==========================================
# ROTA 1: APLICATIVO CONSULTA A CHAVE (A que você já testou)
# ==========================================
@app.post("/verify-license")
def verify_license(data: LicenseCheck):
    with sqlite3.connect("licencas_nuvem.sqlite3") as conn:
        cur = conn.cursor()
        cur.execute("SELECT machine_id, expires_at, status FROM licenses WHERE key = ?", (data.license_key,))
        row = cur.fetchone()

        if not row:
            return {"status": "invalid", "message": "Chave não encontrada no sistema."}

        saved_machine_id, expires_at, status = row

        if status != "active":
            return {"status": "invalid", "message": "Licença suspensa. Contate o suporte."}

        hoje = datetime.now().strftime("%Y-%m-%d")
        if hoje > expires_at:
            return {"status": "invalid", "message": f"Sua licença expirou em {expires_at}."}

        if not saved_machine_id:
            cur.execute("UPDATE licenses SET machine_id = ? WHERE key = ?", (data.machine_id, data.license_key))
            conn.commit()
        elif saved_machine_id != data.machine_id:
            return {"status": "invalid", "message": "Esta chave já está em uso em outro computador."}

        return {"status": "active", "expires_in": expires_at}

# ==========================================
# ROTA 2: VOCÊ (ADMIN) GERA UMA NOVA CHAVE
# ==========================================
@app.post("/generate-license")
def create_license(data: NewLicense):
    # Gera uma chave alfanumérica única (Ex: APP-8F4A2B9C)
    new_key = f"APP-{secrets.token_hex(4).upper()}"
    
    with sqlite3.connect("licencas_nuvem.sqlite3") as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO licenses (key, machine_id, client_name, expires_at, status)
            VALUES (?, '', ?, ?, 'active')
        """, (new_key, data.client_name, data.expires_at))
        conn.commit()
        
    return {
        "message": "Licença criada com sucesso!",
        "key": new_key,
        "client": data.client_name,
        "expires_at": data.expires_at
    }

# PAINEL WEB VISUAL (NOVO)
# ==========================================
# Configura o FastAPI para procurar a pasta "templates"
templates = Jinja2Templates(directory="templates")

@app.get("/admin", response_class=HTMLResponse)
def admin_panel(request: Request):
    """Renderiza a página HTML com a tabela de licenças."""
    with sqlite3.connect("licencas_nuvem.sqlite3") as conn:
        cur = conn.cursor()
        # Busca todas as licenças cadastradas
        cur.execute("SELECT key, machine_id, client_name, expires_at, status FROM licenses ORDER BY expires_at DESC")
        licenses = cur.fetchall()
        
    return templates.TemplateResponse("admin.html", {"request": request, "licenses": licenses})

@app.post("/admin/generate")
def admin_generate(client_name: str = Form(...), expires_at: str = Form(...)):
    """Recebe os dados do formulário HTML e cria a chave."""
    new_key = f"APP-{secrets.token_hex(4).upper()}"
    
    with sqlite3.connect("licencas_nuvem.sqlite3") as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO licenses (key, machine_id, client_name, expires_at, status)
            VALUES (?, '', ?, ?, 'active')
        """, (new_key, client_name, expires_at))
        conn.commit()
        
    # Redireciona de volta para a tela inicial do painel após criar
    return RedirectResponse(url="/admin", status_code=303)