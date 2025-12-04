import os
import json
import logging
import datetime
import time
from apify_client import ApifyClient
import psycopg2
from psycopg2.extras import Json
from dotenv import load_dotenv

# --- IMPORTACIÓN DEL GERENTE DE IA (EL ÚNICO CAMBIO PARA ROTACIÓN) ---
try:
    from ai_manager import brain
except ImportError:
    brain = None
    print("⚠️ ADVERTENCIA: ai_manager.py no encontrado. La IA no funcionará.")

# --- CONFIGURACIÓN INICIAL ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - CAZADOR - %(levelname)s - %(message)s')

APIFY_TOKEN = os.environ.get("APIFY_API_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")

# --- CONSTANTES FINANCIERAS (EL BOZAL) - INTACTO ---
PRESUPUESTO_POR_PROSPECTO_CONTRATADO = 4.0  # Dólares USD
COSTO_ESTIMADO_APIFY_POR_1000 = 5.0         # Costo promedio x 1000 leads crudos
MULTIPLICADOR_RAW_LEADS = 200               # Cuántos leads crudos caben en 1 dólar (aprox)

# --- 1. CEREBRO FINANCIERO (INTACTO) ---

def verificar_presupuesto_mensual(campana_id, limite_diario_contratado):
    """
    Calcula si tenemos saldo para cazar hoy.
    """
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
            WHERE campaign_id = %s 
            AND status = 'cazado'
            AND created_at >= %s;
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

# --- 2. CEREBRO ESTRATÉGICO (MODIFICADO PARA USAR AI_MANAGER) ---

def optimizar_busqueda_con_ia(campana_id, busqueda_original, plataforma):
    """
    Intenta mejorar la búsqueda con IA usando ROTACIÓN DE LLAVES.
    Si falla, devuelve la búsqueda original.
    """
    # Verificamos si el Manager está cargado (Sustituye a la verificación de API KEY fija)
    if not brain:
        return busqueda_original

    logging.info("🧠 IA: Optimizando búsqueda (Usando Rotación)...")
    conn = None
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
        TAREA: Genera UNA frase de búsqueda optimizada para encontrar compradores reales en Google Maps.
        SOLO RESPONDE LA FRASE. Ej: "Tiendas de zapatos en Madrid"
        """

        # --- CAMBIO CLAVE: PEDIR MODELO AL MANAGER ---
        # Pedimos un modelo rápido ('velocidad') ya que es solo una frase corta.
        model, model_id = brain.get_optimal_model(task_type="velocidad")
        
        response = model.generate_content(prompt)
        
        # REGISTRAMOS EL USO
        brain.register_usage(model_id)
        
        busqueda_optimizada = response.text.strip().replace('"', '')

        logging.info(f"🎯 IA: '{busqueda_original}' -> '{busqueda_optimizada}'")
        return busqueda_optimizada

    except Exception as e:
        # AQUI ESTA LA PROTECCION: Si la IA falla (incluso rotando), NO detenemos el programa.
        logging.warning(f"⚠️ IA Falló o se agotaron las llaves. Usando búsqueda original. Error: {e}")
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
            SELECT actor_id, input_config 
            FROM bot_arsenal 
            WHERE platform = %s AND is_active = TRUE
            ORDER BY confidence_level DESC LIMIT 1;
        """
        cur.execute(query, (plataforma_objetivo,))
        resultado = cur.fetchone()
        cur.close()
        
        if resultado:
            return {"actor_id": resultado[0], "config_extra": resultado[1]}
        else:
            return {"actor_id": "compass/crawler-google-places", "config_extra": {}}
    except Exception as e:
        return {"actor_id": "compass/crawler-google-places", "config_extra": {}}
    finally:
        if conn: conn.close()

# --- 4. PREPARAR INPUT (INTACTO) ---

def preparar_input_blindado(actor_id, busqueda, ubicacion, max_items, config_extra):
    if not ubicacion or str(ubicacion).lower() == "none" or ubicacion == "":
        ubicacion = "United States"
    
    base_input = {
        "maxItems": int(max_items),
        "proxy": {"useApifyProxy": True}
    }

    if config_extra:
        base_input.update(config_extra)

    # Reglas de Ahorro Extremo
    reglas_ahorro = {
        "downloadImages": False,
        "downloadVideos": False,
        "downloadMedia": False,
        "scrapePosts": False,
        "scrapeStories": False,
        "maxReviews": 0,
        "reviewsDistribution": False
    }

    if "google" in actor_id:
        base_input.update({
            "searchStringsArray": [busqueda],
            "locationQuery": str(ubicacion),
            "maxCrawledPlacesPerSearch": int(max_items),
            "maxImages": 0,
        })
    elif "tiktok" in actor_id or "instagram" in actor_id:
        base_input.update({
            "searchQueries": [busqueda],
            "resultsLimit": int(max_items),
            "resultsPerPage": int(max_items)
        })

    base_input.update(reglas_ahorro)
    return base_input

# --- 5. FILTRO Y NORMALIZACIÓN (INTACTO) ---

def validar_y_normalizar(item, plataforma, bot_id):
    datos = {
        "business_name": None, "website_url": None, "phone_number": None,
        "email": None, "social_profiles": {}, "raw_data": item, "source_bot_id": bot_id
    }

    if "google" in bot_id or plataforma == "Google Maps":
        datos["business_name"] = item.get("title", item.get("name"))
        datos["website_url"] = item.get("website")
        datos["phone_number"] = item.get("phone")
        datos["email"] = item.get("email") 
        
        # SI NO HAY CONTACTO, ES BASURA
        if not (datos["phone_number"] or datos["website_url"] or datos["email"]):
            return None 

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
    
    # A. Verificación de Fondos
    cantidad_a_cazar = verificar_presupuesto_mensual(campana_id, limite_diario_contratado)
    if cantidad_a_cazar <= 0:
        logging.info("⏸️ Cazador en pausa.")
        return False

    logging.info(f"🚀 CAZANDO: {cantidad_a_cazar} prospectos | Campaña: {campana_id}")

    # B. Optimización IA (Con protección anti-crash y AHORA CON ROTACIÓN)
    busqueda_final = optimizar_busqueda_con_ia(campana_id, prompt_busqueda, plataforma)
    time.sleep(1)

    # C. Ejecución Apify
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
        
        # D. Guardado
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        contador = 0
        for item in client.dataset(dataset_id).iterate_items():
            datos = validar_y_normalizar(item, plataforma, actor_id)
            if not datos: continue 

            try:
                cur.execute(
                    """
                    INSERT INTO prospects 
                    (campaign_id, business_name, website_url, phone_number, captured_email, social_profiles, source_bot_id, status, raw_data, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'cazado', %s, NOW())
                    ON CONFLICT DO NOTHING RETURNING id;
                    """,
                    (campana_id, datos["business_name"], datos["website_url"], datos["phone_number"], 
                     datos["email"], Json(datos["social_profiles"]), actor_id, Json(datos["raw_data"]))
                )
                if cur.rowcount > 0: contador += 1
            except:
                conn.rollback()
            else:
                conn.commit()

        cur.close()
        conn.close()
        logging.info(f"✅ FINALIZADO. Guardados: {contador}")
        return True

    except Exception as e:
        logging.critical(f"🔥 Error Crítico Cazador: {e}")
        return False
