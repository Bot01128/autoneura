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
        Busca la mejor IA disponible. Si falla la gratuita, busca la paga.
        """
        # 1. Buscamos modelos (FREE primero)
        candidate = self._find_available_key(task_type, account_tier='FREE')
        
        # 2. Si no hay gratis, buscamos PAGAS
        if not candidate:
            print("⚠️ No hay cuentas GRATIS disponibles. Buscando en RESERVA (PAID)...")
            candidate = self._find_available_key(task_type, account_tier='PAID')
            
        if not candidate:
            raise Exception("❌ ERROR CRÍTICO: Todas las IAs están ocupadas o muertas por hoy.")

        # 3. Configuramos la IA
        api_key = candidate['ai_vault']['api_key']
        model_name = candidate['model_name']
        
        genai.configure(api_key=api_key)
        
        # Configuración de seguridad para evitar bloqueos tontos
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        
        model = genai.GenerativeModel(model_name, safety_settings=safety_settings)
        
        print(f"✅ Cerebro Asignado: {model_name} (ID: {candidate['id']})")
        
        # Retornamos modelo y ID para reportar éxito o fallo
        return model, candidate['id']

    def _find_available_key(self, task_type, account_tier):
        try:
            # Traemos la lista de modelos candidatos
            response = supabase.table('ai_models').select(
                'id, model_name, usage_today, daily_limit, safety_margin, last_usage_date, ai_vault!inner(api_key, owner_email, account_type, is_active)'
            ).eq('ai_vault.is_active', True)\
             .eq('ai_vault.account_type', account_tier)\
             .filter('purpose', 'in', f'("general","{task_type}")')\
             .execute()
            
            valid_candidates = []
            hoy_str = str(date.today()) 
            
            for item in response.data:
                fecha_guardada = item.get('last_usage_date')
                uso_actual = item['usage_today']
                
                # --- AUTO-LIMPIEZA DIARIA ---
                if fecha_guardada != hoy_str:
                    print(f"🔄 Nuevo día detectado para {item['model_name']}. Reseteando contador en DB...")
                    try:
                        supabase.table('ai_models').update({
                            'usage_today': 0,
                            'last_usage_date': hoy_str
                        }).eq('id', item['id']).execute()
                        uso_actual = 0
                    except Exception as e_reset:
                        print(f"⚠️ Error intentando resetear fecha en DB: {e_reset}")
                
                # --- VERIFICACIÓN DE LÍMITES ---
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
        """ Registra éxito: Suma +1 """
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
        """ SI FALLA: Bloqueo temporal o permanente """
        try:
            hoy_str = str(date.today())
            err_str = str(error_message).lower()
            
            data_limit = supabase.table('ai_models').select('daily_limit').eq('id', model_id).single().execute()
            limite_diario = data_limit.data.get('daily_limit', 1000) if data_limit.data else 1000
            
            nuevo_uso = limite_diario + 500 
            
            if "404" in err_str or "not found" in err_str:
                nuevo_uso = 999999 
            
            supabase.table('ai_models').update({
                'usage_today': nuevo_uso,
                'last_usage_date': hoy_str
            }).eq('id', model_id).execute()
            
        except Exception as e:
            print(f"Error reportando fallo de IA: {e}")

    # =========================================================================
    #  NUEVA FUNCIÓN: Generar Respuesta para el Panel de Control (Chat Admin)
    # =========================================================================
    def generar_respuesta_demo(self, mensaje_usuario):
        intentos = 0
        max_intentos = 2 
        
        system_prompt = """
        ERES UN ASISTENTE EJECUTIVO DE 'AUTONEURA AI'.
        Estás hablando con el Dueño/Administrador de la plataforma.
        TU MISIÓN: Responder sin usar JSON crudo. Usa viñetas. Sé profesional.
        """

        while intentos < max_intentos:
            try:
                model, model_id = self.get_optimal_model(task_type="chat_demo")
                full_prompt = f"{system_prompt}\n\nPREGUNTA DEL USUARIO: {mensaje_usuario}"
                response = model.generate_content(full_prompt)
                self.register_usage(model_id)
                return response.text
                
            except Exception as e:
                print(f"⚠️ Fallo IA Demo (Intento {intentos+1}): {e}")
                if 'model_id' in locals():
                    self.report_failure(model_id, str(e))
                intentos += 1
                time.sleep(1)
        
        return "Disculpa, socio. Mis neuronas están sobrecargadas. Intenta en un minuto."

# --- INSTANCIA GLOBAL (ESTA LÍNEA ES LA CLAVE) ---
brain = AIManager()
