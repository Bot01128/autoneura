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

print("!!! ESTOY CORRIENDO LA VERSION V4 - AUTO-CURACIÓN Y MULTIPLATAFORMA !!!")

# --- CONFIGURACIÓN INICIAL ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - CAZADOR - %(levelname)s - %(message)s')

APIFY_TOKEN = os.environ.get("APIFY_API_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")

# --- CONSTANTES FINANCIERAS ---
PRESUPUESTO_POR_PROSPECTO_CONTRATADO = 4.0
MULTIPLICADOR_RAW_LEADS = 200

# --- 1. CEREBRO FINANCIERO ---
def verificar_presupuesto_mensual(campana_id, limite_diario_contratado):
    if not limite_diario_contratado: limite_diario_contratado = 4
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

# --- 2. CEREBRO ESTRATÉGICO ---
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
        TAREA: Genera UNA frase de búsqueda optimizada para encontrar clientes potenciales en esa plataforma. SOLO LA FRASE.
        """

        model, model_id = brain.get_optimal_model(task_type="velocidad")
        response = model.generate_content(prompt)
        brain.register_usage(model_id)
        
        busqueda_optimizada = response.text.strip().replace('"', '')
        logging.info(f"🎯 IA: '{busqueda_original}' -> '{busqueda_optimizada}'")
        return busqueda_optimizada

    except Exception as e:
        logging.warning(f"⚠️ IA Falló búsqueda. Usando original. Error: {e}")
        if model_id and hasattr(brain, 'report_failure'): brain.report_failure(model_id)
        return busqueda_original
    finally:
        if conn: conn.close()

# --- 3. CONSULTA AL ARSENAL ---
def consultar_arsenal(plataforma_objetivo, tipo_producto):
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        # Buscamos la herramienta activa con mayor confianza
        query = """
            SELECT actor_id, input_config FROM bot_arsenal 
            WHERE platform = %s AND is_active = TRUE ORDER BY confidence_level DESC LIMIT 1;
        """
        cur.execute(query, (plataforma_objetivo,))
        resultado = cur.fetchone()
        cur.close()
        
        if resultado:
            return {"actor_id": resultado[0], "config_extra": resultado[1]}
        else:
            # Fallback seguro: Google Maps siempre confiable
            logging.warning(f"⚠️ No hay herramienta activa para {plataforma_objetivo}. Usando Google Maps por defecto.")
            return {"actor_id": "compass/crawler-google-places", "config_extra": {}}
            
    except Exception as e:
        return {"actor_id": "compass/crawler-google-places", "config_extra": {}}
    finally:
        if conn: conn.close()

# --- 4. PREPARAR INPUT BLINDADO ---
def preparar_input_blindado(actor_id, busqueda, ubicacion, max_items, config_extra):
    if not ubicacion or str(ubicacion).lower() == "none" or ubicacion == "":
        ubicacion = "United States"
        
    base_input = {"maxItems": int(max_items), "proxy": {"useApifyProxy": True}}
    
    # Fusionar configuración extra de la base de datos (JSON)
    if config_extra: 
        if isinstance(config_extra, str):
            try: base_input.update(json.loads(config_extra))
            except: pass
        else:
            base_input.update(config_extra)

    # Configuración Específica por Actor
    if "google" in actor_id:
        base_input.update({
            "searchStringsArray": [busqueda], 
            "locationQuery": str(ubicacion), 
            "maxCrawledPlacesPerSearch": int(max_items),
            "maxImages": 0 # Ahorro
        })
    elif "tiktok" in actor_id:
        base_input.update({"searchQueries": [busqueda], "resultsPerPage": int(max_items)})
    elif "instagram" in actor_id:
        base_input.update({"search": busqueda, "resultsLimit": int(max_items), "searchType": "hashtag"}) # Default a hashtag si no se especifica
    elif "facebook" in actor_id:
        base_input.update({"startUrls": [{"url": f"https://www.facebook.com/search/pages/?q={busqueda}"}]})
    
    return base_input

# --- 5. FILTRO Y NORMALIZACIÓN (SOPORTE REDES SOCIALES) ---
def validar_y_normalizar(item, plataforma, bot_id):
    datos = {
        "business_name": None, "website_url": None, "phone_number": None, 
        "email": None, "social_profiles": {}, "raw_data": item, "source_bot_id": bot_id
    }

    # A. Google Maps (El estándar de oro)
    if "google" in bot_id or "compass" in bot_id:
        datos["business_name"] = item.get("title", item.get("name"))
        datos["website_url"] = item.get("website")
        datos["phone_number"] = item.get("phone")
        datos["email"] = item.get("email") 
        # Filtro de calidad: Debe tener al menos una forma de contacto o web
        if not (datos["phone_number"] or datos["website_url"] or datos["email"]): return None 

    # B. TikTok
    elif "tiktok" in bot_id:
        author = item.get("authorMeta", {})
        datos["business_name"] = author.get("nickName") or author.get("name")
        datos["website_url"] = author.get("signatureLink")
        # Guardamos el perfil
        handle = author.get("name")
        if handle: datos["social_profiles"]["tiktok"] = f"https://www.tiktok.com/@{handle}"

    # C. Instagram
    elif "instagram" in bot_id:
        datos["business_name"] = item.get("fullName") or item.get("username")
        datos["website_url"] = item.get("externalUrl")
        # Guardamos perfil
        user = item.get("username")
        if user: datos["social_profiles"]["instagram"] = f"https://www.instagram.com/{user}"
        
        # Intentamos sacar email de la biografía si no viene explícito
        bio = item.get("biography", "")
        if bio and not datos["email"]:
            import re
            emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', bio)
            if emails: datos["email"] = emails[0]

    # D. Facebook / Twitter / Otros
    else:
        # Intento genérico de rescate
        datos["business_name"] = item.get("name") or item.get("title") or item.get("username")
        datos["website_url"] = item.get("url") or item.get("website")

    if not datos["business_name"]: return None
    return datos

# --- 6. EJECUCIÓN PRINCIPAL CON AUTO-CURACIÓN ---
def ejecutar_caza(campana_id, prompt_busqueda, ubicacion, plataforma="Google Maps", tipo_producto="Tangible", limite_diario_contratado=4):
    cantidad_a_cazar = verificar_presupuesto_mensual(campana_id, limite_diario_contratado)
    if cantidad_a_cazar <= 0:
        logging.info("⏸️ Cazador en pausa (Presupuesto).")
        return False

    logging.info(f"🚀 CAZANDO: {cantidad_a_cazar} prospectos | Campaña: {campana_id}")
    
    # Optimización IA
    busqueda_final = optimizar_busqueda_con_ia(campana_id, prompt_busqueda, plataforma)
    time.sleep(1)

    # Selección de Arma
    bot_info = consultar_arsenal(plataforma, tipo_producto)
    actor_id = bot_info["actor_id"]
    
    logging.info(f"🛠️ Herramienta seleccionada: {actor_id} para {plataforma}")

    try:
        client = ApifyClient(APIFY_TOKEN)
        run_input = preparar_input_blindado(actor_id, busqueda_final, ubicacion, cantidad_a_cazar, bot_info["config_extra"])
        
        logging.info(f"📡 Apify Run ({actor_id}) -> '{busqueda_final}'")
        run = client.actor(actor_id).call(run_input=run_input)
        
        if not run or run.get('status') != 'SUCCEEDED':
            logging.error("❌ Fallo en Apify (Status no Succeeded).")
            return False

        dataset_id = run["defaultDatasetId"]
        
        # Guardado en Base de Datos
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        contador = 0
        
        for item in client.dataset(dataset_id).iterate_items():
            datos = validar_y_normalizar(item, plataforma, actor_id)
            if not datos: continue 
            
            try:
                # Insertar o ignorar si ya existe (Evitar duplicados)
                # OJO: Guardamos 'social_profiles' como JSON
                cur.execute(
                    """INSERT INTO prospects (campaign_id, business_name, website_url, phone_number, captured_email, social_profiles, source_bot_id, status, raw_data, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, 'cazado', %s, NOW()) 
                       ON CONFLICT DO NOTHING RETURNING id;""",
                    (campana_id, datos["business_name"], datos["website_url"], datos["phone_number"], datos["email"], Json(datos["social_profiles"]), actor_id, Json(datos["raw_data"]))
                )
                if cur.rowcount > 0: contador += 1
            except Exception as e_db:
                conn.rollback()
                logging.error(f"Error guardando prospecto: {e_db}")
            else:
                conn.commit()
                
        cur.close()
        conn.close()
        logging.info(f"✅ FINALIZADO. Guardados: {contador}")
        return True

    except Exception as e:
        error_msg = str(e)
        logging.critical(f"🔥 Error Crítico Cazador: {error_msg}")
        
        # =============================================================
        # 🚑 AUTO-CURACIÓN: SI LA HERRAMIENTA NO EXISTE, LA APAGAMOS
        # =============================================================
        if "Actor with this name was not found" in error_msg or "Actor not found" in error_msg:
            logging.info(f"🔧 AUTO-REPARACIÓN: La herramienta {actor_id} está rota. Apagándola en DB...")
            try:
                conn_fix = psycopg2.connect(DATABASE_URL)
                cur_fix = conn_fix.cursor()
                
                # 1. Apagamos la herramienta rota
                cur_fix.execute("UPDATE bot_arsenal SET is_active = FALSE WHERE actor_id = %s", (actor_id,))
                
                # 2. Si era LinkedIn u otra rara, nos aseguramos que Google Maps esté activo como respaldo
                cur_fix.execute("UPDATE bot_arsenal SET is_active = TRUE WHERE platform = 'Google Maps'")
                
                conn_fix.commit()
                cur_fix.close()
                conn_fix.close()
                logging.info("✅ Herramienta rota desactivada. El próximo ciclo usará Google Maps.")
            except Exception as ex:
                logging.error(f"Error intentando auto-reparar: {ex}")
        # =============================================================
        
        return False

# =========================================================================
# 🛑 ANALISIS DE PROSPECTOS (PARA MODO INDEPENDIENTE)
# =========================================================================

def analizar_prospecto_ia(datos, contexto_campana):
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
            time.sleep(1)
    return {"es_calificado": False, "razon": "Error IA"}

def procesar_prospectos_pendientes():
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT p.id, p.raw_data, c.campaign_name, c.product_description 
            FROM prospects p JOIN campaigns c ON p.campaign_id = c.id 
            WHERE p.status = 'cazado' LIMIT 5
        """)
        pendientes = cur.fetchall()
        
        if pendientes:
            logging.info(f"🧠 Analizando {len(pendientes)} prospectos (Modo Independiente)...")
            for pid, raw, cname, cprod in pendientes:
                contexto = f"Campaña: {cname}, Producto: {cprod}"
                resultado = analizar_prospecto_ia(raw, contexto)
                nuevo_estado = 'calificado' if resultado.get('es_calificado') else 'descartado'
                cur.execute("UPDATE prospects SET status = %s, ai_analysis_log = %s WHERE id = %s", (nuevo_estado, Json(resultado), pid))
                conn.commit()
        
        cur.close()
    except Exception as e:
        logging.error(f"Error procesando prospectos: {e}")
    finally:
        if conn: conn.close()

if __name__ == "__main__":
    logging.info(">>> 🤖 CAZADOR ACTIVO (MODO BLINDADO V4) <<<")
    while True:
        procesar_prospectos_pendientes()
        time.sleep(60)
