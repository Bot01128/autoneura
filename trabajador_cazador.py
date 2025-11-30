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
logging.basicConfig(level=logging.INFO, format='%(asctime)s - ANALISTA - %(levelname)s - %(message)s')

DATABASE_URL = os.environ.get("DATABASE_URL")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

# --- SELECCIÓN DEL MODELO (BLINDADO PARA PRUEBAS) ---
# Seleccionamos la versión LITE de tu lista para evitar el Error 429
MODELO_IA = "models/gemini-2.0-flash-lite-preview-02-05" 

genai.configure(api_key=GOOGLE_API_KEY)

def analizar_prospecto(prospect_data):
    """
    Usa la IA para leer el JSON crudo del Cazador y extraer valor.
    """
    try:
        model = genai.GenerativeModel(MODELO_IA)
        
        # Prompt optimizado para modelos Lite (más directo)
        prompt = f"""
        Actúa como un Analista de Ventas Senior B2B.
        Analiza este prospecto crudo y extrae inteligencia estratégica.
        
        DATOS CRUDOS:
        {json.dumps(prospect_data)}
        
        TU MISIÓN:
        1. Determina el RUBRO exacto de la empresa.
        2. Detecta el IDIOMA principal.
        3. Resume sus PUNTOS DE DOLOR probables (basado en su rubro y reviews si hay).
        4. Califica del 1 al 10 qué tan buen lead es (SCORE).
        5. Sugiere un ÁNGULO DE VENTA (una frase corta para romper el hielo).

        Responde SOLO en formato JSON estrictamente válido con esta estructura:
        {{
            "industry": "Rubro",
            "language": "es/en",
            "pain_points": ["dolor1", "dolor2"],
            "lead_score": 8,
            "sales_angle": "frase de entrada",
            "summary": "resumen breve de 1 linea"
        }}
        """

        # Configuración para evitar bloqueos
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        
        return json.loads(response.text)

    except Exception as e:
        logging.error(f"⚠️ Error IA: {e}")
        return None

def ciclo_analista():
    logging.info(f"🧠 INICIANDO ANALISTA con modelo: {MODELO_IA}")
    
    while True:
        conn = None
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()

            # 1. Buscar prospectos 'cazados' (o 'espiados') que falten por analizar
            # Prioridad: Los más recientes para dar feedback rápido en el dashboard
            cur.execute("""
                SELECT id, raw_data, business_name 
                FROM prospects 
                WHERE status IN ('cazado', 'espiado') 
                AND analysis_data IS NULL
                ORDER BY created_at DESC
                LIMIT 1;
            """)
            
            row = cur.fetchone()
            
            if row:
                prospect_id, raw_data, nombre = row
                logging.info(f"🧐 Analizando a: {nombre} (ID: {prospect_id})...")
                
                # 2. Llamada a la IA
                analisis = analizar_prospecto(raw_data)
                
                if analisis:
                    # 3. Guardar resultados
                    cur.execute("""
                        UPDATE prospects 
                        SET analysis_data = %s, 
                            status = 'analizado',
                            updated_at = NOW()
                        WHERE id = %s;
                    """, (Json(analisis), prospect_id))
                    conn.commit()
                    logging.info(f"✅ Análisis guardado para {nombre}.")
                else:
                    # Si falla la IA, esperamos un poco y lo saltamos temporalmente (sin cambiar estado para reintentar luego)
                    logging.warning(f"⏩ Saltando {nombre} por fallo en IA.")
                    time.sleep(5) 

            else:
                logging.info("💤 Sin prospectos nuevos. Durmiendo...")
                time.sleep(30) # Espera larga si no hay trabajo

            cur.close()

        except Exception as e:
            logging.error(f"🔥 Error Crítico en ciclo: {e}")
            time.sleep(10)
        
        finally:
            if conn: conn.close()
            # Pausa de seguridad entre análisis para respetar el límite por minuto de Google
            time.sleep(6) 

if __name__ == "__main__":
    ciclo_analista()
