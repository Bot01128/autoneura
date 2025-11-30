import os
import json
import logging
import datetime
from apify_client import ApifyClient
import psycopg2
from psycopg2.extras import Json
from dotenv import load_dotenv

# --- CONFIGURACIÓN INICIAL ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - CAZADOR - %(levelname)s - %(message)s')

APIFY_TOKEN = os.environ.get("APIFY_API_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")

# --- CONSTANTES FINANCIERAS (EL BOZAL) ---
PRESUPUESTO_POR_PROSPECTO_CONTRATADO = 4.0  # Dólares USD
COSTO_ESTIMADO_APIFY_POR_1000 = 5.0         # Costo promedio x 1000 leads crudos
MULTIPLICADOR_RAW_LEADS = 200               # Cuántos leads crudos caben en 1 dólar (aprox)

# --- 1. CEREBRO FINANCIERO ---

def verificar_presupuesto_mensual(campana_id, limite_diario_contratado):
    """
    Calcula si tenemos saldo para cazar hoy.
    Regla: No gastar más de $4 x (Prospectos Diarios Contratados) al mes.
    """
    # Corrección: Asegurar que sea entero
    if not limite_diario_contratado:
        limite_diario_contratado = 4
    
    try:
        limite_diario_int = int(limite_diario_contratado)
        if limite_diario_int < 1: limite_diario_int = 4
    except:
        limite_diario_int = 4

    # 1. Calcular Techo Financiero
    presupuesto_total_mes = limite_diario_int * PRESUPUESTO_POR_PROSPECTO_CONTRATADO
    
    # 2. Traducir Dinero a "Cabezas" (Raw Leads)
    tope_leads_mensual = presupuesto_total_mes * MULTIPLICADOR_RAW_LEADS

    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        # 3. Contar cuánto hemos cazado este mes
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

        # 4. Decisión
        saldo_restante = tope_leads_mensual - cazados_mes_actual
        
        if saldo_restante <= 0:
            logging.warning(f"🛑 FRENO FINANCIERO: Se alcanzó el tope mensual de {int(tope_leads_mensual)} leads crudos. Cazador duerme.")
            return 0
        
        # Calculamos la cuota diaria segura
        cuota_diaria_sugerida = int(tope_leads_mensual / 30)
        cantidad_a_cazar = min(cuota_diaria_sugerida, saldo_restante)
        
        if cantidad_a_cazar < 5: cantidad_a_cazar = 5

        logging.info(f"💰 PRESUPUESTO: Llevamos {cazados_mes_actual}/{int(tope_leads_mensual)}. Autorizado cazar hoy: {cantidad_a_cazar}")
        return cantidad_a_cazar

    except Exception as e:
        logging.error(f"❌ Error verificando presupuesto: {e}")
        return 0 
    finally:
        if conn: conn.close()

# --- 2. CONSULTA AL ARSENAL ---

def consultar_arsenal(plataforma_objetivo, tipo_producto):
    logging.info(f"🔎 Consultando Arsenal para: Plataforma={plataforma_objetivo}")
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Busca el mejor bot activo para la plataforma
        # NOTA: Requiere que hayas ejecutado el SQL de corrección en Supabase
        query = """
            SELECT actor_id, input_config 
            FROM bot_arsenal 
            WHERE platform = %s 
            AND is_active = TRUE
            ORDER BY confidence_level DESC
            LIMIT 1;
        """
        cur.execute(query, (plataforma_objetivo,))
        resultado = cur.fetchone()
        cur.close()
        
        if resultado:
            return {"actor_id": resultado[0], "config_extra": resultado[1]}
        else:
            return {"actor_id": "compass/crawler-google-places", "config_extra": {}}
    except Exception as e:
        logging.error(f"❌ Error Arsenal (Usando Default): {e}")
        return {"actor_id": "compass/crawler-google-places", "config_extra": {}}
    finally:
        if conn: conn.close()

# --- 3. CONFIGURACIÓN AHORRADORA (INPUTS) ---

def preparar_input_blindado(actor_id, busqueda, ubicacion, max_items, config_extra):
    """
    Configura Apify para gastar lo MÍNIMO posible.
    """
    # CORRECCIÓN DE ERROR: Validar que ubicación sea string y no esté vacía
    if not ubicacion or str(ubicacion).lower() == "none" or ubicacion == "":
        ubicacion = "United States"
    
    base_input = {
        "maxItems": int(max_items),
        "proxy": {"useApifyProxy": True}
    }

    if config_extra:
        base_input.update(config_extra)

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
            "locationQuery": str(ubicacion), # Forzamos string para evitar error
            "maxCrawledPlacesPerSearch": int(max_items),
            "maxImages": 0,
            # "website": True <-- ELIMINADO: Causaba error 'must be string' en algunos actores
        })
    
    elif "tiktok" in actor_id or "instagram" in actor_id:
        base_input.update({
            "searchQueries": [busqueda],
            "resultsLimit": int(max_items),
            "resultsPerPage": int(max_items)
        })

    base_input.update(reglas_ahorro)
    return base_input

# --- 4. FILTRO DE CALIDAD Y NORMALIZACIÓN ---

def validar_y_normalizar(item, plataforma, bot_id):
    """
    Decide si el prospecto vale la pena o es basura.
    """
    datos = {
        "business_name": None,
        "website_url": None,
        "phone_number": None,
        "email": None, 
        "social_profiles": {},
        "raw_data": item,
        "source_bot_id": bot_id
    }

    if "google" in bot_id or plataforma == "Google Maps":
        datos["business_name"] = item.get("title", item.get("name"))
        datos["website_url"] = item.get("website")
        datos["phone_number"] = item.get("phone")
        datos["email"] = item.get("email") 
        
        # FILTRO MAESTRO: Si es empresa y no tiene NADA de contacto, es basura.
        tiene_contacto = datos["phone_number"] or datos["website_url"] or datos["email"]
        if not tiene_contacto:
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

# --- 5. FUNCIÓN PRINCIPAL ---

def ejecutar_caza(campana_id, prompt_busqueda, ubicacion, plataforma="Google Maps", tipo_producto="Tangible", limite_diario_contratado=4):
    
    # 1. VERIFICACIÓN FINANCIERA
    cantidad_a_cazar = verificar_presupuesto_mensual(campana_id, limite_diario_contratado)
    
    if cantidad_a_cazar <= 0:
        logging.info("⏸️ Cazador en pausa por presupuesto o fin de jornada.")
        return False

    logging.info(f"🚀 CAZANDO: {cantidad_a_cazar} prospectos | Campaña: {campana_id}")

    # 2. Consultar Arsenal
    bot_info = consultar_arsenal(plataforma, tipo_producto)
    actor_id = bot_info["actor_id"]
    config_extra = bot_info["config_extra"]

    # 3. Ejecutar Apify
    try:
        client = ApifyClient(APIFY_TOKEN)
        run_input = preparar_input_blindado(actor_id, prompt_busqueda, ubicacion, cantidad_a_cazar, config_extra)
        
        logging.info(f"📡 Apify Run ({actor_id})...")
        run = client.actor(actor_id).call(run_input=run_input)
        
        if not run or run.get('status') != 'SUCCEEDED':
            logging.error("❌ Fallo en Apify.")
            return False

        dataset_id = run["defaultDatasetId"]
        
        # 4. Procesar Resultados
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        contador_guardados = 0
        dataset_items = client.dataset(dataset_id).iterate_items()
        
        for item in dataset_items:
            datos_limpios = validar_y_normalizar(item, plataforma, actor_id)
            
            if not datos_limpios: 
                continue 

            try:
                cur.execute(
                    """
                    INSERT INTO prospects 
                    (campaign_id, business_name, website_url, phone_number, captured_email, social_profiles, source_bot_id, status, raw_data, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'cazado', %s, NOW())
                    ON CONFLICT DO NOTHING 
                    RETURNING id;
                    """,
                    (
                        campana_id,
                        datos_limpios["business_name"],
                        datos_limpios["website_url"],
                        datos_limpios["phone_number"],
                        datos_limpios["email"],
                        Json(datos_limpios["social_profiles"]),
                        actor_id,
                        Json(datos_limpios["raw_data"])
                    )
                )
                
                if cur.rowcount > 0:
                    contador_guardados += 1
                    
            except Exception as db_err:
                conn.rollback()
                continue
            else:
                conn.commit()

        cur.close()
        conn.close()
        
        logging.info(f"✅ FINALIZADO. Guardados: {contador_guardados} (Se filtró la basura).")
        return True

    except Exception as e:
        logging.critical(f"🔥 Error en worker_cazador: {e}")
        return False
