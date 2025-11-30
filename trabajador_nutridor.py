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

# IA BLINDADA (LITE para volumen, pero con instrucciones complejas)
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

        # Mapeo de Estrategias por Paso (La Escalera de Persuasión)
        estrategias = {
            1: "Reciprocidad y Autoridad (Aporte de Valor + Rompehielo)",
            2: "Efecto Zeigarnik y Curiosidad (Mostrar problema incompleto)",
            3: "Prueba Social y Efecto Bandwagon (Caso de Éxito)",
            4: "Manejo de Objeciones (Preocupaciones Financieras/Tiempo)",
            5: "Escasez y Urgencia (Oferta Limitada/Cupos)",
            6: "Downsell o Compromiso Menor (Simplificación de Elección)",
            7: "Aversión a la Pérdida y Despedida (Break-up Email)"
        }
        
        estrategia_actual = estrategias.get(paso_actual, "Aporte de Valor")
        
        prompt = f"""
        ERES: El Mejor Vendedor del Mundo (Estilo Jordan Belfort + Robert Cialdini).
        MISIÓN: Nutrir a un prospecto en el "Nido" (Dashboard de Ventas). Estamos en el MENSAJE {paso_actual} de 7.
        
        DATOS:
        - Cliente: {prospecto.get('business_name')} (Rubro: {analisis.get('industry')})
        - Dolor Principal: {analisis.get('pain_points', ['Necesidad General'])[0]}
        - Producto que vendemos: {campana.get('product_description')}
        - Tono: {campana.get('tone_voice')}
        
        ESTRATEGIA A APLICAR AHORA: "{estrategia_actual}"
        
        TU TAREA (Generar JSON):
        1. "mensaje_chat": El mensaje que el Chatbot le dirá proactivamente al cliente al entrar. Debe ser corto, conversacional y aplicar la estrategia.
        2. "contenido_valor": Un breve texto o 'tip' que demuestre experto (solo para pasos 1-3).
        3. "argumentario_defensa": (IMPORTANTE) Escribe 3 respuestas rápidas que el Chatbot debe tener listas si el cliente pone objeciones sobre Precio, Tiempo o Confianza en este momento.
        
        FORMATO JSON:
        {{
            "fase": {paso_actual},
            "estrategia_usada": "{estrategia_actual}",
            "mensaje_chat_bienvenida": "Hola [Nombre]...",
            "titulo_contenido_nido": "Título atractivo...",
            "texto_contenido_nido": "Cuerpo del contenido...",
            "script_objeciones": {{
                "si_dice_caro": "Respuesta usando re-encuadre de valor...",
                "si_dice_no_tengo_tiempo": "Respuesta usando simplicidad...",
                "si_dice_lo_pensare": "Respuesta usando urgencia..."
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
        Retorna: True (Puede trabajar), False (Detener servicio).
        """
        cur = self.conectar()
        if not cur: return False
        
        try:
            cur.execute("SELECT next_payment_date, is_active FROM clients WHERE id = %s", (client_id,))
            res = cur.fetchone()
            if not res: return False
            
            fecha_pago, activo = res
            
            # Si está activo, todo bien.
            if activo: return True
            
            # Si no está activo, verificamos la gracia de 5 días
            if fecha_pago:
                limite_gracia = fecha_pago + datetime.timedelta(days=5)
                if datetime.date.today() <= limite_gracia.date():
                    return True # En periodo de gracia
            
            return False # Se acabó la fiesta
            
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

            # 1. BUSCAR PROSPECTOS ACTIVOS EN EL NIDO ('nutriendo')
            # Recuperamos también el último paso y la fecha de última actualización
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
                
                # A. VERIFICAR SI EL CLIENTE PAGA (O TIENE GRACIA)
                if not self.verificar_permiso_cliente(client_id):
                    logging.warning(f"⛔ Cliente {client_id} sin saldo y fuera de gracia. Pausando prospecto {pid}.")
                    continue

                # B. DETERMINAR EL PASO ACTUAL (1 al 7)
                datos_nido = p_nido_json if p_nido_json else {}
                paso_actual = datos_nido.get("fase_actual", 0)
                
                # Lógica de Tiempo: Solo avanzamos si han pasado X días (ej: 2 días entre mensajes)
                # O si es el paso 0 (recién llegado)
                tiempo_desde_ultimo = (datetime.datetime.now() - p_ultimo_update).total_seconds()
                horas_espera = 48 # 2 días entre mensajes (ajustable)
                
                if paso_actual > 0 and tiempo_desde_ultimo < (horas_espera * 3600):
                    continue # Aún no toca el siguiente mensaje

                nuevo_paso = paso_actual + 1

                # C. SI YA PASAMOS EL PASO 7 -> GAME OVER (Lead Frío)
                if nuevo_paso > 7:
                    logging.info(f"❄️ Prospecto {p_nombre} agotó los 7 intentos. Marcando como Lead Frío.")
                    cur.execute("UPDATE prospects SET status = 'lead_frio' WHERE id = %s", (pid,))
                    conn.commit()
                    continue

                # D. GENERAR LA JUGADA (IA)
                logging.info(f"🧠 Generando JUGADA {nuevo_paso}/7 para {p_nombre}...")
                
                campana_data = {"product_description": c_prod, "tone_voice": c_tono}
                analisis_data = {"pain_points": p_dolores, "industry": "General"} # Simplificado

                try:
                    contenido_nuevo = self.generar_jugada_maestra(
                        {"business_name": p_nombre}, 
                        campana_data, 
                        analisis_data, 
                        nuevo_paso
                    )
                    
                    if contenido_nuevo:
                        # Actualizamos el JSON del Nido conservando historial si quisieramos, 
                        # pero aquí actualizamos la "Pantalla Actual" del Nido.
                        contenido_nuevo["fase_actual"] = nuevo_paso
                        
                        cur.execute("""
                            UPDATE prospects 
                            SET nido_data = %s, updated_at = NOW()
                            WHERE id = %s
                        """, (Json(contenido_nuevo), pid))
                        conn.commit()
                        logging.info(f"✅ Nido actualizado (Fase {nuevo_paso}) para {p_nombre}")
                        
                        # Pausa de seguridad IA
                        time.sleep(10)

                except Exception as e_ia:
                    if "429" in str(e_ia):
                        logging.warning("🛑 Nutridor en pausa por IA (429).")
                        time.sleep(60)
                        break # Salir del ciclo para esperar
                    logging.error(f"Error IA en {p_nombre}: {e_ia}")

            # 2. VERIFICAR INTERACCIONES PARA COBRAR (El Contador)
            # Buscamos prospectos que tengan >= 3 interacciones y aún no estén validados
            cur.execute("""
                UPDATE prospects 
                SET status = 'validado_facturable' 
                WHERE status = 'nutriendo' AND interactions_count >= 3
            """)
            if cur.rowcount > 0:
                conn.commit()
                logging.info(f"💰 Se han validado {cur.rowcount} nuevos prospectos facturables.")

            cur.close()

        except Exception as e:
            logging.error(f"🔥 Error Ciclo Nutridor: {e}")
        finally:
            if conn: conn.close()

if __name__ == "__main__":
    worker = TrabajadorNutridor()
    # Ejecutamos una vez al iniciar y luego el orquestador lo manejará
    worker.ejecutar_ciclo_seguimiento()
