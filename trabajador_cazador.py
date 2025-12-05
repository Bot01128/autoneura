import os
import json
import logging
import datetime
import time
from apify_client import ApifyClient
import psycopg2
from psycopg2.extras import Json
from dotenv import load_dotenv

# --- IMPORTACIÓN DEL GERENTE DE IA ---
try:
    from ai_manager import brain
except ImportError:
    brain = None
    print("⚠️ ADVERTENCIA: ai_manager.py no encontrado. La IA no funcionará.")
print("!!! ESTOY CORRIENDO LA VERSION NUEVA V3 - BLINDADA !!!")
# --- CONFIGURACIÓN INICIAL ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - CAZADOR - %(levelname)s - %(message)s')

APIFY_TOKEN = os.environ.get("APIFY_API_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")

# --- CONSTANTES FINANCIERAS (INTACTAS) ---
PRESUPUESTO_POR_PROSPECTO_CONTRATADO = 4.0
COSTO_ESTIMADO_APIFY_POR_1000 = 5.0
MULTIPLICADOR_RAW_LEADS = 200

# --- 1. CEREBRO FINANCIERO (INTACTO) ---
def verificar_presupuesto_mensual(campana_id, limite_diario_contratado):
    if not limite_diario_contratado:
        limite_diario_contratado = 4
    try:
        limite_diario_int = int(limite_diario_contratado)
        if limite_diario_int < 1: limite_diario_int = 4
    except:
        limite_diario_int = 4

    presupuesto_total_mes = limite_diario_int * PRESUPUESTO_POR_PROSPECTO_CONTRATADO
    tope_leads_mensual = presupuesto_total_mes * MULTIPLICADOR_RAW_LEADS

    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        hoy = datetime.date.today()
        inicio_mes = hoy.replace(day=1)
        query = """
            SELECT count(*) FROM prospects 
            WHERE campaign_id = %s AND status = 'cazado' AND created_at >= %s;
        """
        cur.execute(query, (campana_id, inicio_mes))
        cazados_mes_actual = cur.fetchone()[0]
        cur.close()

        saldo_restante = tope_leads_mensual - cazados_mes_actual
        if saldo_restante <= 0:
            logging.warning(f"🛑 FRENO FINANCIERO: Tope mensual alcanzado. Cazador duerme.")
            return 0
        
        cuota_diaria_sugerida = int(tope_leads_mensual / 30)
        cantidad_a_cazar = min(cuota_diaria_sugerida, saldo_restante)
        if cantidad_a_cazar < 5: cantidad_a_cazar = 5

        logging.info(f"💰 PRESUPUESTO: {cazados_mes_actual}/{int(tope_leads_mensual)}. Autorizado hoy: {cantidad_a_cazar}")
        return cantidad_a_cazar
    except Exception as e:
        logging.error(f"❌ Error verificando presupuesto: {e}")
        return 0 
    finally:
        if conn: conn.close()

# --- 2. CEREBRO ESTRATÉGICO (CON REPORTE DE FALLOS) ---
def optimizar_busqueda_con_ia(campana_id, busqueda_original, plataforma):
    if not brain: return busqueda_original

    logging.info("🧠 IA: Optimizando búsqueda...")
    conn = None
    model_id = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT campaign_name, product_description, target_audience, cta_goal FROM campaigns WHERE id = %s", (campana_id,))
        row = cur.fetchone()
        cur.close()

        if not row: return busqueda_original
        nombre_c, producto, target, mision = row
        
        prompt = f"""
        CONTEXTO: Producto: {producto}, Target: {target}, Misión: {mision}, Plataforma: {plataforma}
        INTENCIÓN: "{busqueda_original}"
        TAREA: Genera UNA frase de búsqueda optimizada. SOLO LA FRASE.
        """

        model, model_id = brain.get_optimal_model(task_type="velocidad")
        response = model.generate_content(prompt)
        brain.register_usage(model_id)
        
        busqueda_optimizada = response.text.strip().replace('"', '')
        logging.info(f"🎯 IA: '{busqueda_original}' -> '{busqueda_optimizada}'")
        return busqueda_optimizada

    except Exception as e:
        logging.warning(f"⚠️ IA Falló búsqueda. Reportando. Error: {e}")
        if model_id: brain.report_failure(model_id)
        return busqueda_original
    finally:
        if conn: conn.close()

# --- 3. CONSULTA AL ARSENAL (INTACTO) ---
def consultar_arsenal(plataforma_objetivo, tipo_producto):
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        query = """
            SELECT actor_id, input_config FROM bot_arsenal 
            WHERE platform = %s AND is_active = TRUE ORDER BY confidence_level DESC LIMIT 1;
        """
        cur.execute(query, (plataforma_objetivo,))
        resultado = cur.fetchone()
        cur.close()
        return {"actor_id": resultado[0], "config_extra": resultado[1]} if resultado else {"actor_id": "compass/crawler-google-places", "config_extra": {}}
    except Exception as e:
        return {"actor_id": "compass/crawler-google-places", "config_extra": {}}
    finally:
        if conn: conn.close()

# --- 4. PREPARAR INPUT (INTACTO) ---
def preparar_input_blindado(actor_id, busqueda, ubicacion, max_items, config_extra):
    if not ubicacion or str(ubicacion).lower() == "none" or ubicacion == "":
        ubicacion = "United States"
    base_input = {"maxItems": int(max_items), "proxy": {"useApifyProxy": True}}
    if config_extra: base_input.update(config_extra)

    reglas_ahorro = {
        "downloadImages": False, "downloadVideos": False, "downloadMedia": False,
        "scrapePosts": False, "scrapeStories": False, "maxReviews": 0, "reviewsDistribution": False
    }

    if "google" in actor_id:
        base_input.update({"searchStringsArray": [busqueda], "locationQuery": str(ubicacion), "maxCrawledPlacesPerSearch": int(max_items), "maxImages": 0})
    elif "tiktok" in actor_id or "instagram" in actor_id:
        base_input.update({"searchQueries": [busqueda], "resultsLimit": int(max_items), "resultsPerPage": int(max_items)})
    
    base_input.update(reglas_ahorro)
    return base_input

# --- 5. FILTRO Y NORMALIZACIÓN (INTACTO) ---
def validar_y_normalizar(item, plataforma, bot_id):
    datos = {"business_name": None, "website_url": None, "phone_number": None, "email": None, "social_profiles": {}, "raw_data": item, "source_bot_id": bot_id}

    if "google" in bot_id or plataforma == "Google Maps":
        datos["business_name"] = item.get("title", item.get("name"))
        datos["website_url"] = item.get("website")
        datos["phone_number"] = item.get("phone")
        datos["email"] = item.get("email") 
        if not (datos["phone_number"] or datos["website_url"] or datos["email"]): return None 

    elif "tiktok" in bot_id:
        author = item.get("authorMeta", {})
        datos["business_name"] = author.get("nickName") or author.get("name")
        datos["website_url"] = author.get("signatureLink")
        datos["social_profiles"] = {"tiktok": f"https://www.tiktok.com/@{author.get('name')}"}

    elif "instagram" in bot_id:
        datos["business_name"] = item.get("fullName") or item.get("username")
        datos["website_url"] = item.get("externalUrl")
        datos["social_profiles"] = {"instagram": f"https://www.instagram.com/{item.get('username')}"}

    if not datos["business_name"]: return None
    return datos

# --- 6. EJECUCIÓN PRINCIPAL (INTACTO) ---
def ejecutar_caza(campana_id, prompt_busqueda, ubicacion, plataforma="Google Maps", tipo_producto="Tangible", limite_diario_contratado=4):
    cantidad_a_cazar = verificar_presupuesto_mensual(campana_id, limite_diario_contratado)
    if cantidad_a_cazar <= 0:
        logging.info("⏸️ Cazador en pausa.")
        return False

    logging.info(f"🚀 CAZANDO: {cantidad_a_cazar} prospectos | Campaña: {campana_id}")
    busqueda_final = optimizar_busqueda_con_ia(campana_id, prompt_busqueda, plataforma)
    time.sleep(1)

    bot_info = consultar_arsenal(plataforma, tipo_producto)
    actor_id = bot_info["actor_id"]
    
    try:
        client = ApifyClient(APIFY_TOKEN)
        run_input = preparar_input_blindado(actor_id, busqueda_final, ubicacion, cantidad_a_cazar, bot_info["config_extra"])
        logging.info(f"📡 Apify Run ({actor_id}) -> '{busqueda_final}'")
        run = client.actor(actor_id).call(run_input=run_input)
        
        if not run or run.get('status') != 'SUCCEEDED':
            logging.error("❌ Fallo en Apify.")
            return False

        dataset_id = run["defaultDatasetId"]
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        contador = 0
        for item in client.dataset(dataset_id).iterate_items():
            datos = validar_y_normalizar(item, plataforma, actor_id)
            if not datos: continue 
            try:
                cur.execute(
                    """INSERT INTO prospects (campaign_id, business_name, website_url, phone_number, captured_email, social_profiles, source_bot_id, status, raw_data, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, 'cazado', %s, NOW()) ON CONFLICT DO NOTHING RETURNING id;""",
                    (campana_id, datos["business_name"], datos["website_url"], datos["phone_number"], datos["email"], Json(datos["social_profiles"]), actor_id, Json(datos["raw_data"]))
                )
                if cur.rowcount > 0: contador += 1
            except: conn.rollback()
            else: conn.commit()
        cur.close()
        conn.close()
        logging.info(f"✅ FINALIZADO. Guardados: {contador}")
        return True
    except Exception as e:
        logging.critical(f"🔥 Error Crítico Cazador: {e}")
        return False

# =========================================================================
# 🛑 AQUÍ ESTABA LO QUE FALTABA PARA QUE LA IA NO FALLE EN LOS LOGS ROJOS
# =========================================================================

def analizar_prospecto_ia(datos, contexto_campana):
    """ Función blindada para analizar leads con rotación y reporte de fallos """
    if not brain: return {"es_calificado": False, "razon": "Sin Cerebro"}
    
    max_intentos = 2
    model_id = None
    for intento in range(max_intentos):
        try:
            model, model_id = brain.get_optimal_model(task_type="velocidad")
            prompt = f"""
            ERES UN EXPERTO B2B. ANALIZA:
            CAMPAÑA: {contexto_campana}
            PROSPECTO: {json.dumps(datos, indent=2)}
            RESPONDE SOLO JSON: {{ "es_calificado": true/false, "razon": "...", "nivel_interes": 1-10 }}
            """
            res = model.generate_content(prompt)
            brain.register_usage(model_id)
            clean_json = res.text.strip().replace('```json','').replace('```','')
            return json.loads(clean_json)
        except Exception as e:
            logging.warning(f"⚠️ IA Falló Análisis. Intento {intento+1}. Error: {e}")
            if model_id and "429" in str(e): 
                brain.report_failure(model_id) # Reportamos muerte
            time.sleep(2)
    return {"es_calificado": False, "razon": "Error IA"}

def procesar_prospectos_pendientes():
    """ Ciclo que busca prospectos 'cazados' y los analiza con IA """
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Buscamos prospectos que necesiten análisis
        cur.execute("""
            SELECT p.id, p.raw_data, c.campaign_name, c.product_description 
            FROM prospects p JOIN campaigns c ON p.campaign_id = c.id 
            WHERE p.status = 'cazado' LIMIT 5
        """)
        pendientes = cur.fetchall()
        
        if pendientes:
            logging.info(f"🧠 Procesando lote de {len(pendientes)} prospectos...")
            
            for pid, raw, cname, cprod in pendientes:
                contexto = f"Campaña: {cname}, Producto: {cprod}"
                resultado = analizar_prospecto_ia(raw, contexto)
                
                nuevo_estado = 'calificado' if resultado.get('es_calificado') else 'descartado'
                cur.execute("UPDATE prospects SET status = %s, ai_analysis_log = %s WHERE id = %s",
                            (nuevo_estado, Json(resultado), pid))
                conn.commit()
        else:
            logging.info("💤 No hay prospectos pendientes de análisis.")
            
        cur.close()
    except Exception as e:
        logging.error(f"Error procesando prospectos: {e}")
    finally:
        if conn: conn.close()

# --- BUCLE PRINCIPAL ---
if __name__ == "__main__":
    logging.info(">>> 🤖 CAZADOR ACTIVO (MODO BLINDADO) <<<")
    while True:
        # 1. Fase de Caza (Buscar nuevos si hace falta)
        # (Aquí iría tu lógica para disparar ejecutar_caza según horario, lo dejo pasivo por seguridad)
        
        # 2. Fase de Análisis (Lo que estaba fallando en rojo)
        procesar_prospectos_pendientes()
        
        time.sleep(60) # Descanso de 1 minuto
# Actualizacion forzada
