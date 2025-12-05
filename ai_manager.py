import os
import random
import time
from datetime import datetime, date
from supabase import create_client, Client
import google.generativeai as genai

# Configuración de Supabase
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

class AIManager:
    def __init__(self):
        pass
        
    def get_optimal_model(self, task_type="general"):
        """
        Busca la mejor IA disponible.
        """
        # 1. Buscamos modelos (FREE primero)
        candidate = self._find_available_key(task_type, account_tier='FREE')
        
        # 2. Si no hay gratis, buscamos PAGAS
        if not candidate:
            print("⚠️ No hay cuentas GRATIS disponibles. Buscando en RESERVA (PAID)...")
            candidate = self._find_available_key(task_type, account_tier='PAID')
            
        if not candidate:
            raise Exception("❌ ERROR CRÍTICO: Todas las IAs están ocupadas o muertas.")

        # 3. Configuramos la IA
        api_key = candidate['ai_vault']['api_key']
        model_name = candidate['model_name']
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        
        print(f"✅ Cerebro Asignado: {model_name}")
        
        # Retornamos modelo y ID para reportar éxito o fallo
        return model, candidate['id']

    def _find_available_key(self, task_type, account_tier):
        try:
            # Traemos last_usage_date para saber si hay que resetear
            response = supabase.table('ai_models').select(
                'id, model_name, usage_today, daily_limit, safety_margin, last_usage_date, ai_vault!inner(api_key, owner_email, account_type, is_active)'
            ).eq('ai_vault.is_active', True)\
             .eq('ai_vault.account_type', account_tier)\
             .filter('purpose', 'in', f'("general","{task_type}")')\
             .execute()
            
            valid_candidates = []
            hoy_str = str(date.today()) 
            
            for item in response.data:
                # --- AUTO-LIMPIEZA DIARIA ---
                fecha_guardada = item.get('last_usage_date')
                uso_actual = item['usage_today']
                
                if fecha_guardada != hoy_str:
                    uso_actual = 0 # Nuevo día, cuenta nueva
                
                # --- VERIFICACIÓN DE LÍMITES ---
                # Si el uso es 99999 (Marcado como MUERTO/404), nunca entra aquí.
                limite_seguro = item['daily_limit'] - item['safety_margin']
                
                if uso_actual < limite_seguro:
                    valid_candidates.append(item)
            
            if valid_candidates:
                return random.choice(valid_candidates)
            return None

        except Exception as e:
            print(f"Error consultando DB de IA: {e}")
            return None

    def register_usage(self, model_id):
        """ Registra éxito: Suma +1 y actualiza fecha """
        try:
            hoy_str = str(date.today())
            data = supabase.table('ai_models').select('usage_today, last_usage_date').eq('id', model_id).single().execute()
            if not data.data: return

            stored_date = data.data.get('last_usage_date')
            current_usage = data.data.get('usage_today', 0)
            
            new_usage = 1 if stored_date != hoy_str else current_usage + 1
            
            supabase.table('ai_models').update({
                'usage_today': new_usage,
                'last_usage_date': hoy_str
            }).eq('id', model_id).execute()
            
        except Exception as e:
            print(f"Error actualizando contador: {e}")

    def report_failure(self, model_id, error_message=""):
        """
        SISTEMA DE AUTO-DEPURACIÓN INTELIGENTE:
        - Si es 429 (Límite): Bloquea por HOY (9999).
        - Si es 404 (No existe): Bloquea PARA SIEMPRE (99999).
        """
        try:
            hoy_str = str(date.today())
            err_str = str(error_message).lower()
            
            nuevo_uso = 9999 # Por defecto: Bloqueo diario (429)
            
            if "404" in err_str or "not found" in err_str:
                print(f"💀 MODELO FANTASMA DETECTADO ID: {model_id}. Eliminando de la rotación permanentemente.")
                nuevo_uso = 99999 # Bloqueo eterno (simbólico, supera cualquier límite diario)
            else:
                print(f"🚨 LÍMITE ALCANZADO ID: {model_id}. Bloqueando por hoy...")

            supabase.table('ai_models').update({
                'usage_today': nuevo_uso,
                'last_usage_date': hoy_str
            }).eq('id', model_id).execute()
            
        except Exception as e:
            print(f"Error reportando fallo de IA: {e}")

# Instancia global
brain = AIManager()
