import os
import json
import logging
import psycopg2
from psycopg2.extras import Json
import google.generativeai as genai
from dotenv import load_dotenv

# --- CONFIGURACIÓN DE ENTORNO ---
load_dotenv()

# Configuración de Logs
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - PERSUASOR - %(levelname)s - %(message)s'
)

# Credenciales
DATABASE_URL = os.environ.get("DATABASE_URL")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
# URL base para los links (Ajústala si tu dominio cambia)
BASE_APP_URL = os.environ.get("APP_URL", "https://autoneura-production.up.railway.app") 

# Configuración de IA
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
else:
    logging.critical("GOOGLE_API_KEY no encontrada. El Persuasor no puede funcionar sin cerebro.")

# --- AQUÍ ESTÁ LA CLASE QUE EL ORQUESTADOR BUSCABA ---
class TrabajadorPersuasor:
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-1.5-flash') if GOOGLE_API_KEY else None

    def conectar_db(self):
        return psycopg2.connect(DATABASE_URL)

    def construir_prompt_maestro(self, prospecto, campana, link_prenido):
        """Construye el Prompt de Ingeniería para la IA."""
        nombre_negocio = prospecto['business_name']
        puntos_dolor = prospecto.get('pain_points', {}).get('puntos_de_dolor', [])
        
        nombre_cliente = campana.get('client_name', 'El Equipo de Expertos')
        nombre_campana = campana['campaign_name']
        que_vende = campana['product_description']
        
        lista_dolores_txt = "\n".join([f"- {d}" for d in puntos_dolor]) if puntos_dolor else "- Oportunidades de mejora general en digitalización."

        prompt = f"""
        ACTÚA COMO: {nombre_cliente}, experto en {nombre_campana}.
        MISIÓN: Escribir mensaje de contacto para "{nombre_negocio}".
        
        CONTEXTO (DOLORES DETECTADOS):
        {lista_dolores_txt}
        
        SOLUCIÓN: {que_vende}
        
        INSTRUCCIONES:
        1. Rompehielo empático.
        2. Menciona sutilmente los dolores.
        3. Ofrece la solución.
        4. LLAMADO A LA ACCIÓN (OBLIGATORIO): "Ver diagnóstico gratuito aquí: {link_prenido}"
        
        FORMATO: Breve, profesional, persuasivo. Solo el cuerpo del mensaje.
        """
        return prompt

    def generar_mensaje_ia(self, prompt):
        try:
            if not self.model: return "Error: IA no disponible."
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            logging.error(f"Error IA: {e}")
            return None

    def procesar_lote(self):
        conn = self.conectar_db()
        cur = conn.cursor()

        try:
            # Buscar prospectos listos para persuadir
            query = """
                SELECT 
                    p.id, p.business_name, p.pain_points, p.unique_access_token,
                    c.campaign_name, c.product_description, cl.full_name
                FROM prospects p
                JOIN campaigns c ON p.campaign_id = c.id
                JOIN clients cl ON c.client_id = cl.id
                WHERE p.status = 'analizado_exitoso'
                LIMIT 5
            """
            cur.execute(query)
            lote = cur.fetchall()

            if not lote:
                logging.info("💤 Persuasor: No hay prospectos analizados para contactar.")
                return

            for row in lote:
                pid, p_nombre, p_puntos, p_token, c_nombre, c_desc, cl_nombre = row
                
                prospecto = {'business_name': p_nombre, 'pain_points': p_puntos if p_puntos else {}}
                campana = {'campaign_name': c_nombre, 'product_description': c_desc, 'client_name': cl_nombre}
                
                # Generar Link y Mensaje
                link = f"{BASE_APP_URL}/pre-nido/{p_token}"
                prompt = self.construir_prompt_maestro(prospecto, campana, link)
                borrador = self.generar_mensaje_ia(prompt)

                if borrador:
                    # Guardar y avanzar estado
                    cur.execute("""
                        UPDATE prospects 
                        SET draft_message = %s, status = 'persuadido_listo_para_revision'
                        WHERE id = %s
                    """, (borrador, pid))
                    logging.info(f"💎 Mensaje generado para {p_nombre}")

            conn.commit()

        except Exception as e:
            logging.error(f"Error Persuasor: {e}")
            if conn: conn.rollback()
        finally:
            cur.close()
            conn.close()

if __name__ == "__main__":
    worker = TrabajadorPersuasor()
    worker.procesar_lote()
