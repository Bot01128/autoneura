import os
import psycopg2
import json
import google.generativeai as genai
import uuid
import logging
import re
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_babel import Babel, gettext
from psycopg2.extras import Json
from werkzeug.routing import BaseConverter
from dotenv import load_dotenv

# --- IMPORTACIÓN DE MÓDULOS PROPIOS ---
try:
    from cerebro_dashboard import create_chatbot
except ImportError:
    create_chatbot = None

try:
    from trabajador_nutridor import TrabajadorNutridor
except ImportError:
    TrabajadorNutridor = None

# --- CONFIGURACIÓN INICIAL ---
load_dotenv()

# Configuración básica de logs
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "autoneura-super-secret-key-2025")

class UUIDConverter(BaseConverter):
    def to_python(self, value): return uuid.UUID(value)
    def to_url(self, value): return str(value)

app.url_map.converters['uuid'] = UUIDConverter

# --- IDIOMAS ---
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['BABEL_TRANSLATION_DIRECTORIES'] = os.path.join(basedir, 'translations')

def get_locale():
    return request.accept_languages.best_match(['en', 'es']) or 'es'

babel = Babel(app, locale_selector=get_locale)

@app.context_processor
def inject_get_locale():
    return dict(get_locale=get_locale, _=gettext)

# --- CONEXIÓN DB Y API ---
DATABASE_URL = os.environ.get("DATABASE_URL")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

dashboard_brain = None
nutridor_brain = None

if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    if TrabajadorNutridor:
        nutridor_brain = TrabajadorNutridor()

def get_db_connection():
    try:
        return psycopg2.connect(DATABASE_URL)
    except Exception as e:
        print(f"Error DB: {e}")
        return None

# ==========================================
# CEREBRO ARQUITECTO (ADMIN & CLIENTE) - VERSIÓN GEMINI 2.5 FLASH
# ==========================================
class CerebroArquitecto:
    def __init__(self, api_key):
        # USAMOS LA VERSIÓN ESTABLE Y RÁPIDA
        self.model = genai.GenerativeModel('models/gemini-2.5-flash')
        
        # ESQUEMA PARA SQL
        self.schema = """
        ERES UN EXPERTO EN SQL POSTGRESQL. TU TRABAJO ES CONSULTAR ESTAS TABLAS:
        
        1. clients 
           - Columnas: id, full_name, email, plan_cost (dinero), created_at.
        
        2. campaigns 
           - Columnas: id, client_id, campaign_name, status, created_at.
           - Relación: campaigns.client_id = clients.id
        
        3. prospects 
           - Columnas: id, campaign_id, interactions_count, created_at.
           - Relación: prospects.campaign_id = campaigns.id
        
        EJEMPLOS DE CONSULTAS:
        - "Campaña con más prospectos": SELECT c.campaign_name, COUNT(p.id) as total FROM campaigns c LEFT JOIN prospects p ON c.id = p.campaign_id GROUP BY c.campaign_name ORDER BY total DESC LIMIT 5;
        - "Total de ingresos": SELECT SUM(plan_cost) FROM clients;
        """

    def pensar(self, pregunta_usuario):
        conn = get_db_connection()
        if not conn:
            return "Error crítico: No hay conexión a la base de datos."
        
        try:
            # PASO 1: Generar SQL
            prompt_sql = f"""
            Genera SOLO un código SQL (PostgreSQL) para responder: "{pregunta_usuario}"
            CONTEXTO: {self.schema}
            REGLAS:
            1. Devuelve SOLO el SQL puro. Sin markdown.
            2. Usa 'LEFT JOIN' para contar prospectos.
            3. 'Ingresos' = SUM(plan_cost) de tabla clients.
            """
            
            response_sql = self.model.generate_content(prompt_sql)
            sql_query = response_sql.text.strip().replace('```sql', '').replace('```', '').replace('\n', ' ')
            
            # Seguridad
            if any(x in sql_query.lower() for x in ["delete", "update", "drop", "insert", "alter"]):
                return "Lo siento, solo tengo permisos de LECTURA."

            # PASO 2: Ejecutar SQL
            cursor = conn.cursor()
            cursor.execute(sql_query)
            resultados = cursor.fetchall()
            nombres_columnas = [desc[0] for desc in cursor.description] if cursor.description else []
            cursor.close()
            conn.close()
            
            if not resultados:
                return f"Consulté la base de datos y no encontré datos para esa pregunta."

            # PASO 3: Interpretar Resultados
            prompt_final = f"""
            ACTÚA COMO ANALISTA DE NEGOCIOS.
            PREGUNTA: "{pregunta_usuario}"
            DATOS (SQL): Columnas {nombres_columnas}, Filas {resultados}
            RESPONDE: Directo, profesional, usa signo $ si es dinero.
            """
            response_final = self.model.generate_content(prompt_final)
            return response_final.text

        except Exception as e:
            return f"Error técnico: {str(e)}"

# Instancia global del Arquitecto
arquitecto_brain = CerebroArquitecto(GOOGLE_API_KEY) if GOOGLE_API_KEY else None


# --- RUTAS PRINCIPALES ---
@app.route('/')
def home(): return render_template('client_dashboard.html')

@app.route('/cliente')
def client_dashboard(): return render_template('client_dashboard.html')

@app.route('/mis-clientes')
def mis_clientes(): return render_template('mis_clientes.html')

@app.route('/admin')
def admin_dashboard(): return render_template('admin_dashboard.html')

@app.route('/admin/taller')
def admin_taller(): return render_template('admin_taller.html')

# --- API: DATOS DEL DASHBOARD ---
@app.route('/api/dashboard-data', methods=['GET'])
def obtener_datos_dashboard():
    conn = get_db_connection()
    if not conn: return jsonify({"error": "No DB"}), 500
    try:
        cur = conn.cursor()
        client_email = 'admin@autoneura.com' 
        
        cur.execute("""
            SELECT 
                COUNT(p.id) as total,
                COUNT(p.id) FILTER (WHERE p.interactions_count >= 3) as calificados
            FROM prospects p
            JOIN campaigns c ON p.campaign_id = c.id
            JOIN clients cl ON c.client_id = cl.id
            WHERE cl.email = %s
        """, (client_email,))
        kpis = cur.fetchone()
        total_prospectos = kpis[0] or 0
        total_calificados = kpis[1] or 0
        tasa_conversion = round((total_calificados / total_prospectos * 100), 1) if total_prospectos > 0 else 0

        cur.execute("""
            SELECT 
                c.campaign_name, c.created_at, c.status,
                COUNT(p.id) as encontrados,
                COUNT(p.id) FILTER (WHERE p.interactions_count >= 3) as leads,
                c.id
            FROM campaigns c
            JOIN clients cl ON c.client_id = cl.id
            LEFT JOIN prospects p ON c.id = p.campaign_id
            WHERE cl.email = %s
            GROUP BY c.id
            ORDER BY c.created_at DESC
        """, (client_email,))
        
        campanas = []
        for row in cur.fetchall():
            campanas.append({
                "nombre": row[0], "fecha": row[1].strftime('%Y-%m-%d') if row[1] else "-",
                "estado": row[2], "encontrados": row[3], "calificados": row[4], "id": row[5]
            })

        return jsonify({
            "kpis": {"total": total_prospectos, "calificados": total_calificados, "tasa": f"{tasa_conversion}%"},
            "campanas": campanas
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

# --- API: CREAR CAMPAÑA ---
@app.route('/api/crear-campana', methods=['POST'])
def crear_campana():
    conn = get_db_connection()
    if not conn: return jsonify({"success": False}), 500
    try:
        d = request.json
        cur = conn.cursor()
        
        cur.execute("SELECT id FROM clients WHERE email = 'admin@autoneura.com'")
        res = cur.fetchone()
        if not res:
            cur.execute("INSERT INTO clients (email, full_name, plan_type, plan_cost) VALUES ('admin@autoneura.com', 'Admin', 'starter', 149.00) RETURNING id")
            cid = cur.fetchone()[0]
            conn.commit()
        else:
            cid = res[0]

        desc = f"{d.get('que_vende')}. {d.get('descripcion')}"
        cur.execute("""
            INSERT INTO campaigns (
                client_id, campaign_name, product_description, target_audience, 
                product_type, search_languages, geo_location,
                ticket_price, competitors, cta_goal, pain_points_defined, tone_voice, red_flags,
                ai_constitution, ai_blackboard, whatsapp_number, sales_link,
                status, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'active', NOW())
            RETURNING id
        """, (
            cid, d.get('nombre'), desc, d.get('a_quien'), d.get('tipo_producto'), d.get('idiomas'), d.get('ubicacion'),
            d.get('ticket_producto'), d.get('competidores_principales'), d.get('objetivo_cta'), d.get('dolores_pain_points'), 
            d.get('tono_marca'), d.get('red_flags'), d.get('ai_constitution'), d.get('ai_blackboard'), 
            d.get('numero_whatsapp'), d.get('enlace_venta')
        ))
        
        nid = cur.fetchone()[0]
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        if conn: conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        conn.close()

# --- API: MIS CAMPAÑAS ---
@app.route('/api/mis-campanas', methods=['GET'])
def api_mis_campanas():
    conn = get_db_connection()
    if not conn: return jsonify([]), 500
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, campaign_name, status, created_at, 
            (SELECT COUNT(*) FROM prospects WHERE campaign_id = campaigns.id) as count
            FROM campaigns ORDER BY created_at DESC
        """)
        rows = cur.fetchall()
        data = []
        for r in rows:
            data.append({
                "id": r[0], "name": r[1], "status": r[2], 
                "created_at": r[3].strftime('%Y-%m-%d') if r[3] else '', 
                "prospects_count": r[4]
            })
        return jsonify(data)
    except Exception as e:
        return jsonify([]), 500
    finally:
        conn.close()

# --- RUTAS DE NIDO (CORREGIDAS PARA JSON DINÁMICO) ---
@app.route('/ver-pre-nido/<string:token>')
def mostrar_pre_nido(token):
    conn = get_db_connection()
    if not conn: return "Error DB", 500
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, business_name, generated_copy FROM prospects WHERE access_token = %s", (token,))
            res = cur.fetchone()
            if res:
                prospect_id = res[0]
                # Lógica mejorada para extraer el JSON
                raw_copy = res[2]
                contenido = {}
                if raw_copy:
                    if isinstance(raw_copy, str):
                        try: contenido = json.loads(raw_copy)
                        except: contenido = {}
                    else: contenido = raw_copy
                
                # ENVIAMOS EL OBJETO COMPLETO 'CONTENIDO'
                return render_template('persuasor.html', 
                                     prospecto_id=prospect_id, 
                                     contenido=contenido)
            return "Enlace no válido", 404
    finally:
        conn.close()

# === FUNCIÓN CORREGIDA VITAL PARA EL NIDO ===
@app.route('/generar-nido', methods=['POST'])
def generar_nido_y_entrar():
    email = request.form.get('email')
    pid = request.form.get('prospecto_id')
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 1. Actualizamos el email y el estado
            cur.execute("""
                UPDATE prospects SET captured_email = %s, status = 'nutriendo', last_interaction_at = NOW()
                WHERE id = %s RETURNING business_name, access_token, generated_copy
            """, (email, pid))
            res = cur.fetchone()
            conn.commit()
            
            if res:
                nombre_negocio = res[0]
                token_sesion = res[1]
                raw_copy = res[2]
                
                # 2. Extraemos el JSON (Copia Inteligente)
                contenido = {}
                if raw_copy:
                    if isinstance(raw_copy, str):
                        try: contenido = json.loads(raw_copy)
                        except: contenido = {}
                    else: contenido = raw_copy
                
                # 3. Renderizamos el Nido pasando el 'contenido' real
                return render_template('nido_template.html', 
                                     nombre_negocio=nombre_negocio, 
                                     token_sesion=token_sesion,
                                     contenido=contenido, # ¡ESTO ES LO IMPORTANTE!
                                     titulo_personalizado=f"Bienvenido {nombre_negocio}")
            return "Error al generar el nido", 404
    finally:
        conn.close()

# ==========================================================
# CORRECCIÓN VITAL: AQUÍ ESTÁ EL CAMBIO PARA QUE LA IA PIENSE
# ==========================================================
@app.route('/api/chat-nido', methods=['POST'])
def chat_nido_api():
    d = request.json
    mensaje = d.get('message')
    token = d.get('token')
    
    # 1. Validación de seguridad
    if not mensaje or not token:
        return jsonify({"respuesta": "Error: Datos incompletos."})
        
    # 2. CONEXIÓN REAL CON EL CEREBRO
    if nutridor_brain:
        # Llamamos a la función que creamos en trabajador_nutridor.py
        respuesta_ia = nutridor_brain.responder_chat_instantaneo(mensaje, token)
        return jsonify({"respuesta": respuesta_ia})
        
    return jsonify({"respuesta": "El Asistente está desconectado (Falta API Key)."})
# ==========================================================

# --- RUTAS DEBUG ---
@app.route('/ver-pre-nido')
def debug_pre(): return render_template('persuasor.html', prospecto_id="TEST", contenido={})

@app.route('/ver-nido')
def debug_nido(): return render_template('nido_template.html', nombre_negocio="Demo", token_sesion="TEST", titulo_personalizado="Demo", contenido={})

# --- RUTA CHAT ARQUITECTO (INTELIGENTE) ---
@app.route('/api/chat-arquitecto', methods=['POST'])
def chat_arquitecto_api():
    mensaje = request.json.get('message')
    if not mensaje: return jsonify({"response": "Por favor escribe una pregunta."})
    if arquitecto_brain:
        return jsonify({"response": arquitecto_brain.pensar(mensaje)})
    else:
        return jsonify({"response": "Cerebro inactivo (Falta API Key)."})

# --- RUTA ANTIGUA CHAT ---
@app.route('/chat', methods=['POST'])
def chat_admin():
    global dashboard_brain
    if not dashboard_brain and create_chatbot: dashboard_brain = create_chatbot()
    if dashboard_brain: return jsonify({"response": dashboard_brain.invoke({"question": request.json.get('message')})})
    return jsonify({"response": "Mantenimiento"})

# --- API: DETALLES CAMPAÑA ---
@app.route('/api/campana/<string:id>', methods=['GET'])
def obtener_detalle_campana(id):
    conn = get_db_connection()
    if not conn: return jsonify({"error": "No DB"}), 500
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, campaign_name, product_description, target_audience, product_type, search_languages, geo_location,
            ticket_price, competitors, cta_goal, pain_points_defined, tone_voice, red_flags, ai_constitution, ai_blackboard,
            daily_prospects_limit, whatsapp_number, sales_link FROM campaigns WHERE id = %s
        """, (id,))
        row = cur.fetchone()
        if row:
            campana = {
                "id": row[0], "campaign_name": row[1], "product_description": row[2], "target_audience": row[3],
                "product_type": row[4], "languages": row[5], "geo_location": row[6], "ticket_price": row[7],
                "competitors": row[8], "cta_goal": row[9], "pain_points_defined": row[10], "tone_voice": row[11],
                "red_flags": row[12], "adn_corporativo": row[13], "pizarron_contexto": row[14],
                "daily_prospects_limit": row[15], "whatsapp_number": row[16], "sales_link": row[17]
            }
            return jsonify(campana)
        return jsonify({"error": "No encontrada"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# --- API: ACTUALIZAR CAMPAÑA ---
@app.route('/api/actualizar-campana', methods=['POST'])
def actualizar_campana():
    conn = get_db_connection()
    try:
        d = request.json
        cur = conn.cursor()
        cur.execute("""
            UPDATE campaigns SET campaign_name=%s, product_description=%s, target_audience=%s, search_languages=%s, 
            ticket_price=%s, competitors=%s, cta_goal=%s, pain_points_defined=%s, red_flags=%s, tone_voice=%s, 
            ai_constitution=%s, ai_blackboard=%s, whatsapp_number=%s, sales_link=%s WHERE id=%s
        """, (
            d.get('campaign_name'), d.get('product_description'), d.get('target_audience'), d.get('languages'),
            d.get('ticket_price'), d.get('competidores'), d.get('cta_goal'), d.get('pain_points_defined'),
            d.get('red_flags'), d.get('tone_voice'), d.get('adn_corporativo'), d.get('pizarron_contexto'),
            d.get('whatsapp_number'), d.get('sales_link'), d.get('id')
        ))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()
# --- API ADMIN: DATOS GLOBALES ---
@app.route('/api/admin/metricas-globales', methods=['GET'])
def admin_metricas():
    # AQUÍ DEBERÍAS PONER SEGURIDAD (verificar sesión de admin)
    conn = get_db_connection()
    if not conn: return jsonify({"error": "No DB"}), 500
    try:
        cur = conn.cursor()
        
        # 1. MRR (Suma de planes activos)
        cur.execute("SELECT SUM(plan_cost) FROM clients WHERE is_active = TRUE")
        mrr = cur.fetchone()[0] or 0
        
        # 2. Total Clientes
        cur.execute("SELECT COUNT(*) FROM clients")
        total_clientes = cur.fetchone()[0]
        
        # 3. Big Data (Prospectos Totales)
        cur.execute("SELECT COUNT(*) FROM prospects")
        total_prospectos = cur.fetchone()[0]
        
        # 4. Carga Sistema (Campañas Activas)
        cur.execute("SELECT COUNT(*) FROM campaigns WHERE status = 'active'")
        campanas_activas = cur.fetchone()[0]
        
        return jsonify({
            "mrr": mrr,
            "total_clientes": total_clientes,
            "total_prospectos": total_prospectos,
            "campanas_activas": campanas_activas
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# --- API ADMIN: LISTA DE CLIENTES ---
@app.route('/api/admin/lista-clientes', methods=['GET'])
def admin_lista_clientes():
    conn = get_db_connection()
    if not conn: return jsonify([]), 500
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, full_name, email, plan_type, is_active, 
            (SELECT COUNT(*) FROM campaigns WHERE client_id = clients.id) as num_campanas
            FROM clients
            ORDER BY created_at DESC
        """)
        rows = cur.fetchall()
        clientes = []
        for r in rows:
            clientes.append({
                "id": r[0],
                "nombre": r[1] or "Sin Nombre",
                "email": r[2],
                "plan": r[3],
                "activo": r[4],
                "campanas": r[5]
            })
        return jsonify(clientes)
    except Exception as e:
        return jsonify([]), 500
    finally:
        conn.close()
        # ==========================================
# NUEVAS RUTAS: FINANZAS Y MONITOR (ADMIN)
# ==========================================

# 1. OBTENER HISTORIAL FINANCIERO
@app.route('/api/admin/finanzas', methods=['GET'])
def admin_get_finanzas():
    conn = get_db_connection()
    if not conn: return jsonify([]), 500
    try:
        cur = conn.cursor()
        # Traemos los últimos 5>
                <button class="tab-button" data-tab="campanas">📢 Campañas</button>
                <button class="tab-button" data-tab="finanzas">💰 Finanzas</button>
                <button class="tab-button" data-tab="monitor">⚙️ Monitor</button>
            </div>

            <!-- 1. DASHBOARD GLOBAL -->
            <div class="tab-content" id="dashboard" style="display: block;">
                <h2>Signos Vitales</h2>
                <div class="kpi-container">
                    <div class="kpi-card"><span class="kpi-title">Ingresos Mensuales</span><span class="kpi-value" id="kpi-mrr">$0.00</span></div>
                    <div class="kpi-card"><span class="kpi-title">Clientes Totales</span><span class="kpi-value" id="kpi-clientes">0</span></div>
                    <div class="kpi-card"><span class="kpi-title">Prospectos Totales</span><span class="kpi-value" id="kpi-data">0</span></div>
                    <div class="kpi-card"><span class="kpi-title">Campañas Activas</span><span class="kpi-value" id="kpi-activas">0</span></div>
                </div>
            </div>

            <!-- 2. CLIENTES -->
            <div class="tab-content" id="clientes" style="display: none;">
                <h2>Base de Datos de Clientes</h2>
                <table class="campaign-table">
                    <thead><tr><th>Nombre</th><th>Email</th><th>Plan</th><th>Estado</th><th>Campañas</th></tr></thead>
                    <tbody id="lista-clientes"></tbody>
                </table>
            </div>

            <!-- 3. TODAS LAS CAMPAÑAS -->
            <div class="tab-content" id="campanas" style="display: none;">
                <h2>Visión de Rayos X</h2>
                <p>Lista maestra de todas las campañas del sistema.</p>
                <table class="campaign-table">
                    <thead><tr><th>Campaña</th><th>Cliente</th><th>Estado</th><th>Prospectos</th></tr></thead>
                    <tbody id="lista-campanas">
                        <!-- Se llenará luego con JS -->
                        <tr><td colspan="4">Cargando datos...</td></tr>
                    </tbody>
                </table>
            </div>

            <!-- 4. FINANZAS (NUEVO) -->
            <div class="tab-content" id="finanzas" style="display: none;">
                <h2>Tesorería y Ganancias</h2>
                
                <!-- KPI DE GANANCIA NETA -->
                <div style="background: #1e1e1e; padding: 20px; border-radius: 8px; border: 1px solid #4caf50; margin-bottom: 20px; text-align: center;">
                    <h3 style="color: #4caf50; margin:0;">GANANCIA NETA REAL (Caja)</h3>
                    <h1 style="font-size: 3em; margin: 10px 0; color: white;" id="total-neto">$0.00</h1>
                </div>

                <!-- FORMULARIO DE GASTOS -->
                <div class="gasto-form">
                    <h4 style="margin-top:0;">🔴 Registrar Gasto Operativo</h4>
                    <div style="display: flex; gap: 10px;">
                        <input type="text" id="gasto-concepto" placeholder="Ej: Recarga Apify" style="flex: 2;">
                        <input type="number" id="gasto-monto" placeholder="Monto ($)" style="flex: 1;">
                        <button class="recharge-btn" style="background-0 movimientos
        cur.execute("""
            SELECT created_at, movement_type, category, description, amount_gross, amount_net 
            FROM finance_logs 
            ORDER BY created_at DESC LIMIT 50
        """)
        rows = cur.fetchall()
        
        # Calculamos el Balance Total (Ganancia Neta)
        cur.execute("SELECT SUM(amount_net) FROM finance_logs")
        balance = cur.fetchone()[0] or 0.00
        
        historial = []
        for r in rows:
            historial.append({
                "fecha": r[0].strftime('%Y-%m-%d %H:%M'),
                "tipo": r[1],
                "categoria": r[2],
                "desc": r[3] or "-",
                "bruto": float(r[4]),
                "neto": float(r[5])
            })
            
        return jsonify({"balance": float(balance), "historial": historial})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# 2. REGISTRAR GASTO MANUAL (Tú registras lo que pagas)
@app.route('/api/color: #f44336;" onclick="registrarGasto()">Registrar Salida</button>
                    </div>
                </div>

                <!-- TABLA HISTORIAL -->
                <h3>Libro Contable (Últimos 50 movimientos)</h3>
                <table class="campaign-table">
                    <thead><tr><th>Fecha</th><th>Tipo</th><th>Concepto</th><th>Monto Bruto</th><th>Neto</th></tr></thead>
                    <tbody id="tabla-finanzas"></tbody>
                </table>
            </div>

            <!-- 5. MONITOR DEL SISTEMA (NUEVO) -->
            <div class="tab-content" idadmin/registrar-gasto', methods=['POST'])
def admin_registrar_gasto():
    d = request.json
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        # Un gasto es negativo para el neto. 
        # Ejemplo: Bruto 10, Neto -10 (porque salió de tu bolsillo)
        monto = float(d.get('monto'))
        monto_neto = monto * -1  
        
        cur.execute("""
            INSERT INTO finance_logs (movement_type, category, description, amount_gross, amount_net)
            VALUES ('GASTO', %s, %s, %s, %s)
        """, (d.get('categoria'), d.get('descripcion'), monto, monto_neto))
        
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return="monitor" style="display: none;">
                <h2>Cuarto de Máquinas</h2>
                <div class="kpi-container">
                    <div class="kpi-card"><span class="kpi-title">Base de Datos</span><span class="kpi-value" id="status-db">...</span></div>
                    <div class="kpi-card"><span class="kpi-title">Google AI</span><span class="kpi-value" id="status-ai">...</span></div>
                    <div class="kpi-card"><span class="kpi-title">Apify Scraper</span><span class="kpi-value" id="status-apify">...</span></div>
                </div>
            </div>
        </div>
    </div>

    <!-- JAVASCRIPT DEL ADMIN -->
    <script>
        document.addEventListener('DOMContentLoaded', async () => {
            
            // --- 1. CARGA INICIAL DE DATOS ---
            cargarKPIsGlobales();
            cargarClientes();
            cargarFinanzas();
            cargarMonitor();

            // --- 2. LÓGICA DE PESTAÑAS ---
            const tabs = document.querySelectorAll('.tab-button');
            const contents = document.querySelectorAll('.tab-content');
            tabs.forEach(btn => {
                btn jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# 3. MONITOR DE SISTEMA (Estado de las APIs)
@app.route('/api/admin/monitor', methods=['GET'])
def admin_monitor():
    # Verificamos DB
    db_status = "OK" if get_db_connection() else "ERROR"
    
    # Verificamos Google IA (Simulada para no gastar saldo, o real si quieres)
    ia_status = "OK" if GOOGLE_API_KEY else "FALTA KEY"
    
    return jsonify({
        "database": db_status,
        ".addEventListener('click', () => {
                    contents.forEach(c => c.style.display = 'none');
                    tabs.forEach(t => t.classList.remove('active'));
                    document.getElementById(btn.dataset.tab).style.display = 'block';
                    btn.classList.add('active');
                });
            });

            // --- 3. FUNCIONES DE CARGA ---
            async function cargarKPIsGlobales() {
                try {
                    const res = await fetch('/api/admin/metricas-globales');
                    const data = await res.json();
                    document.getElementById('kpi-mrr').innerText = `$${data.mrr}`;
                    document.getElementById('kpi-clientes').innerText = data.total_clientes;
                    document.getElementById('kpi-data').innerText = data.total_prospectos;
                    document.getElementById('kpi-activas').innerText = data.campanas_activas;
                } catch(e) { console.error(e); }
            }

            async function cargarClientes() {
                try {
                    const res = await fetch('/api/admin/lista-clientes');
                    const clientes = await res.json();
                    const tbody = document.getElementById('lista-clientes');
                    tbody.innerHTML = '';
                    clientes.forEach(google_ai": ia_status,
        "apify": "OK" # Asumimos OK si hay token, luego podemos refinar
    })
    # ==========================================
# RUTAS NUEVAS PARA EL PANEL ADMIN (FINANZAS Y MONITOR)
# ==========================================

# 1. OBTENER HISTORIAL FINANCIERO
@app.route('/api/admin/finanzas', methods=['GET'])
def admin_get_finanzas():
    conn = get_db_connection()
    if not conn: return jsonify([]), 500
    try:
        cur = conn.cursor()
        # Traemos los últimos 50 movimientos
        cur.execute("""
            SELECT created_at, movement_type, category, description, amount_gross, amount_net 
            FROM finance_logs 
            ORDER BY created_at DESC LIMIT 50
        """)
        rows = cur.fetchall()
        
        # Calculamos el Balance Total (Ganancia Neta)
        cur.execute("SELECT SUM(amount_net) FROM finance_logs")
        res_total = cur.fetchone()
        balance = res_total[0] if res_total and res_total[0] else 0.00
        
        historial = []
        for r in rows:
            historial.append({
                "fecha": r[0].strftime('%Y-%m-%d %H:%M') if r[0] else "-",
                "tipo": r[1],
                "categoria": r[2],
                "desc": r[3] or "-",
                "bruto": float(r[4]),
                "neto": float(r[5])
            })
            
        return jsonify({"balance": float(balance), "historial": historial})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# 2. REGISTRAR GASTO MANUAL (Tú registras lo que pagas)
@app.route('/api/admin/registrar-gasto', methods=['POST'])
def admin_registrar_gasto():
    d = request.json
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        # Un gasto es negativo para el neto. 
        monto = float(d.get('monto'))
        monto_neto = monto * -1  
        
        cur.execute("""
            INSERT INTO finance_logs (movement_type, category, description, amount_gross, amount_net)
            VALUES ('GASTO', %s, %s, %s, %s)
        """, ('Operativo', d.get('concepto'), d.get('monto'), monto_neto))
        
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

# 3. MONITOR DE SISTEMA (Estado de las APIs)
@app.route('/api/admin/monitor', methods=['GET'])
def admin_monitor():
    # Verificamos DB
    db_status = "🟢 Online" if get_db_connection() else "🔴 Error Conexión"
    
    # Verificamos Google IA
    ia_status = "🟢 Activo" if GOOGLE_API_KEY else "🔴 Falta Key"
    
    # Verificamos Apify
    apify_status = "🟢 Activo" if os.environ.get('APIFY_TOKEN') else "🔴 Falta Token"
    
    return jsonify({
        "database": db_status,
        "google_ai": ia_status,
        "apify": apify_status
    })
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
