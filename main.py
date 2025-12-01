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
# NUEVO: LÓGICA DEL CEREBRO ARQUITECTO (ADMIN)
# ==========================================
class CerebroArquitecto:
    def __init__(self, api_key):
        self.model = genai.GenerativeModel('gemini-2.0-flash-lite-preview-02-05')
        # Esquema simplificado para que la IA entienda la DB
        self.schema = """
        TABLAS DISPONIBLES EN SUPABASE:
        1. clients (id, full_name, email, plan_type, plan_cost, created_at)
        2. campaigns (id, client_id, campaign_name, status, created_at)
        3. prospects (id, campaign_id, status, interactions_count, created_at)
        
        RELACIONES:
        - campaigns.client_id -> clients.id
        - prospects.campaign_id -> campaigns.id
        """

    def pensar(self, pregunta_usuario):
        conn = get_db_connection()
        if not conn:
            return "Error crítico: No hay conexión a la base de datos."
        
        try:
            # PASO 1: Generar SQL
            prompt_sql = f"""
            Eres el Arquitecto de Datos de un sistema SaaS.
            Tu misión: Convertir la pregunta del usuario en una consulta SQL POSTGRESQL válida.
            
            ESQUEMA:
            {self.schema}
            
            PREGUNTA: "{pregunta_usuario}"
            
            REGLAS:
            1. Solo responde con el código SQL. Sin markdown, sin explicaciones.
            2. Solo usa sentencias SELECT (Lectura). Nada de DELETE o UPDATE.
            3. Si preguntan por 'Leads', son prospectos con interactions_count >= 3.
            4. Si preguntan por 'Ganancias' o 'Ingresos', suma el plan_cost de la tabla clients.
            5. LIMITA los resultados a 10 filas si no especifican cantidad.
            """
            
            response_sql = self.model.generate_content(prompt_sql)
            sql_query = response_sql.text.strip().replace('```sql', '').replace('```', '')
            
            # Limpieza de seguridad básica
            if "delete" in sql_query.lower() or "update" in sql_query.lower() or "drop" in sql_query.lower():
                return "Lo siento, como medida de seguridad no puedo modificar datos, solo consultarlos."

            # PASO 2: Ejecutar SQL
            cursor = conn.cursor()
            cursor.execute(sql_query)
            resultados = cursor.fetchall()
            columnas = [desc[0] for desc in cursor.description]
            conn.close()
            
            datos_str = str(resultados)
            if not resultados:
                datos_str = "La consulta no arrojó resultados."

            # PASO 3: Interpretar Resultados
            prompt_final = f"""
            Actúa como el Director de Operaciones (COO) de AutoNeura.
            
            PREGUNTA ORIGINAL: "{pregunta_usuario}"
            DATOS OBTENIDOS DE LA DB: {datos_str}
            COLUMNAS: {columnas}
            
            Instrucción: Responde al usuario de forma ejecutiva, profesional y basada en los datos. 
            Si es dinero, usa formato moneda. Sé breve y directo.
            """
            response_final = self.model.generate_content(prompt_final)
            return response_final.text

        except Exception as e:
            return f"Error procesando la consulta: {str(e)}"

# Instancia global del Arquitecto
arquitecto_brain = CerebroArquitecto(GOOGLE_API_KEY) if GOOGLE_API_KEY else None

# ==========================================
# FIN LÓGICA ARQUITECTO
# ==========================================

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
                c.campaign_name, 
                c.created_at, 
                c.status,
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
                "nombre": row[0],
                "fecha": row[1].strftime('%Y-%m-%d') if row[1] else "-",
                "estado": row[2],
                "encontrados": row[3],
                "calificados": row[4],
                "id": row[5]
            })

        return jsonify({
            "kpis": {
                "total": total_prospectos,
                "calificados": total_calificados,
                "tasa": f"{tasa_conversion}%"
            },
            "campanas": campanas
        })

    except Exception as e:
        print(f"Error API Dashboard: {e}")
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
        
        # 1. Obtener o Crear Cliente Admin
        cur.execute("SELECT id FROM clients WHERE email = 'admin@autoneura.com'")
        res = cur.fetchone()
        if not res:
            cur.execute("INSERT INTO clients (email, full_name, plan_type, plan_cost) VALUES ('admin@autoneura.com', 'Admin', 'starter', 149.00) RETURNING id")
            cid = cur.fetchone()[0]
            conn.commit()
        else:
            cid = res[0]

        # 2. Preparar Datos
        desc = f"{d.get('que_vende')}. {d.get('descripcion')}"
        ticket = d.get('ticket_producto')
        competidores = d.get('competidores_principales')
        cta = d.get('objetivo_cta')
        dolores = d.get('dolores_pain_points')
        tono = d.get('tono_marca')
        red_flags = d.get('red_flags')
        adn = d.get('ai_constitution')
        pizarron = d.get('ai_blackboard')
        whatsapp = d.get('numero_whatsapp')
        link = d.get('enlace_venta')
        
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
            cid, d.get('nombre'), desc, d.get('a_quien'), 
            d.get('tipo_producto'), d.get('idiomas'), d.get('ubicacion'),
            ticket, competidores, cta, dolores, tono, red_flags,
            adn, pizarron, whatsapp, link
        ))
        
        nid = cur.fetchone()[0]
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        if conn: conn.rollback()
        print(f"ERROR CREANDO CAMPAÑA: {e}")
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
            FROM campaigns 
            ORDER BY created_at DESC
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

# --- RUTAS DE NIDO ---
@app.route('/ver-pre-nido/<string:token>')
def mostrar_pre_nido(token):
    conn = get_db_connection()
    if not conn: return "Error DB", 500
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, business_name, generated_copy FROM prospects WHERE access_token = %s", (token,))
            res = cur.fetchone()
            if res:
                content = res[2] if res[2] else {}
                if isinstance(content, str): content = json.loads(content)
                titulo = content.get('caja_1_titulo', 'Hola')
                mensaje = content.get('caja_1_contenido', 'Bienvenido')
                return render_template('persuasor.html', prospecto_id=res[0], nombre_negocio=res[1], 
                                     titulo_personalizado=titulo,
                                     mensaje_personalizado=mensaje)
            return "Enlace no válido", 404
    finally:
        conn.close()

@app.route('/generar-nido', methods=['POST'])
def generar_nido_y_entrar():
    email = request.form.get('email')
    pid = request.form.get('prospecto_id')
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE prospects SET captured_email = %s, status = 'nutriendo', last_interaction_at = NOW()
                WHERE id = %s RETURNING business_name, access_token
            """, (email, pid))
            res = cur.fetchone()
            conn.commit()
            if res:
                return render_template('nido_template.html', nombre_negocio=res[0], token_sesion=res[1], 
                                     titulo_personalizado=f"Bienvenido {res[0]}", texto_contenido_de_valor="Demo")
            return "Error", 404
    finally:
        conn.close()

@app.route('/api/chat-nido', methods=['POST'])
def chat_nido_api():
    d = request.json
    if nutridor_brain:
        return jsonify({"respuesta": "El Asistente está procesando tu solicitud..."}) 
    return jsonify({"respuesta": "Conectando..."})

# --- RUTAS DEBUG ---
@app.route('/ver-pre-nido')
def debug_pre(): return render_template('persuasor.html', prospecto_id="TEST", nombre_negocio="Demo", titulo_personalizado="Demo", mensaje_personalizado="Demo")

@app.route('/ver-nido')
def debug_nido(): return render_template('nido_template.html', nombre_negocio="Demo", token_sesion="TEST", titulo_personalizado="Demo", texto_contenido_de_valor="Demo")

# --- RUTA ANTIGUA CHAT (Mantenida por compatibilidad) ---
@app.route('/chat', methods=['POST'])
def chat_admin():
    global dashboard_brain
    if not dashboard_brain and create_chatbot: dashboard_brain = create_chatbot()
    if dashboard_brain: return jsonify({"response": dashboard_brain.invoke({"question": request.json.get('message')})})
    return jsonify({"response": "Mantenimiento"})

# --- NUEVA RUTA: CHAT ARQUITECTO (INTELIGENTE CON DB) ---
@app.route('/api/chat-arquitecto', methods=['POST'])
def chat_arquitecto_api():
    mensaje = request.json.get('message')
    if not mensaje:
        return jsonify({"response": "Por favor escribe una pregunta."})
    
    if arquitecto_brain:
        respuesta = arquitecto_brain.pensar(mensaje)
        return jsonify({"response": respuesta})
    else:
        return jsonify({"response": "El cerebro del Arquitecto no está activo (Falta API Key)."})

# --- API: OBTENER DETALLES COMPLETOS DE UNA CAMPAÑA ---
@app.route('/api/campana/<string:id>', methods=['GET'])
def obtener_detalle_campana(id):
    conn = get_db_connection()
    if not conn: return jsonify({"error": "No DB"}), 500
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                id, campaign_name, product_description, target_audience, 
                product_type, search_languages, geo_location,
                ticket_price, competitors, cta_goal, pain_points_defined, 
                tone_voice, red_flags, ai_constitution, ai_blackboard,
                daily_prospects_limit, whatsapp_number, sales_link
            FROM campaigns 
            WHERE id = %s
        """, (id,))
        row = cur.fetchone()
        
        if row:
            campana = {
                "id": row[0],
                "campaign_name": row[1],
                "product_description": row[2],
                "target_audience": row[3],
                "product_type": row[4],
                "languages": row[5],
                "geo_location": row[6],
                "ticket_price": row[7],
                "competitors": row[8],
                "cta_goal": row[9],
                "pain_points_defined": row[10],
                "tone_voice": row[11],
                "red_flags": row[12],
                "adn_corporativo": row[13],
                "pizarron_contexto": row[14],
                "daily_prospects_limit": row[15],
                "whatsapp_number": row[16],
                "sales_link": row[17]
            }
            return jsonify(campana)
        return jsonify({"error": "No encontrada"}), 404
    except Exception as e:
        print(f"Error fetching campaign: {e}")
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
            UPDATE campaigns 
            SET campaign_name = %s, product_description = %s, target_audience = %s,
                search_languages = %s, ticket_price = %s, competitors = %s,
                cta_goal = %s, pain_points_defined = %s, red_flags = %s,
                tone_voice = %s, ai_constitution = %s, ai_blackboard = %s,
                whatsapp_number = %s, sales_link = %s
            WHERE id = %s
        """, (
            d.get('campaign_name'), d.get('product_description'), d.get('target_audience'),
            d.get('languages'), d.get('ticket_price'), d.get('competidores'),
            d.get('cta_goal'), d.get('pain_points_defined'), d.get('red_flags'),
            d.get('tone_voice'), d.get('adn_corporativo'), d.get('pizarron_contexto'),
            d.get('whatsapp_number'), d.get('sales_link'),
            d.get('id')
        ))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
