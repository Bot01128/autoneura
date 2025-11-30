import os
import time
import json
import logging
import psycopg2
from psycopg2.extras import Json
import google.generativeai as genai
from dotenv import load_dotenv

# --- CONFIGURACIÓN ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - PERSUASOR - %(levelname)s - %(message)s')

DATABASE_URL = os.environ.get("DATABASE_URL")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

# --- IA BLINDADA (MODELO LITE) ---
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    # Usamos el modelo resistente para alto volumen de redacción
    MODELO_IA = "models/gemini-2.0-flash-lite-preview-02-05"
else:
    MODELO_IA = None

# --- CEREBRO COPYWRITER ---

def generar_estrategia_prenido(prospecto, campana, analisis):
    """
    Genera el contenido de las DOS CAJAS (Valor + Pitch) usando 
    psicología de ventas adaptada al dolor específico.
    """
    if not MODELO_IA: return None

    # Extraemos datos clave
    nombre_cliente = prospecto.get('business_name', 'Emprendedor')
    rubro_cliente = analisis.get('industry', 'su sector')
    
    # Extraemos el dolor principal detectado por el Analista
    dolores = analisis.get('pain_points', [])
    dolor_principal = dolores[0] if dolores else "falta de optimización"
    
    # Extraemos datos de campaña
    producto = campana.get('product_description', 'Soluciones B2B')
    mision = campana.get('mission_statement', 'Ayudar a empresas')
    tono = campana.get('tone_voice', 'Profesional y Empático')

    try:
        model = genai.GenerativeModel(MODELO_IA)
        
        prompt = f"""
        ACTÚA COMO: Un Consultor de Negocios Senior y Copywriter de Respuesta Directa.
        TU OBJETIVO: Escribir un mensaje de "Pre-Nido" para {nombre_cliente} ({rubro_cliente}).
        
        CONTEXTO DE VENTA:
        - Vendemos: {producto}.
        - Nuestra Misión: {mision}.
        - El Dolor Detectado en el cliente: "{dolor_principal}".
        
        ESTRATEGIA PSICOLÓGICA (Usa una de estas según el dolor):
        1. Si es miedo/desconocimiento -> Usa "Autoridad" y "Simplificación".
        2. Si es dinero -> Usa "Inversión Irracional" o "Aversión a la Pérdida".
        3. Si es tiempo/estrés -> Usa "Principio de Mínima Resistencia".
        
        TU TAREA: Genera el contenido para DOS SECCIONES (JSON):
        
        SECCIÓN 1: "Oportunidad de Crecimiento" (Caja de Valor Gratuito)
        - NO VENDAS TU PRODUCTO AQUÍ.
        - Dale un consejo real, un "Tip", o una micro-solución gratis para su dolor "{dolor_principal}".
        - Demuestra que entiendes su problema mejor que ellos.
        
        SECCIÓN 2: "El Siguiente Nivel" (El Pitch del Diagnóstico)
        - Conecta el problema anterior con TU solución ({producto}).
        - Vende la "Demo Interactiva" o el "Diagnóstico Gratuito" como el paso lógico.
        - Usa un Gatillo Mental (Urgenta, Exclusividad o Curiosidad).
        
        ASUNTO DEL CORREO:
        - Debe ser corto (max 5 palabras), intrigante y tocar el dolor.
        
        FORMATO DE RESPUESTA (SOLO JSON):
        {{
            "asunto": "Asunto del correo",
            "caja_1_titulo": "Título para la sección de valor",
            "caja_1_contenido": "Texto de valor (consejo experto, empatía con el dolor)...",
            "caja_2_titulo": "El Siguiente Nivel: Un Diagnóstico Personalizado",
            "caja_2_contenido": "Texto persuasivo vendiendo el clic al diagnóstico...",
            "estrategia_usada": "Nombre de la estrategia psicológica aplicada"
        }}
        """
        
        respuesta = model.generate_content(prompt)
        texto_limpio = respuesta.text.replace("```json", "").replace("```", "").strip()
        return json.loads(texto_limpio)

    except Exception as e:
        logging.error(f"⚠️ Error generando copy IA: {e}")
        if "429" in str(e): raise e # Re-lanzar si es cuota para pausar
        return None

# --- SIMULACIÓN DE ENVÍO ---

def enviar_mensaje_multicanal(prospecto, contenido):
    """
    Simula el envío por el canal disponible (Email, Instagram, etc).
    Aquí se conectarían las APIs reales de Gmail/Twilio en el futuro.
    """
    canal = "Email"
    contacto = prospecto.get('captured_email')
    
    if not contacto:
        # Si no hay email, intentamos simular envío a red social
        perfiles = prospecto.get('social_profiles', {})
        if 'instagram' in str(perfiles):
            canal = "DM Instagram"
            contacto = perfiles.get('instagram')
        else:
            canal = "Desconocido"

    if canal == "Desconocido" or not contacto:
        logging.warning(f"📭 No hay canal de contacto válido para {prospecto.get('business_name')}")
        return False

    # AQUÍ OCURRIRÍA EL ENVÍO REAL
    logging.info(f"📨 ENVIANDO {canal} a {contacto} | Asunto: {contenido['asunto']}")
    logging.info(f"   > Caja 1: {contenido['caja_1_titulo']}")
    logging.info(f"   > Caja 2: {contenido['caja_2_titulo']}")
    return True

# --- CICLO DE TRABAJO ---

def trabajar_persuasor():
    logging.info(f"🎩 PERSUASOR ACTIVO (Modelo: {MODELO_IA})")
    
    while True:
        conn = None
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()

            # 1. BUSCAR PROSPECTOS 'analizado_exitoso'
            # Estos son los que el Analista ya filtró y encontró dolores.
            query = """
                SELECT 
                    p.id, p.business_name, p.captured_email, p.social_profiles, p.pain_points,
                    c.id as campaign_id, c.product_description, c.mission_statement, c.tone_voice
                FROM prospects p
                JOIN campaigns c ON p.campaign_id = c.id
                WHERE p.status = 'analizado_exitoso'
                LIMIT 3;
            """
            cur.execute(query)
            lote = cur.fetchall()

            if not lote:
                logging.info("💤 Sin prospectos calificados. Durmiendo 60s...")
                time.sleep(60)
                cur.close()
                conn.close()
                continue

            logging.info(f"💎 Procesando {len(lote)} prospectos calificados...")

            for fila in lote:
                pid, p_nombre, p_email, p_social, p_dolores, cid, c_prod, c_mision, c_tono = fila
                
                # Estructuras de datos
                prospecto_data = {
                    "business_name": p_nombre, 
                    "captured_email": p_email, 
                    "social_profiles": p_social
                }
                campana_data = {
                    "product_description": c_prod, 
                    "mission_statement": c_mision, 
                    "tone_voice": c_tono
                }
                analisis_data = p_dolores if p_dolores else {}

                # 2. GENERAR EL "PRE-NIDO" (El Mensaje Perfecto)
                try:
                    contenido_prenido = generar_estrategia_prenido(prospecto_data, campana_data, analisis_data)
                    
                    if contenido_prenido:
                        # 3. ENVIAR MENSAJE (Simulado)
                        enviado = enviar_mensaje_multicanal(prospecto_data, contenido_prenido)
                        
                        if enviado:
                            # 4. ACTUALIZAR DB
                            # Guardamos el JSON generado para mostrarlo en el Dashboard si hace falta
                            # Cambiamos estado a 'persuadido' (Intento realizado)
                            cur.execute("""
                                UPDATE prospects 
                                SET generated_copy = %s,
                                    status = 'persuadido',
                                    updated_at = NOW()
                                WHERE id = %s
                            """, (Json(contenido_prenido), pid))
                            conn.commit()
                            logging.info(f"✅ Persuasión ejecutada para: {p_nombre}")
                        else:
                            # Si no se pudo enviar por falta de datos, se marca como fallido
                            cur.execute("UPDATE prospects SET status = 'contacto_fallido' WHERE id = %s", (pid,))
                            conn.commit()
                    
                    else:
                        logging.warning(f"⚠️ IA devolvió vacío para {p_nombre}")

                except Exception as e_ia:
                    if "429" in str(e_ia):
                        logging.warning("🛑 Límite de IA (429). Durmiendo 45s...")
                        time.sleep(45)
                    else:
                        logging.error(f"Error en {p_nombre}: {e_ia}")

                time.sleep(3) # Pausa dramática entre correos

            cur.close()

        except Exception as e:
            logging.critical(f"🔥 Error Crítico Persuasor: {e}")
            time.sleep(30)
        finally:
            if conn: conn.close()

if __name__ == "__main__":
    trabajar_persuasor()
