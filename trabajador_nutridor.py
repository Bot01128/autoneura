import os
import time
import json
import logging
import datetime
import psycopg2
from psycopg2.extras import Json
import google.generativeai as genai
from dotenv import load_dotenv

# --- CONFIGURACIÓN ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - NUTRIDOR - %(levelname)s - %(message)s')

DATABASE_URL = os.environ.get("DATABASE_URL")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

# USAMOS EL MODELO LITE (Barato y Rápido)
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    MODELO_IA = "models/gemini-2.0-flash-lite-preview-02-05"
else:
    MODELO_IA = None

class TrabajadorNutridor:
    def __init__(self):
        self.conn = None

    def conectar(self):
        try:
            self.conn = psycopg2.connect(DATABASE_URL)
            return self.conn.cursor()
        except Exception as e:
            logging.error(f"Error DB: {e}")
            return None

    # --- CEREBRO PSICOLÓGICO (Generador de Jugadas) ---

    def generar_jugada_maestra(self, prospecto, campana, analisis, paso_actual):
        """
        Genera el contenido para el Nido basado en el Paso (1-7) 
        y aplica la estrategia psicológica correspondiente.
        """
        if not MODELO_IA: return None

        # LA ESCALERA DE PERSUASIÓN (Tus 20 Trucos aplicados)
        estrategias = {
            1: "Aporte de Valor + Reciprocidad (Regalar conocimiento sin pedir nada)",
            2: "Efecto Zeigarnik (Mostrar que su proceso está incompleto)",
            3: "Prueba Social (Caso de Éxito de industria similar)",
            4: "Manejo de Objeciones (Atacar Precio/Tiempo antes de que lo digan)",
            5: "Escasez y Urgencia (Cupos limitados o tiempo)",
            6: "Downsell o Compromiso Menor (Simplificación)",
            7: "Aversión a la Pérdida y Despedida (Break-up Email)"
        }
        
        estrategia_actual = estrategias.get(paso_actual, "Aporte de Valor")
        
        # PROMPT DE INGENIERÍA DE VENTAS
        prompt = f"""
        ERES: Un Estratega de Ventas B2B (Estilo Jordan Belfort).
        MISIÓN: Nutrir a un prospecto en el "Nido". Estamos en el MENSAJE {paso_actual} de 7.
        
        DATOS DEL PROSPECTO:
        - Nombre: {prospecto.get('business_name')}
        - Dolor Principal: {analisis.get('pain_points', ['Necesidad General'])[0]}
        
        DATOS DE NOSOTROS (CAMPAÑA):
        - Producto: {campana.get('product_description')}
        - Tono de Voz: {campana.get('tone_voice')}
        
        ESTRATEGIA OBLIGATORIA AHORA: "{estrategia_actual}"
        
        TU TAREA (Generar JSON):
        Crea el contenido que verá el cliente en su Dashboard ("Nido").
        1. "mensaje_chat": El mensaje PROACTIVO que el Chatbot enviará al abrir la web.
        2. "contenido_valor": Un consejo o dato útil relacionado con su dolor.
        3. "script_objeciones": 3 respuestas listas por si el cliente responde al chat.
        
        FORMATO JSON:
        {{
            "fase": {paso_actual},
            "estrategia_usada": "{estrategia_actual}",
            "mensaje_chat_bienvenida": "Hola [Nombre], encontré esto para ti...",
            "titulo_contenido_nido": "Título persuasivo...",
            "texto_contenido_nido": "Cuerpo del contenido (Max 100 palabras)...",
            "script_objeciones": {{
                "objecion_precio": "Respuesta usando re-encuadre...",
                "objecion_tiempo": "Respuesta usando simplicidad...",
                "objecion_confianza": "Respuesta usando prueba social..."
            }}
        }}
        """

        try:
            model = genai.GenerativeModel(MODELO_IA)
            res = model.generate_content(prompt)
            texto_limpio = res.text.replace("```json", "").replace("```", "").strip()
            return json.loads(texto_limpio)
        except Exception as e:
            logging.error(f"⚠️ Error IA Nutridor: {e}")
            if "429" in str(e): raise e 
            return None

    # --- GESTIÓN FINANCIERA (El cobrador amable) ---

    def verificar_permiso_cliente(self, client_id):
        """
        Verifica si el cliente pagó. Da 5 días de gracia.
        """
        cur = self.conectar()
        if not cur: return False
        
        try:
            cur.execute("SELECT next_payment_date, is_active FROM clients WHERE id = %s", (client_id,))
            res = cur.fetchone()
            if not res: return False
            
            fecha_pago, activo = res
            
            # Si está activo, pase adelante
            if activo: return True
            
            # Si no está activo, verificamos Gracia de 5 Días
            if fecha_pago:
                limite_gracia = fecha_pago + datetime.timedelta(days=5)
                hoy = datetime.date.today()
                
                if hoy <= limite_gracia:
                    logging.info(f"⚠️ Cliente {client_id} en PERIODO DE GRACIA (Vence: {limite_gracia})")
                    return True
                else:
                    # Se acabó la gracia. Despedida.
                    logging.warning(f"⛔ Cliente {client_id}: Periodo de gracia expirado.")
                    return False
            
            return False
            
        except Exception:
            return False
        finally:
            cur.close()
            if self.conn: self.conn.close()

    # --- MOTOR DE EJECUCIÓN ---

    def ejecutar_ciclo_seguimiento(self):
        logging.info("🏗️ NUTRIDOR: Iniciando ronda de mantenimiento del Nido...")
        
        conn = None
        try:
            conn = psycopg2.connect(DATABASE_URL)
            cur = conn.cursor()

            # 1. BUSCAR PROSPECTOS EN 'NUTRIENDO'
            # (Aquellos que ya dejaron su email en el Pre-Nido)
            cur.execute("""
                SELECT 
                    p.id, p.business_name, p.pain_points, p.nido_data, p.updated_at,
                    c.id as campaign_id, c.client_id, c.product_description, c.tone_voice
                FROM prospects p
                JOIN campaigns c ON p.campaign_id = c.id
                WHERE p.status = 'nutriendo'
            """)
            
            prospectos = cur.fetchall()
            
            for fila in prospectos:
                pid, p_nombre, p_dolores, p_nido_json, p_ultimo_update, cid, client_id, c_prod, c_tono = fila
                
                # A. VERIFICAR PAGOS (Regla de los 5 días)
                if not self.verificar_permiso_cliente(client_id):
                    continue # Cliente moroso, no trabajamos para él.

                # B. DETERMINAR EL PASO ACTUAL (1 al 7)
                datos_nido = p_nido_json if p_nido_json else {}
                paso_actual = datos_nido.get("fase", 0)
                
                # C. CONTROL DE TIEMPO (No spamear)
                # Esperamos 48 horas entre mensajes, excepto el primero (paso 0)
                if p_ultimo_update:
                    horas_pasadas = (datetime.datetime.now() - p_ultimo_update).total_seconds() / 3600
                    if paso_actual > 0 and horas_pasadas < 48:
                        continue # Aún no toca
                
                nuevo_paso = paso_actual + 1

                # D. REGLA DE SALIDA: Si ya pasó el 7, es Lead Frío
                if nuevo_paso > 7:
                    logging.info(f"❄️ Prospecto {p_nombre} sin respuesta tras 7 intentos. Lead Frío.")
                    cur.execute("UPDATE prospects SET status = 'lead_frio' WHERE id = %s", (pid,))
                    conn.commit()
                    continue

                # E. GENERAR JUGADA CON IA
                logging.info(f"🧠 Generando JUGADA {nuevo_paso}/7 para {p_nombre}...")
                
                campana_data = {"product_description": c_prod, "tone_voice": c_tono}
                analisis_data = {"pain_points": p_dolores}

                try:
                    contenido_nuevo = self.generar_jugada_maestra(
                        {"business_name": p_nombre}, 
                        campana_data, 
                        analisis_data, 
                        nuevo_paso
                    )
                    
                    if contenido_nuevo:
                        # Guardamos en DB
                        cur.execute("""
                            UPDATE prospects 
                            SET nido_data = %s, updated_at = NOW()
                            WHERE id = %s
                        """, (Json(contenido_nuevo), pid))
                        conn.commit()
                        logging.info(f"✅ Nido actualizado (Fase {nuevo_paso}) para {p_nombre}")
                        
                        # Pausa para no saturar Google (Anti-429)
                        time.sleep(10)

                except Exception as e_ia:
                    if "429" in str(e_ia):
                        logging.warning("🛑 Pausa por Límite IA (429).")
                        time.sleep(60)
                        break 
                    logging.error(f"Error IA en {p_nombre}: {e_ia}")

            # 2. VERIFICAR INTERACCIONES (FACTURACIÓN)
            # Si el cliente interactuó 3 veces, marcamos como "Validado" para cobrar.
            cur.execute("""
                UPDATE prospects 
                SET status = 'validado_facturable' 
                WHERE status = 'nutriendo' AND interactions_count >= 3
            """)
            if cur.rowcount > 0:
                conn.commit()
                logging.info(f"💰 ¡CA-CHING! {cur.rowcount} prospectos validados para facturación.")

            cur.close()

        except Exception as e:
            logging.error(f"🔥 Error Ciclo Nutridor: {e}")
        finally:
            if conn: conn.close()

if __name__ == "__main__":
    worker = TrabajadorNutridor()
    # Esto se ejecutará en bucle cuando lo llame el Orquestador
    worker.ejecutar_ciclo_seguimiento()
