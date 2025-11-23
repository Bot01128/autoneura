import os
import json
import logging
import psycopg2
from psycopg2.extras import Json
import google.generativeai as genai
from dotenv import load_dotenv

# --- CONFIGURACIÓN DE ENTORNO ---
load_dotenv()

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - PERSUASOR - %(levelname)s - %(message)s'
)

DATABASE_URL = os.environ.get("DATABASE_URL")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
# Asegúrate que esta URL no tenga barra al final
BASE_APP_URL = os.environ.get("APP_URL", "https://autoneura-production.up.railway.app") 

if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

class TrabajadorPersuasor:
    def __init__(self):
        # Usamos el modelo 2.5-flash que ya sabemos que funciona
        self.model = genai.GenerativeModel('gemini-2.5-flash') if GOOGLE_API_KEY else None

    def conectar_db(self):
        return psycopg2.connect(DATABASE_URL)

    def construir_prompt_maestro(self, prospecto, campana):
        """
        Construye el Prompt SOLO para el texto persuasivo.
        EL ENLACE YA NO SE LE DA A LA IA PARA QUE NO LO ROMPA.
        """
        nombre_negocio = prospecto['business_name']
        puntos_dolor = prospecto.get('pain_points', {}).get('puntos_de_dolor', [])
        
        nombre_cliente = campana.get('client_name', 'El Equipo de Expertos')
        nombre_campana = campana['campaign_name']
        que_vende = campana['product_description']
        
        lista_dolores_txt = "\n".join([f"- {d}" for d in puntos_dolor]) if puntos_dolor else "- Oportunidades de mejora general."

        prompt = f"""
        ACTÚA COMO: {nombre_cliente}, experto en {nombre_campana}.
        MISIÓN: Escribir el cuerpo de un correo para "{nombre_negocio}".
        
        CONTEXTO (DOLORES):
        {lista_dolores_txt}
        
        SOLUCIÓN: {que_vende}
        
        INSTRUCCIONES:
        1. Escribe un saludo personalizado y amable.
        2. Menciona sutilmente los problemas detectados y cómo podemos ayudar.
        3. Termina invitando a ver un diagnóstico gratuito que preparamos.
        4. IMPORTANTE: NO escribas el enlace ni URL. Solo di "puedes verlo aquí" o similar. Yo pegaré el enlace después.
        
        FORMATO: Breve (max 150 palabras). Solo el texto del correo.
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
            # Buscar prospectos que devolvimos a 'analizado_exitoso'
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
                logging.info("💤 Persuasor: Nada nuevo por aquí.")
                return

            for row in lote:
                pid, p_nombre, p_puntos, p_token, c_nombre, c_desc, cl_nombre = row
                
                prospecto = {'business_name': p_nombre, 'pain_points': p_puntos if p_puntos else {}}
                campana = {'campaign_name': c_nombre, 'product_description': c_desc, 'client_name': cl_nombre}
                
                # 1. Generamos solo el texto con IA
                prompt = self.construir_prompt_maestro(prospecto, campana)
                cuerpo_mensaje = self.generar_mensaje_ia(prompt)

                if cuerpo_mensaje:
                    # 2. CONSTRUIMOS EL ENLACE NOSOTROS (PYTHON) PARA QUE SEA PERFECTO
                    link_perfecto = f"{BASE_APP_URL}/pre-nido/{str(p_token)}"
                    
                    # 3. Unimos todo
                    mensaje_final = f"{cuerpo_mensaje}\n\n👉 Ver diagnóstico gratuito aquí: {link_perfecto}"

                    # Guardar
                    cur.execute("""
                        UPDATE prospects 
                        SET draft_message = %s, status = 'persuadido_listo_para_revision'
                        WHERE id = %s
                    """, (mensaje_final, pid))
                    logging.info(f"💎 Mensaje BLINDADO generado para {p_nombre}")

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
