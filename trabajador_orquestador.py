import os
import time
import logging
import psycopg2
import threading
from datetime import datetime, timedelta
from psycopg2.extras import Json
import google.generativeai as genai
from dotenv import load_dotenv

# --- IMPORTACIÓN DE TRABAJADORES (TUS EMPLEADOS) ---
try:
    from trabajador_cazador import ejecutar_caza
    from trabajador_analista import TrabajadorAnalista
    from trabajador_persuasor import TrabajadorPersuasor
    from trabajador_nutridor import TrabajadorNutridor
except ImportError as e:
    print(f"!!! ERROR CRÍTICO: Faltan archivos de trabajadores: {e}")
    exit(1)

# --- CONFIGURACIÓN ---
load_dotenv()

# Configuración de Logs (Formato profesional)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - ORQUESTADOR (CEO) - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("sistema_ventas.log"),
        logging.StreamHandler()
    ]
)

DATABASE_URL = os.environ.get("DATABASE_URL")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

# Configuración IA (Cerebro Estratégico)
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)

class OrquestadorSupremo:
    def __init__(self):
        self.analista = TrabajadorAnalista()
        self.persuasor = TrabajadorPersuasor()
        self.nutridor = TrabajadorNutridor()
        self.model = genai.GenerativeModel('gemini-2.5-flash') if GOOGLE_API_KEY else None

    def conectar_db(self):
        return psycopg2.connect(DATABASE_URL)

    # ==========================================
    # MÓDULO 1: GESTIÓN FINANCIERA Y DE SUSCRIPCIONES
    # ==========================================

    def gestionar_ciclo_vida_clientes(self):
        """
        Revisa pagos, corta servicios y elimina datos de morosos.
        """
        conn = self.conectar_db()
        cur = conn.cursor()
        try:
            # 1. ALERTA DE PAGO (3 días antes)
            cur.execute("""
                SELECT id, email, full_name, next_payment_date 
                FROM clients 
                WHERE is_active = TRUE 
                AND next_payment_date BETWEEN NOW() AND NOW() + INTERVAL '3 DAYS'
                AND payment_alert_sent = FALSE
            """)
            por_vencer = cur.fetchall()
            for cliente in por_vencer:
                self.enviar_email_sistema(cliente[1], "Recordatorio de Pago", 
                    f"Hola {cliente[2]}, tu suscripción vence el {cliente[3]}. Por favor recarga saldo.")
                cur.execute("UPDATE clients SET payment_alert_sent = TRUE WHERE id = %s", (cliente[0],))

            # 2. CORTE DE SERVICIO (Día de pago fallido)
            cur.execute("""
                SELECT id, email, balance, plan_cost 
                FROM clients 
                WHERE is_active = TRUE AND next_payment_date < NOW()
            """)
            vencidos = cur.fetchall()
            for cliente in vencidos:
                cid, email, saldo, costo = cliente
                if saldo >= costo:
                    # Cobro exitoso
                    nuevo_saldo = saldo - costo
                    cur.execute("""
                        UPDATE clients 
                        SET balance = %s, next_payment_date = next_payment_date + INTERVAL '30 DAYS', payment_alert_sent = FALSE 
                        WHERE id = %s
                    """, (nuevo_saldo, cid))
                    logging.info(f"💰 Cobro exitoso al cliente {cid}. Nuevo saldo: {nuevo_saldo}")
                else:
                    # Fallo de pago -> Corte de servicio
                    cur.execute("UPDATE clients SET is_active = FALSE, status = 'suspended' WHERE id = %s", (cid,))
                    self.enviar_email_sistema(email, "Servicio Suspendido", 
                        "No pudimos procesar tu pago. Tus trabajadores han sido detenidos. Recarga para continuar.")
                    logging.warning(f"⛔ Servicio suspendido para {cid} por falta de saldo.")

            # 3. ELIMINACIÓN DE MOROSOS (2 días después del corte)
            cur.execute("""
                SELECT id, email FROM clients 
                WHERE status = 'suspended' 
                AND next_payment_date < NOW() - INTERVAL '2 DAYS'
            """)
            morosos = cur.fetchall()
            for moroso in morosos:
                cid, email = moroso
                logging.info(f"🗑️ ELIMINANDO DATOS de cliente moroso {cid}...")
                
                # Eliminar trabajadores y prospectos (Limpieza total)
                cur.execute("DELETE FROM prospects WHERE campaign_id IN (SELECT id FROM campaigns WHERE client_id = %s)", (cid,))
                cur.execute("DELETE FROM campaigns WHERE client_id = %s", (cid,))
                # Opcional: Eliminar cliente o dejarlo marcado como 'deleted'
                cur.execute("UPDATE clients SET status = 'deleted_data' WHERE id = %s", (cid,))
                
                self.enviar_email_sistema(email, "Cuenta Eliminada", 
                    "Debido a la falta de pago, hemos eliminado tus datos y campañas. Esperamos verte pronto.")

            conn.commit()
        except Exception as e:
            logging.error(f"Error en gestión financiera: {e}")
            conn.rollback()
        finally:
            cur.close()
            conn.close()

    # ==========================================
    # MÓDULO 2: ESTRATEGIA DE MERCADO (CEREBRO IA)
    # ==========================================

    def definir_estrategia_caza(self, campana):
        """
        Usa IA para convertir "Vendo casas" en "Buscar Inversores en Miami".
        """
        if not self.model: return campana['target_audience'], "Google Maps"

        prompt = f"""
        ACTÚA COMO: Estratega de Marketing de Guerrilla.
        CLIENTE VENDE: {campana['product_description']}
        OBJETIVO: {campana['campaign_name']}
        UBICACIÓN: {campana['geo_location']}
        
        TU MISIÓN:
        1. Identifica quién compra esto (Perfil B2B, B2C, B2G).
        2. Define la búsqueda EXACTA para encontrarlo en Google Maps o Redes.
        3. Elige la mejor herramienta (Google Maps, LinkedIn, Instagram).
        
        SALIDA JSON: {{"query_busqueda": "...", "plataforma": "..."}}
        """
        try:
            res = self.model.generate_content(prompt)
            estrat = json.loads(res.text.replace("```json", "").replace("```", "").strip())
            return estrat['query_busqueda'], estrat['plataforma']
        except:
            return campana['target_audience'], "Google Maps"

    # ==========================================
    # MÓDULO 3: COORDINACIÓN DE TRABAJADORES
    # ==========================================

    def ejecutar_hilo_cazador(self, camp_id, query, ubicacion, plataforma, cantidad):
        """Ejecuta al Cazador en un hilo separado para escalabilidad."""
        try:
            ejecutar_caza(camp_id, query, ubicacion, plataforma, cantidad)
        except Exception as e:
            logging.error(f"Error en hilo cazador {camp_id}: {e}")

    def gestionar_operaciones_diarias(self):
        conn = self.conectar_db()
        cur = conn.cursor()
        
        try:
            # 1. OBTENER CAMPAÑAS ACTIVAS Y CON CUPO
            cur.execute("""
                SELECT c.id, c.client_id, c.campaign_name, c.product_description, 
                       c.geo_location, c.target_audience, cl.daily_prospects_quota
                FROM campaigns c
                JOIN clients cl ON c.client_id = cl.id
                WHERE c.status = 'active' AND cl.is_active = TRUE
            """)
            campanas = cur.fetchall()

            for camp in campanas:
                cid, client_id, nombre, prod, ubic, audiencia, cuota = camp
                
                # Verificar cuántos prospectos VÁLIDOS (3 interacciones) tenemos hoy
                # NOTA: Tu regla dice que se cobra por válidos, pero cazamos más.
                # Aquí limitamos la CAZA para no sobrecargar costos de APIFY.
                # Factor de sobrecaza: Cazamos 3x la cuota para asegurar conversiones.
                meta_caza_diaria = cuota * 3 
                
                cur.execute("SELECT COUNT(*) FROM prospects WHERE campaign_id = %s AND created_at::date = CURRENT_DATE", (cid,))
                cazados_hoy = cur.fetchone()[0]

                if cazados_hoy < meta_caza_diaria:
                    faltantes = meta_caza_diaria - cazados_hoy
                    
                    # 🧠 Definir Estrategia con IA
                    query_ia, plataforma_ia = self.definir_estrategia_caza({
                        'product_description': prod, 'campaign_name': nombre, 
                        'geo_location': ubic, 'target_audience': audiencia
                    })
                    
                    logging.info(f"🚀 Lanzando Cazador para '{nombre}'. Meta: {faltantes}. Estrategia: {query_ia} en {plataforma_ia}")
                    
                    # ESCALADO DE RECURSOS: Si faltan muchos, usamos hilos.
                    hilo = threading.Thread(target=self.ejecutar_hilo_cazador, args=(cid, query_ia, ubic, plataforma_ia, faltantes))
                    hilo.start()
                else:
                    logging.info(f"⏸️ Campaña '{nombre}' en pausa. Meta de caza cumplida ({cazados_hoy}/{meta_caza_diaria}).")

            # 2. ACTIVAR ANALISTA (Procesa todo lo cazado)
            self.analista.procesar_lote()

            # 3. ACTIVAR PERSUASOR (Genera mensajes para los analizados)
            self.persuasor.procesar_lote()

            # 4. ACTIVAR NUTRIDOR (Gestiona seguimientos y embudo)
            self.nutridor.procesar_seguimientos()

        finally:
            cur.close()
            conn.close()

    # ==========================================
    # MÓDULO 4: REPORTES Y COMUNICACIÓN
    # ==========================================

    def enviar_email_sistema(self, destinatario, asunto, cuerpo):
        """Simula envío de emails del sistema (Reportes, Alertas)."""
        logging.info(f"📨 EMAIL SISTEMA a {destinatario} | Asunto: {asunto}")
        # Aquí iría la conexión SMTP real

    def generar_reportes_diarios(self):
        """Envía el reporte de avance cada 24h."""
        conn = self.conectar_db()
        cur = conn.cursor()
        try:
            cur.execute("SELECT id, email, full_name FROM clients WHERE is_active = TRUE")
            clientes = cur.fetchall()
            
            for cl in clientes:
                cid, email, nombre = cl
                # Estadísticas del día
                cur.execute("""
                    SELECT COUNT(*) FILTER (WHERE status='cazado') as cazados,
                           COUNT(*) FILTER (WHERE status='nutriendo') as en_nido,
                           COUNT(*) FILTER (WHERE interactions_count >= 3) as calificados
                    FROM prospects 
                    WHERE campaign_id IN (SELECT id FROM campaigns WHERE client_id = %s)
                    AND created_at >= NOW() - INTERVAL '24 HOURS'
                """, (cid,))
                stats = cur.fetchone()
                
                cuerpo_email = f"""
                Hola {nombre}, aquí tienes tu reporte diario de AutoNeura:
                - Nuevos Prospectos Encontrados: {stats[0]}
                - Prospectos que entraron al Nido: {stats[1]}
                - LEADS CALIFICADOS (Facturables): {stats[2]}
                
                ¡Tu sistema sigue trabajando mientras duermes!
                """
                self.enviar_email_sistema(email, "Reporte Diario AutoNeura", cuerpo_email)
        finally:
            cur.close()
            conn.close()

    # ==========================================
    # BUCLE PRINCIPAL (MAIN LOOP)
    # ==========================================

    def iniciar_operaciones(self):
        logging.info(">>> SISTEMA DE VENTAS COGNITIVO AUTÓNOMO INICIADO <<<")
        
        schedule_reportes = datetime.now()
        
        while True:
            try:
                # 1. Gestión Financiera (Cada ciclo, es rápido)
                self.gestionar_ciclo_vida_clientes()
                
                # 2. Operaciones de Venta (Caza, Análisis, Persuasión, Nutrición)
                self.gestionar_operaciones_diarias()
                
                # 3. Reportes Diarios (Una vez al día)
                if datetime.now() > schedule_reportes + timedelta(hours=24):
                    self.generar_reportes_diarios()
                    schedule_reportes = datetime.now()

                # Descanso táctico para no saturar la CPU/DB
                logging.info("💤 Ciclo completado. Esperando 5 minutos...")
                time.sleep(300) 

            except KeyboardInterrupt:
                logging.info("🛑 Apagando sistema manualmente...")
                break
            except Exception as e:
                logging.critical(f"!!! ERROR EN ORQUESTADOR: {e}")
                time.sleep(60) # Espera de seguridad ante fallos

if __name__ == "__main__":
    ceo = OrquestadorSupremo()
    ceo.iniciar_operaciones()
