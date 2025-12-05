import os
import time
import json
import logging
import requests
import psycopg2
from bs4 import BeautifulSoup
import google.generativeai as genai
from psycopg2.extras import Json
from dotenv import load_dotenv

# --- CONEXIÓN AL CEREBRO ROTATIVO (NUEVO) ---
try:
    from ai_manager import brain
except ImportError:
    brain = None
    print("⚠️ ADVERTENCIA: ai_manager.py no encontrado. El Analista no podrá pensar.")

# --- CONFIGURACIÓN ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - ANALISTA - %(levelname)s - %(message)s')

DATABASE_URL = os.environ.get("DATABASE_URL")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# --- IA BLINDADA (YA NO ES FIJA) ---
# El control ahora lo tiene ai_manager.

# --- 1. LECTURA DE WEB (OJOS DEL ANALISTA - INTACTO) ---

def escanear_web_simple(url):
    """
    Entra a la web del prospecto (si tiene) y extrae texto clave.
    """
    if not url: return ""
    if not url.startswith("http"): url = "http://" + url
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200: return ""
        
        soup = BeautifulSoup(response.text, 'html.parser')
        textos = []
        for tag in soup.find_all(['h1', 'h2', 'h3', 'p', 'meta']):
            if tag.name == 'meta' and tag.get('name') == 'description':
                textos.append(tag.get('content', ''))
            else:
                textos.append(tag.get_text(strip=True))
        
        return " ".join(textos)[:2500] 

    except Exception as e:
        logging.warning(f"No se pudo leer la web {url}: {e}")
        return ""

# --- 2. EL PSICÓLOGO (GEMINI ROTATIVO) ---

def realizar_psicoanalisis(prospecto, campana, texto_web):
    if not brain: return None

    # Prompt optimizado para Venta Consultiva
    prompt = f"""
    ERES UN ANALISTA DE VENTAS B2B DE ÉLITE.
    
    --- DATOS DE LA CAMPAÑA (LO QUE VENDEMOS) ---
    Producto: {campana['product_description']}
    Precio (Ticket): {campana.get('ticket_price', 'N/A')}
    Red Flags (DESCARTAR SI): {campana.get('red_flags', 'Ninguna')}
    Dolores Definidos: {campana.get('pain_points_defined', 'General')}
    Competencia: {campana.get('competitors', 'Desconocida')}
    
    --- DATOS DEL PROSPECTO (A QUIÉN ANALIZAS) ---
    Nombre: {prospecto['business_name']}
    Info Web/Bio: {texto_web}
    Datos Crudos (JSON): {str(prospecto.get('raw_data', {}))[:1000]}
    
    --- TUS ÓRDENES ---
    1. FILTRO DE RED FLAGS: Si encuentras palabras prohibidas o el perfil no encaja con el precio, DESCÁRTALO.
    2. DETECCIÓN DE DOLORES: Busca evidencia de los dolores de la campaña.
    3. PERFILADO: Infiere género, edad aprox y tono.

    --- SALIDA OBLIGATORIA (JSON PURO) ---
    Responde SOLO con este JSON:
    {{
        "veredicto": "APROBADO" o "DESCARTADO",
        "razon_descarte": "Texto explicativo si se descarta (o null)",
        "perfil_demografico": {{
            "tono_recomendado": "{campana.get('tone_voice', 'Profesional')}"
        }},
        "analisis_dolores": [
            {{
                "dolor_detectado": "Ej: Falta de tiempo",
                "plan_ataque": "Ej: Ofrecer automatización"
            }}
        ],
        "puntuacion_calidad": 0-100
    }}
    """

    model_id = None # Para reportar fallos
    try:
        # CAMBIO: Pedimos cerebro RÁPIDO (Flash) al Manager
        model, model_id = brain.get_optimal_model(task_type="velocidad")
        
        respuesta = model.generate_content(prompt)
        
        # CAMBIO: Registramos uso
        brain.register_usage(model_id)
        
        texto_limpio = respuesta.text.replace("```json", "").replace("```", "").strip()
        return json.loads(texto_limpio)

    except Exception as e:
        logging.error(f"Error interpretando a Gemini: {e}")
        # CAMBIO: Reportamos muerte si es 429
        if model_id and "429" in str(e):
            brain.report_failure(model_id)
        return None

# --- 3. FUNCIÓN PRINCIPAL DEL TRABAJADOR (MODIFICADO PARA SECUENCIA) ---

def trabajar_analista():
    # Eliminamos el while True para que funcione en la cadena del Orquestador
    logging.info("🧠 Analista Iniciado (Modo Secuencial - Brain Rotativo).")
    
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        # --- SELECCIÓN OPORTUNISTA ---
        # Busca:
        # 1. 'espiado' (El Espía trajo datos)
        # 2. 'cazado' CON EMAIL (El Cazador trajo datos directos)
        query = """
            SELECT 
                p.id, p.business_name, p.website_url, p.raw_data, p.captured_email,
                c.id as campaign_id, c.product_description, c.ticket_price, 
                c.red_flags, c.pain_points_defined, c.competitors, c.tone_voice
            FROM prospects p
            JOIN campaigns c ON p.campaign_id = c.id
            WHERE p.status = 'espiado' 
            OR (p.status = 'cazado' AND (p.captured_email IS NOT NULL OR p.phone_number IS NOT NULL))
            LIMIT 5;
        """
        cur.execute(query)
        lote = cur.fetchall()

        if not lote:
            logging.info("💤 Nada que analizar en este turno.")
            return # Termina el turno y devuelve el control al Orquestador

        logging.info(f"🧠 Procesando lote de {len(lote)} prospectos...")

        for fila in lote:
            # Mapeo de datos
            prospecto = {
                "id": fila[0], "business_name": fila[1], "website_url": fila[2], 
                "raw_data": fila[3], "email": fila[4]
            }
            campana = {
                "product_description": fila[6], "ticket_price": fila[7],
                "red_flags": fila[8], "pain_points_defined": fila[9],
                "competitors": fila[10], "tone_voice": fila[11]
            }

            # 1. Escanear
            texto_web = ""
            if prospecto["website_url"]:
                texto_web = escanear_web_simple(prospecto["website_url"])
            
            # 2. Analizar (Ahora usa el Brain Rotativo)
            analisis_ia = realizar_psicoanalisis(prospecto, campana, texto_web)

            # 3. Decidir
            nuevo_estado = "analizado_exitoso"
            pain_points_json = None

            if not analisis_ia:
                logging.warning(f"⚠️ Fallo análisis IA ID {prospecto['id']}")
                time.sleep(2) 
                continue 

            if analisis_ia.get("veredicto") == "DESCARTADO":
                nuevo_estado = "descartado"
                logging.info(f"🚫 DESCARTADO ID {prospecto['id']}: {analisis_ia.get('razon_descarte')}")
            else:
                logging.info(f"✅ APROBADO ID {prospecto['id']}")
                pain_points_json = Json(analisis_ia)

            # 4. Guardar
            cur.execute("""
                UPDATE prospects 
                SET status = %s,
                    pain_points = %s,
                    updated_at = NOW()
                WHERE id = %s
            """, (nuevo_estado, pain_points_json, prospecto['id']))
            conn.commit()
            
            # Pausa breve para no saturar
            time.sleep(2) 

        cur.close()

    except Exception as e:
        logging.error(f"🔥 Error Crítico Analista: {e}")
    finally:
        if conn: conn.close()

if __name__ == "__main__":
    trabajar_analista()
