import os
import time
import json
import logging
import psycopg2
import random
from datetime import datetime, timedelta
from psycopg2.extras import Json
from dotenv import load_dotenv

# --- CONEXIÓN AL CEREBRO ROTATIVO ---
try:
    from ai_manager import brain
except ImportError:
    brain = None
    print("⚠️ ADVERTENCIA: ai_manager.py no encontrado. El Orquestador será menos inteligente.")

# --- IMPORTACIÓN DE TUS EMPLEADOS (LOS TRABAJADORES) ---
try:
    # Trabajadores tipo "Función Única"
    from trabajador_cazador import ejecutar_caza
    from trabajador_espia import ejecutar_espia
    
    # Trabajadores tipo "Procesamiento Lotes"
    from trabajador_analista import trabajar_analista
    from trabajador_persuasor import trabajar_persuasor
    
    # Trabajador tipo "Clase"
    from trabajador_nutridor import TrabajadorNutridor
except ImportError as e:
    print(f"!!! ERROR CRÍTICO DE INICIO: Faltan archivos de trabajadores. Detalle: {e}")

# --- CONFIGURACIÓN ---
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - ORQUESTADOR (CEO) - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("sistema_autoneura.log"),
        logging.StreamHandler()
    ]
)

DATABASE_URL = os.environ.get("DATABASE_URL")

class OrquestadorSupremo:
    def __init__(self):
        # Inicializamos al Nutridor
        self.nutridor = TrabajadorNutridor()
        
    def conectar_db(self):
        return psycopg2.connect(DATABASE_URL)

    # ==============================================================================
    # 💰 MÓDULO 1: DEPARTAMENTO FINANCIERO (INTACTO)
    # ==============================================================================

    def gestionar_finanzas_clientes(self):
        """Revisa pagos, envía alertas y corta el servicio a morosos."""
        logging.info("💼 Revisando estado de cuentas y pagos...")
        conn = self.conectar_db()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                SELECT id, email, full_name, next_payment_date 
                FROM clients 
                WHERE is_active = TRUE 
                AND next_payment_date BETWEEN NOW() AND NOW() + INTERVAL '3 DAYS'
                AND payment_alert_sent = FALSE
            """)
            for c in cur.fetchall():
                self.enviar_notificacion(c[1], "Tu suscripción vence pronto", f"Hola {c[2]}, recuerda recargar.")
                cur.execute("UPDATE clients SET payment_alert_sent = TRUE WHERE id = %s", (c[0],))

            cur.execute("""
                SELECT id, email, balance, plan_cost 
                FROM clients 
                WHERE is_active = TRUE AND next_payment_date <= NOW()
            """)
            for c in cur.fetchall():
                cid, email, saldo, costo = c or (0, "", 0, 0)
                costo = costo or 0
                
                if saldo and saldo >= costo:
                    nuevo_saldo = saldo - costo
                    cur.execute("""
                        UPDATE clients 
                        SET balance = %s, next_payment_date = next_payment_date + INTERVAL '30 DAYS', payment_alert_sent = FALSE 
                        WHERE id = %s
                    """, (nuevo_saldo, cid))
                    logging.info(f"✅ Cobro exitoso: Cliente {cid}. Nuevo ciclo iniciado.")
                elif costo > 0:
                    cur.execute("UPDATE clients SET is_active = FALSE, status = 'suspended_payment_fail' WHERE id = %s", (cid,))
                    self.enviar_notificacion(email, "Servicio Suspendido", "No tienes saldo suficiente.")
                    logging.warning(f"⛔ Cliente {cid} suspendido por falta de fondos.")

            conn.commit()

        except Exception as e:
            logging.error(f"Error crítico en finanzas: {e}")
            conn.rollback()
        finally:
            cur.close()
            conn.close()

    # ==============================================================================
    # 🧠 MÓDULO 2: ESTRATEGIA Y GOBERNADOR
    # ==============================================================================

    def obtener_arsenal_disponible(self):
        conn = self.conectar_db()
        cur = conn.cursor()
        try:
            cur.execute("SELECT DISTINCT platform FROM bot_arsenal WHERE is_active = TRUE")
            rows = cur.fetchall()
            return [r[0] for r in rows] if rows else ["Google Maps"]
        except Exception as e:
            logging.error(f"⚠️ Error leyendo Arsenal: {e}")
            return ["Google Maps"] 
        finally:
            cur.close()
            conn.close()

    def verificar_salud_global_ia(self):
        """
        EL GOBERNADOR: Revisa si tenemos capacidad de IA antes de arrancar una campaña.
        """
        if not brain: return False 
        
        try:
            # Intentamos obtener un modelo de prueba
            brain._find_available_key("general", "FREE") 
            return True
        except Exception:
            logging.warning("🛑 GOBERNADOR: Alerta de capacidad. Todas las IAs están ocupadas o agotadas.")
            return False

    def planificar_estrategia_caza(self, descripcion_producto, audiencia_objetivo, tipo_producto):
        plataformas_disponibles = self.obtener_arsenal_disponible()
        platform_default = plataformas_disponibles[0] if plataformas_disponibles else "Google Maps"
        query_default = audiencia_objetivo

        if not brain: return query_default, platform_default

        model_id = None
        try:
            model, model_id = brain.get_optimal_model(task_type="inteligencia")
            prompt = f"""
            Eres Director de Estrategia. ARSENAL: {json.dumps(plataformas_disponibles)}
            CLIENTE: {descripcion_producto}, {audiencia_objetivo}, {tipo_producto}
            MISIÓN: 1. Elegir MEJOR plataforma. 2. Redactar Query.
            Responde JSON: {{"query": "...", "platform": "..."}}
            """
            res = model.generate_content(prompt)
            brain.register_usage(model_id)
            texto_limpio = res.text.replace("```json", "").replace("```", "").strip()
            data = json.loads(texto_limpio)
            
            platform_elegida = data.get("platform", platform_default)
            if platform_elegida not in plataformas_disponibles: platform_elegida = platform_default

            logging.info(f"💡 ESTRATEGIA IA: Usar {platform_elegida} para buscar '{data.get('query')}'")
            return data.get("query", query_default), platform_elegida

        except Exception as e:
            logging.error(f"⚠️ Fallo estrategia IA: {e}")
            if model_id and "429" in str(e): brain.report_failure(model_id)
            return query_default, platform_default

    # ==============================================================================
    # ⚙️ MÓDULO 3: COORDINACIÓN DE TRABAJADORES (LA CADENA DE MONTAJE)
    # ==============================================================================

    def ejecutar_campana_secuencial(self, campana):
        """
        Ejecuta TODOS los trabajadores en orden para UNA sola campaña.
        """
        # Desempacamos TODAS las variables, incluyendo ubicacion
        camp_id, nombre, prod, audiencia, tipo_prod, limite_diario, ubicacion = campana
        if not limite_diario: limite_diario = 4

        logging.info(f"🎬 --- INICIANDO SECUENCIA PARA: {nombre} ---")

        # 1. EL CAZADOR (Trae la materia prima)
        # Verificamos si ya cumplió la meta de hoy antes de mandarlo a trabajar
        conn = self.conectar_db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM prospects WHERE campaign_id = %s AND created_at::date = CURRENT_DATE AND status = 'cazado'", (camp_id,))
        cazados_hoy = cur.fetchone()[0]
        cur.close()
        conn.close()

        if cazados_hoy < limite_diario:
            logging.info(f"🔫 1. ACTIVANDO CAZADOR ({cazados_hoy}/{limite_diario})")
            query_opt, plat = self.planificar_estrategia_caza(prod, audiencia, tipo_prod)
            
            # --- CORRECCIÓN CRÍTICA AQUI: usamos 'ubicacion' en vez de 'ubic' ---
            ejecutar_caza(camp_id, query_opt, ubicacion, plat, "Variable", limite_diario)
            # --------------------------------------------------------------------
        else:
            logging.info(f"✅ Meta de caza cumplida hoy para {nombre}.")

        # 2. EL ESPÍA (Enriquece datos)
        logging.info("🕵️ 2. ACTIVANDO ESPÍA")
        ejecutar_espia(camp_id, limite_diario)

        # 3. EL ANALISTA (Filtra calidad)
        logging.info("🧠 3. ACTIVANDO ANALISTA")
        try:
            trabajar_analista() # Se asume que procesa un lote y retorna
        except Exception as e:
            logging.error(f"Error Analista: {e}")

        # 4. EL PERSUASOR (Escribe correos)
        logging.info("🎩 4. ACTIVANDO PERSUASOR")
        try:
            trabajar_persuasor() # Se asume que procesa un lote y retorna
        except Exception as e:
            logging.error(f"Error Persuasor: {e}")

        # 5. EL NUTRIDOR (Chat y Seguimiento)
        logging.info("🌱 5. ACTIVANDO NUTRIDOR")
        try:
            self.nutridor.ejecutar_ciclo_seguimiento()
        except Exception as e:
            logging.error(f"Error Nutridor: {e}")

        logging.info(f"🏁 --- FIN SECUENCIA PARA: {nombre} ---")


    def coordinar_operaciones_diarias(self):
        """
        CONTROLADOR DE TRÁFICO: Distribuye las campañas en el tiempo disponible.
        """
        conn = self.conectar_db()
        cur = conn.cursor()
        
        try:
            # A. Obtener Campañas
            cur.execute("""
                SELECT c.id, c.campaign_name, c.product_description, c.target_audience, 
                       c.product_type, c.daily_prospects_limit, c.geo_location
                FROM campaigns c
                JOIN clients cl ON c.client_id = cl.id
                WHERE c.status = 'active' AND cl.is_active = TRUE
            """)
            campanas = cur.fetchall()
            
            if not campanas:
                logging.info("💤 No hay campañas activas.")
                return

            # B. Cálculos de Tiempo (Balanceo de Carga)
            total_campanas = len(campanas)
            
            logging.info(f"🚦 CONTROLADOR DE TRÁFICO: {total_campanas} campañas en cola.")

            for campana in campanas:
                # 1. GOBERNADOR: ¿Hay cupo de IA Global?
                if not self.verificar_salud_global_ia():
                    logging.warning("🛑 GOBERNADOR: Frenando operaciones por falta de IA. Reintentando más tarde.")
                    break 

                # 2. EJECUCIÓN SECUENCIAL
                self.ejecutar_campana_secuencial(campana)
                
                # 3. Respiro entre campañas
                tiempo_respiro = 30 
                if total_campanas > 10: tiempo_respiro = 10 
                
                logging.info(f"⏳ Respirando {tiempo_respiro}s antes de la siguiente campaña...")
                time.sleep(tiempo_respiro)

        except Exception as e:
            logging.error(f"Error en coordinación operaciones: {e}")
        finally:
            cur.close()
            conn.close()

    # ==============================================================================
    # 📨 MÓDULO 4: REPORTES (INTACTO)
    # ==============================================================================

    def enviar_notificacion(self, email, asunto, mensaje):
        logging.info(f"📧 [SIMULACION EMAIL] A: {email} | Asunto: {asunto}")

    def generar_reporte_diario(self):
        conn = self.conectar_db()
        cur = conn.cursor()
        logging.info("📊 Generando reportes diarios...")
        try:
            cur.execute("SELECT id, email, full_name FROM clients WHERE is_active = TRUE")
            clientes = cur.fetchall()
            for c in clientes:
                cid, email, nombre = c
                cur.execute("""
                    SELECT COUNT(*) FILTER (WHERE p.status='cazado') as nuevos,
                           COUNT(*) FILTER (WHERE p.status='persuadido') as listos_nutrir
                    FROM prospects p JOIN campaigns cam ON p.campaign_id = cam.id
                    WHERE cam.client_id = %s AND p.created_at >= NOW() - INTERVAL '24 HOURS'
                """, (cid,))
                stats = cur.fetchone()
                if stats:
                    cuerpo = f"Hola {nombre}, resumen: {stats[0]} nuevos, {stats[1]} contactados."
                    self.enviar_notificacion(email, "Reporte Diario AutoNeura", cuerpo)
        except Exception as e:
            logging.error(f"Error reportes: {e}")
        finally:
            cur.close()
            conn.close()

    # ==============================================================================
    # 🏁 BUCLE PRINCIPAL (NUEVO RITMO)
    # ==============================================================================

    def iniciar_turno(self):
        logging.info(">>> 🤖 ORQUESTADOR SUPREMO (MODO SECUENCIAL 24H) 🤖 <<<")
        
        ultima_revision_reportes = datetime.now() - timedelta(days=1)
        
        while True:
            try:
                inicio_ciclo = time.time()
                
                # 1. Finanzas (Siempre primero)
                self.gestionar_finanzas_clientes()
                
                # 2. Operaciones Tácticas (La Cadena de Montaje)
                self.coordinar_operaciones_diarias()
                
                # 3. Reportes
                if datetime.now() > ultima_revision_reportes + timedelta(hours=24):
                    self.generar_reporte_diario()
                    ultima_revision_reportes = datetime.now()

                # 4. DESCANSO DEL CICLO MAYOR
                duracion_proceso = time.time() - inicio_ciclo
                
                tiempo_base_descanso = 3600 # 1 hora
                
                if duracion_proceso > 1800:
                    tiempo_dormir = 600
                else:
                    tiempo_dormir = tiempo_base_descanso - duracion_proceso
                    if tiempo_dormir < 600: tiempo_dormir = 600 

                logging.info(f"💤 Vuelta completa en {duracion_proceso/60:.1f} mins. Durmiendo {tiempo_dormir/60:.1f} mins...")
                time.sleep(tiempo_dormir) 

            except KeyboardInterrupt:
                logging.info("🛑 Deteniendo sistema...")
                break
            except Exception as e:
                logging.critical(f"🔥 ERROR CATASTRÓFICO: {e}")
                time.sleep(60)

if __name__ == "__main__":
    ceo = OrquestadorSupremo()
    ceo.iniciar_turno()
