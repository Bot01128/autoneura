import os
import json
import logging
import psycopg2
from psycopg2.extras import Json
import google.generativeai as genai
from datetime import datetime, timedelta
from dotenv import load_dotenv

# --- CONFIGURACIÓN ---
load_dotenv()

# Configuración de Logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - NUTRIDOR - %(levelname)s - %(message)s')

# Credenciales
DATABASE_URL = os.environ.get("DATABASE_URL")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

# Configuración IA
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
else:
    logging.critical("GOOGLE_API_KEY faltante. El Nutridor está lobotomizado.")

# --- ARGUMENTARIOS DE VENTA (BASE DE CONOCIMIENTO RAG) ---
# Estos son los guiones de clase mundial que el Nutridor usará en el Chat.
ARGUMENTARIOS = {
    "OBJECION_DESCONOCIDO": """
    Argumento: Asesoría Integral desde el Día Cero.
    Enfoque: No necesita ser experto. Tendrá un Gerente de Proyecto dedicado. Explicamos cada fase en lenguaje claro.
    Herramienta: Simulaciones y Recorridos Virtuales para eliminar la incertidumbre visual antes de construir.
    """,
    "OBJECION_FINANCIERA": """
    Argumento: Presupuesto Cerrado, Sin Sorpresas.
    Enfoque: Entregamos presupuesto minucioso antes de firmar. Garantía de precio fijo.
    Opciones: Gestionamos opciones de financiamiento.
    Visión a largo plazo: Es una inversión para el patrimonio de hijos y nietos. Alquilar es más caro a la larga.
    """,
    "OBJECION_ESTRES_TIEMPO": """
    Argumento: Gestión Llave en Mano.
    Enfoque: Nosotros somos el director de orquesta, usted disfruta el concierto.
    Beneficio: Un solo punto de contacto. Nosotros lidiamos con burocracia y permisos. Su tiempo es oro.
    """,
    "OBJECION_DESCONFIANZA_RETRASOS": """
    Argumento: Cronograma Garantizado con Penalización.
    Enfoque: Planificación rigurosa. Si nos retrasamos por nuestra culpa, pagamos una penalización.
    Tecnología: Monitoreo avanzado en tiempo real.
    """
}

class TrabajadorNutridor:
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-2.5-flash') if GOOGLE_API_KEY else None

    def conectar_db(self):
        return psycopg2.connect(DATABASE_URL)

    # ==========================================
    # PARTE 1: EL CEREBRO DEL CHAT (NIDO)
    # ==========================================
    
    def procesar_mensaje_chat(self, prospecto_id, mensaje_usuario):
        """
        Analiza la intención, busca el argumento correcto y responde o alerta al humano.
        """
        conn = self.conectar_db()
        cur = conn.cursor()
        
        try:
            # 1. Obtener contexto del prospecto
            cur.execute("""
                SELECT p.business_name, p.pain_points, c.product_description, c.campaign_name 
                FROM prospects p
                JOIN campaigns c ON p.campaign_id = c.id
                WHERE p.id = %s
            """, (prospecto_id,))
            data = cur.fetchone()
            
            if not data: return "Error: No te encuentro en mi base de datos."
            
            nombre_negocio, pain_points, producto, nombre_campana = data
            
            # 2. Análisis de Intención y Sentimiento (IA)
            prompt_analisis = f"""
            Eres el "Psicólogo de Ventas" de AutoNeura. Analiza este mensaje del cliente: "{mensaje_usuario}"
            
            Identifica:
            1. INTENCION: ¿Es una duda, una objeción o una señal de compra?
            2. CATEGORIA_OBJECION: Si es objeción, clasifícala en: [FINANCIERA, DESCONOCIDO, TIEMPO, DESCONFIANZA, OTRA].
            3. TRIGGER_HUMANO: ¿Pide hablar con alguien, cotización o llamada? (SI/NO).
            
            Responde SOLO en formato JSON: {{"intencion": "...", "categoria": "...", "trigger": "..."}}
            """
            res_analisis = self.model.generate_content(prompt_analisis)
            analisis = json.loads(res_analisis.text.replace("```json", "").replace("```", "").strip())
            
            # 3. Lógica de Trigger Humano
            if analisis.get("trigger") == "SI":
                # Notificar al humano (En un sistema real, enviar email/whatsapp al dueño)
                cur.execute("UPDATE prospects SET status = 'alerta_humana' WHERE id = %s", (prospecto_id,))
                conn.commit()
                return "¡Entendido! He notificado a un especialista humano. Te contactará en breve para darte esa información detallada."

            # 4. Recuperación de Conocimiento (RAG Simplificado)
            argumento_base = ""
            cat = analisis.get("categoria", "")
            
            if cat == "FINANCIERA": argumento_base = ARGUMENTARIOS["OBJECION_FINANCIERA"]
            elif cat == "DESCONOCIDO": argumento_base = ARGUMENTARIOS["OBJECION_DESCONOCIDO"]
            elif cat == "TIEMPO": argumento_base = ARGUMENTARIOS["OBJECION_ESTRES_TIEMPO"]
            elif cat == "DESCONFIANZA": argumento_base = ARGUMENTARIOS["OBJECION_DESCONFIANZA_RETRASOS"]
            else: argumento_base = "Responde de forma general sobre los beneficios de: " + producto

            # 5. Generación de Respuesta Empática
            prompt_respuesta = f"""
            ACTÚA COMO: Un experto consultor de ventas para {nombre_negocio}.
            PRODUCTO: {producto}.
            CONTEXTO: El cliente dijo "{mensaje_usuario}".
            
            TU ARMA SECRETA (Argumentario a usar): 
            {argumento_base}
            
            INSTRUCCIONES:
            - No copies el argumento. Úsalo para inspirar tu respuesta.
            - Sé empático. Valida su preocupación primero ("Entiendo perfectamente...").
            - Sé breve y conversacional.
            - Termina con una pregunta que invite a seguir hablando.
            """
            
            respuesta_final = self.model.generate_content(prompt_respuesta).text.strip()
            
            # Registrar interacción
            cur.execute("UPDATE prospects SET interactions_count = interactions_count + 1, last_interaction_at = NOW() WHERE id = %s", (prospecto_id,))
            conn.commit()
            
            return respuesta_final

        except Exception as e:
            logging.error(f"Error en Chat Nutridor: {e}")
            return "Estoy teniendo un pequeño lapso de memoria. ¿Podrías repetirme eso?"
        finally:
            cur.close()
            conn.close()

    # ==========================================
    # PARTE 2: EL MOTOR DE SEGUIMIENTO (EMAIL)
    # ==========================================

    def generar_email_seguimiento(self, etapa, prospecto, producto):
        """Genera el contenido del email usando IA + Contexto."""
        nombre = prospecto['business_name']
        dolores = prospecto.get('pain_points', {}).get('puntos_de_dolor', [])
        
        prompt = ""
        if etapa == "VALOR":
            prompt = f"""
            Escribe un email corto para {nombre}. 
            CONTEXTO: Hace 3 días vieron nuestro diagnóstico.
            MISIÓN: Aportar valor GRATIS. Inventa que encontraste un artículo relevante sobre su industria y resume un tip clave.
            TONO: "Pensé en ti". Cero venta.
            """
        elif etapa == "PRUEBA_SOCIAL":
            prompt = f"""
            Escribe un email para {nombre}.
            CONTEXTO: Hace una semana hablamos.
            MISIÓN: Contar un caso de éxito anónimo de una empresa similar que logró resultados con {producto}.
            TONO: Inspirador.
            """
        elif etapa == "DESPEDIDA":
            prompt = f"""
            Escribe un 'Break-up Email' para {nombre}.
            CONTEXTO: No han respondido en 2 semanas.
            MISIÓN: Preguntar si cerrar el archivo. Quitarles la presión.
            TONO: Profesional y amable.
            """
            
        return self.model.generate_content(prompt).text.strip()

    def procesar_seguimientos(self):
        """
        Revisa la DB y ejecuta las jugadas de ajedrez según el tiempo transcurrido.
        """
        conn = self.conectar_db()
        cur = conn.cursor()

        try:
            logging.info("♟️ Iniciando ronda de Ajedrez (Seguimientos)...")

            # --- JUGADA 1: APORTE DE VALOR (3-4 días) ---
            cur.execute("""
                SELECT p.id, p.business_name, p.pain_points, c.product_description 
                FROM prospects p JOIN campaigns c ON p.campaign_id = c.id
                WHERE p.status = 'nutriendo' AND p.last_interaction_at < NOW() - INTERVAL '3 DAYS'
            """)
            lote_1 = cur.fetchall()
            for row in lote_1:
                pid, nombre, pain, prod = row
                email_body = self.generar_email_seguimiento("VALOR", {'business_name': nombre, 'pain_points': pain}, prod)
                
                # Guardar borrador para envío (o enviar directamente)
                cur.execute("UPDATE prospects SET draft_message = %s, status = 'en_nutricion_1', last_interaction_at = NOW() WHERE id = %s", (email_body, pid))
                logging.info(f"📧 Jugada 1 (Valor) preparada para {nombre}")

            # --- JUGADA 2: PRUEBA SOCIAL (7-10 días) ---
            cur.execute("""
                SELECT p.id, p.business_name, p.pain_points, c.product_description 
                FROM prospects p JOIN campaigns c ON p.campaign_id = c.id
                WHERE p.status = 'en_nutricion_1' AND p.last_interaction_at < NOW() - INTERVAL '7 DAYS'
            """)
            lote_2 = cur.fetchall()
            for row in lote_2:
                pid, nombre, pain, prod = row
                email_body = self.generar_email_seguimiento("PRUEBA_SOCIAL", {'business_name': nombre, 'pain_points': pain}, prod)
                
                cur.execute("UPDATE prospects SET draft_message = %s, status = 'en_nutricion_2', last_interaction_at = NOW() WHERE id = %s", (email_body, pid))
                logging.info(f"📧 Jugada 2 (Social) preparada para {nombre}")

            # --- JUGADA 3: DESPEDIDA (15 días) ---
            cur.execute("""
                SELECT p.id, p.business_name, p.pain_points, c.product_description 
                FROM prospects p JOIN campaigns c ON p.campaign_id = c.id
                WHERE p.status = 'en_nutricion_2' AND p.last_interaction_at < NOW() - INTERVAL '15 DAYS'
            """)
            lote_3 = cur.fetchall()
            for row in lote_3:
                pid, nombre, pain, prod = row
                email_body = self.generar_email_seguimiento("DESPEDIDA", {'business_name': nombre, 'pain_points': pain}, prod)
                
                # Aquí marcamos como lead frío si no responde a este último
                cur.execute("UPDATE prospects SET draft_message = %s, status = 'lead_frio', last_interaction_at = NOW() WHERE id = %s", (email_body, pid))
                logging.info(f"📧 Jugada 3 (Jaque Mate/Despedida) preparada para {nombre}")

            conn.commit()

        except Exception as e:
            logging.error(f"Error crítico en Nutridor: {e}")
            if conn: conn.rollback()
        finally:
            cur.close()
            conn.close()

if __name__ == "__main__":
    # Prueba manual del ciclo de seguimiento
    nutridor = TrabajadorNutridor()
    nutridor.procesar_seguimientos()
