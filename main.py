import os
import psycopg2
import json
import google.generativeai as genai
import uuid
import logging
import re
import sys          # NUEVO: Para diagnósticos
import traceback    # NUEVO: Para ver el error real
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
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

# ==============================================================================
#  BLOQUE DE DIAGNÓSTICO CRÍTICO (AQUÍ ESTÁ EL CAMBIO  PARA ENCONTRAR EL ERROR)
# ==============================================================================
print("----------------------------------------------------------------")
print(f"📂 DIAGNÓSTICO DE ARRANQUE: Directorio actual del servidor: {os.getcwd()}")
try:
    files = os.listdir('.')
    if 'ai_manager.py' in files:
        print("✅ ARCHIVO ENCONTRADO FÍSICAMENTE: ai_manager.py está en la carpeta raíz.")
    else:
        print(f"❌ ARCHIVO FALTANTE: ai_manager.py NO aparece en la lista de archivos: {files}")
except Exception as list_err:
    print(f"⚠️ Error intentando leer el directorio: {list_err}")

# INTENTO DE IMPORTACIÓN FORZADA (SIN OCULTAR ERRORES)
try:
    from ai_manager import brain
    print("✅ ÉXITO TOTAL: ai_manager cargado, la rotación de llaves está ACTIVA.")
except Exception as e:
    brain = None
    print(f"\n🚨🚨🚨 ERROR CRÍTICO AL IMPORTAR AI_MANAGER: {e} 🚨🚨🚨")
    print("🔎 DETALLE TÉCNICO DEL ERROR (Traceback):")
    traceback.print_exc()
    print("⚠️ ADVERTENCIA: El sistema arrancará, pero SIN inteligencia rotativa (Modo Fallo).\n")
print("----------------------------------------------------------------")
# ==============================================================================

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

# Configuración Legacy para el Nutridor (se actualizará en el siguiente paso)
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

def get_current_user_email():
    # En producción esto debe venir de session['user_email'] o similar
    # Por ahora hardcodeado como en tu código original para Admin
    return 'admin@autoneura.com'

# ==========================================
# CEREBRO ARQUITECTO (ACTUALIZADO CON ROTACIÓN DE LLAVES)
# ==========================================
class CerebroArquitecto:
    def __init__(self):
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
        
        4. finance_logs (NUEVA TABLA FINANCIERA)
           - Columnas: movement_type (INGRESO/GASTO), category, amount_net, created_at.
        
        EJEMPLOS DE CONSULTAS:
        - "Campaña con más prospectos": SELECT c.campaign_name, COUNT(p.id) as total FROM campaigns c LEFT JOIN prospects p ON c.id = p.campaign_id GROUP BY c.campaign_name ORDER BY total DESC LIMIT 5;
        - "Total de ingresos": SELECT SUM(amount_net) FROM finance_logs WHERE movement_type = 'INGRESO';
        """

    def pensar(self, pregunta_usuario):
        conn = get_db_connection()
        if not conn:
            return "Error crítico: No hay conexión a la base de datos."
        
        # 1. SOLICITAR CEREBRO AL MANAGER (ROTACIÓN)
        if not brain:
            return "Error: El sistema de rotación de IA (ai_manager) no está activo. Revisa el LOG de arranque."
            
        try:
            # Pedimos un modelo 'inteligente' (Pro) o 'general' para escribir SQL bien
            # Esto buscará en Supabase qué llave tiene saldo/cupo
            model, model_id = brain.get_optimal_model(task_type="inteligencia")
            
            # PASO 1: Generar SQL
            prompt_sql = f"""
            Genera SOLO un código SQL (PostgreSQL) para responder: "{pregunta_usuario}"
            CONTEXTO: {self.schema}
            REGLAS:
            1. Devuelve SOLO el SQL puro. Sin markdown.
            2. Usa 'LEFT JOIN' para contar prospectos.
            3. Si preguntan finanzas, usa la tabla finance_logs.
            """
            
            response_sql = model.generate_content(prompt_sql)
            # REGISTRAMOS EL USO (SEMAFORO)
            brain.register_usage(model_id)
            
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

            # PASO 3: Interpretar Resultados (Reutilizamos el modelo o pedimos otro)
            prompt_final = f"""
            ACTÚA COMO ANALISTA DE NEGOCIOS.
            PREGUNTA: "{pregunta_usuario}"
            DATOS (SQL): Columnas {nombres_columnas}, Filas {resultados}
            RESPONDE: Directo, profesional, usa signo $ si es dinero.
            """
            response_final = model.generate_content(prompt_final)
            brain.register_usage(model_id) # Cobramos el segundo uso
            
            return response_final.text

        except Exception as e:
            return f"Error técnico o de IA: {str(e)}"

# Instancia global del Arquitecto
arquitecto_brain = CerebroArquitecto()


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
        client_email = get_current_user_email()
        
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
        if conn: conn.close()

# --- API: CREAR CAMPAÑA (ARREGLADA 100%) ---
@app.route('/api/crear-campana', methods=['POST'])
def crear_campana():
    conn = get_db_connection()
    if not conn: return jsonify({"success": False, "error": "No DB Connection"}), 500
    try:
        d = request.json
        cur = conn.cursor()
        client_email = get_current_user_email()
        
        # 1. Obtener o crear Cliente
        cur.execute("SELECT id FROM clients WHERE email = %s", (client_email,))
        res = cur.fetchone()
        if not res:
            cur.execute("INSERT INTO clients (email, full_name, plan_type, plan_cost) VALUES (%s, 'Admin', 'starter', 149.00) RETURNING id", (client_email,))
            cid = cur.fetchone()[0]
            conn.commit()
        else:
            cid = res[0]

        # 2. Preparar Datos (Usando los nombres correctos de columna DB)
        desc = f"{d.get('que_vende')}. {d.get('descripcion')}"
        phone = d.get('numero_whatsapp') # Ya viene con +58
        
        # 3. Insertar con NOMBRES EXACTOS DE COLUMNAS DB
        # Usamos whatsapp_number y whatsapp_contact duplicados por seguridad
        cur.execute("""
            INSERT INTO campaigns (
                client_id, campaign_name, product_description, target_audience, 
                product_type, search_languages, geo_location,
                ticket_price, competitors, cta_goal, 
                pain_points_defined, tone_voice, red_flags,
                ai_constitution, ai_blackboard, 
                whatsapp_number, whatsapp_contact, sales_link,
                status, created_at, daily_prospects_limit
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'active', NOW(), 10)
            RETURNING id
        """, (
            cid, 
            d.get('nombre'), 
            desc, 
            d.get('a_quien'), 
            d.get('tipo_producto'), 
            d.get('idiomas'), 
            d.get('ubicacion'),
            d.get('ticket_producto'), 
            d.get('competidores_principales'), 
            d.get('objetivo_cta'), 
            d.get('dolores_pain_points'), 
            d.get('tono_marca'), 
            d.get('red_flags'), 
            d.get('ai_constitution'), 
            d.get('ai_blackboard'), 
            phone, # whatsapp_number
            phone, # whatsapp_contact (duplicado para asegurar)
            d.get('enlace_venta')
        ))
        
        nid = cur.fetchone()[0]
        conn.commit()
        print(f"✅ Campaña Creada ID: {nid}")
        return jsonify({"success": True})
        
    except Exception as e:
        print(f"❌ Error creando campaña: {e}")
        if conn: conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        if conn: conn.close()

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
                                     contenido=contenido, 
                                     titulo_personalizado=f"Bienvenido {nombre_negocio}")
            return "Error al generar el nido", 404
    finally:
        conn.close()

# ==========================================================
# CHAT NIDO
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
        respuesta_ia = nutridor_brain.responder_chat_instantaneo(mensaje, token)
        return jsonify({"respuesta": respuesta_ia})
        
    return jsonify({"respuesta": "El Asistente está desconectado temporalmente."})

# --- RUTAS DEBUG ---
@app.route('/ver-pre-nido')
def debug_pre(): return render_template('persuasor.html', prospecto_id="TEST", contenido={})

@app.route('/ver-nido')
def debug_nido(): return render_template('nido_template.html', nombre_negocio="Demo", token_sesion="TEST", titulo_personalizado="Demo", contenido={})

# --- RUTA CHAT ARQUITECTO (USANDO EL CEREBRO ROTATIVO) ---
@app.route('/api/chat-arquitecto', methods=['POST'])
def chat_arquitecto_api():
    mensaje = request.json.get('message')
    if not mensaje: return jsonify({"response": "Por favor escribe una pregunta."})
    
    if arquitecto_brain:
        return jsonify({"response": arquitecto_brain.pensar(mensaje)})
    else:
        return jsonify({"response": "Cerebro inactivo."})

# --- RUTA CHAT ADMIN (CORREGIDA PARA NO MOSTRAR JSON) ---
@app.route('/chat', methods=['POST'])
def chat_admin():
    # Intenta usar el nuevo sistema (Manager) si el viejo no existe
    mensaje = request.json.get('message')
    
    # INTENTO 1: Usar ai_manager (Cerebro Nuevo con rotación)
    if brain:
        if hasattr(brain, 'generar_respuesta_demo'):
            return jsonify({"response": brain.generar_respuesta_demo(mensaje)})
            
    # INTENTO 2: Usar sistema viejo (Fallback)
    global dashboard_brain
    if not dashboard_brain and create_chatbot: 
        dashboard_brain = create_chatbot()
        
    if dashboard_brain: 
        return jsonify({"response": dashboard_brain.invoke({"question": mensaje})})
        
    return jsonify({"response": "Sistema de Chat en mantenimiento (Cerebros desconectados)."})

# --- API: DETALLES CAMPAÑA ---
@app.route('/api/campana/<string:id>', methods=['GET'])
def obtener_detalle_campana(id):
    conn = get_db_connection()
    if not conn: return jsonify({"error": "No DB"}), 500
    try:
        cur = conn.cursor()
        # Seleccionamos nombres correctos de columna
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
        row = cur.fetchone()
        mrr = row[0] if row and row[0] else 0
        
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
    ia_status = "🟢 Rotación Activa" if brain else "🔴 Error Manager"
    
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
