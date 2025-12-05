import os
import requests
import logging
from datetime import datetime, date
from supabase import create_client, Client

# --- CONFIGURACIÓN ---
# No necesita llaves fijas, las lee de la base de datos
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - SCRAPER MGR - %(levelname)s - %(message)s')

class ScraperManager:
    def __init__(self):
        pass

    def get_valid_key(self, provider):
        """
        Busca una llave ACTIVA y con SALDO REAL para el proveedor solicitado.
        Rotación: FREE primero -> PAID después.
        """
        # 1. Intentar con cuentas FREE
        key_data = self._find_key_in_db(provider, 'FREE')
        
        # 2. Si no hay free, intentar con PAID
        if not key_data:
            logging.warning(f"⚠️ No hay cuentas FREE disponibles para {provider}. Buscando PAID...")
            key_data = self._find_key_in_db(provider, 'PAID')
            
        if not key_data:
            logging.error(f"❌ CRÍTICO: No hay llaves disponibles para {provider}. Todo agotado.")
            return None

        # 3. Tenemos una candidata. ¿Tiene saldo real?
        # Hacemos el "Pre-Flight Check" conectando a la API del proveedor.
        if self._check_real_balance(key_data):
            # Registrar que la vamos a usar para rotación
            self._update_last_used(key_data['id'])
            return key_data['api_key']
        else:
            # Si falló el chequeo de saldo, buscamos otra recursivamente
            logging.warning(f"🔄 Llave {key_data['id']} falló chequeo de saldo. Buscando otra...")
            return self.get_valid_key(provider)

    def _find_key_in_db(self, provider, account_type):
        """Busca en Supabase una llave que no esté marcada como AGOTADA."""
        try:
            # Buscamos llaves ACTIVE. Ordenamos por last_used_at para rotar equitativamente.
            response = supabase.table('scraper_keys').select('*')\
                .eq('provider', provider)\
                .eq('account_type', account_type)\
                .eq('status', 'ACTIVE')\
                .order('last_used_at', desc=False)\
                .limit(1)\
                .execute()
            
            if response.data:
                return response.data[0]
            
            # Si no hay ACTIVE, revisamos si alguna EXHAUSTED ya cumplió su fecha de corte
            # (Esta lógica de reactivación se puede ampliar luego, por ahora priorizamos lo activo)
            return None
            
        except Exception as e:
            logging.error(f"Error DB Scraper: {e}")
            return None

    def _check_real_balance(self, key_data):
        """
        Consulta la API oficial del proveedor para ver si hay crédito.
        Si no hay, marca la llave como EXHAUSTED en la DB.
        """
        provider = key_data['provider']
        api_key = key_data['api_key']
        kid = key_data['id']
        
        try:
            saldo_ok = False
            
            # --- VERIFICACIÓN APIFY ---
            if provider == 'apify':
                # Endpoint de usuario de Apify
                url = f"https://api.apify.com/v2/users/me?token={api_key}"
                res = requests.get(url, timeout=5)
                
                if res.status_code == 200:
                    data = res.json().get('data', {})
                    limits = data.get('limits', {})
                    usage = data.get('usage', {})
                    
                    # Calculamos saldo restante (Límite - Usado)
                    # MonthlyUsageCredit suele ser el límite gratuito ($5)
                    limit_usd = limits.get('monthlyUsageCreditUsd', 0)
                    used_usd = usage.get('monthlyUsageCreditUsd', 0)
                    remaining = limit_usd - used_usd
                    
                    logging.info(f"💰 Apify Balance ID {kid}: ${remaining:.2f} restantes.")
                    
                    # Si queda menos de $0.20, la consideramos muerta para evitar cortes
                    if remaining > 0.20:
                        saldo_ok = True
                    else:
                        self._mark_as_exhausted(kid, f"Saldo bajo: ${remaining}")
                else:
                    logging.error(f"Error consultando Apify: {res.status_code}")
                    # Si da error de autenticación, la llave está mal
                    if res.status_code == 401 or res.status_code == 403:
                        self._mark_as_error(kid, "Llave inválida")

            # --- VERIFICACIÓN SERPAPI ---
            elif provider == 'serpapi':
                url = f"https://serpapi.com/account?api_key={api_key}"
                res = requests.get(url, timeout=5)
                
                if res.status_code == 200:
                    data = res.json()
                    # SerpApi da búsquedas, no dólares
                    total_limit = data.get('searches_per_month', 0)
                    used = data.get('this_month_usage', 0)
                    remaining = total_limit - used
                    
                    logging.info(f"🔍 SerpApi Balance ID {kid}: {remaining} búsquedas restantes.")
                    
                    if remaining > 2: # Mínimo 2 búsquedas
                        saldo_ok = True
                    else:
                        self._mark_as_exhausted(kid, f"Búsquedas agotadas: {remaining}")
            
            # --- OTROS (ScraperAPI, etc) ---
            else:
                # Si no tenemos integración directa, asumimos que sirve
                # hasta que falle en ejecución.
                saldo_ok = True 

            return saldo_ok

        except Exception as e:
            logging.error(f"Error conexión proveedor {provider}: {e}")
            # Si hay error de red, asumimos que está bien para no bloquear por error de internet
            return True

    def _mark_as_exhausted(self, key_id, reason):
        logging.warning(f"📉 Marcando llave {key_id} como AGOTADA. Razón: {reason}")
        supabase.table('scraper_keys').update({'status': 'EXHAUSTED'}).eq('id', key_id).execute()

    def _mark_as_error(self, key_id, reason):
        logging.error(f"🚫 Marcando llave {key_id} como ERROR. Razón: {reason}")
        supabase.table('scraper_keys').update({'status': 'ERROR'}).eq('id', key_id).execute()

    def _update_last_used(self, key_id):
        supabase.table('scraper_keys').update({'last_used_at': datetime.now().isoformat()}).eq('id', key_id).execute()

    def report_execution_failure(self, api_key):
        """
        Si un trabajador falla al usar la llave (ej: 401 Unauthorized), 
        llama a esto para buscar quién es y marcarla.
        """
        # (Lógica simplificada: busca por texto de llave)
        try:
            supabase.table('scraper_keys').update({'status': 'ERROR'}).eq('api_key', api_key).execute()
            logging.error(f"💀 Llave reportada como fallida por trabajador. Desactivada.")
        except:
            pass

# Instancia global
scraper_brain = ScraperManager()
