import os
import random
import time
from supabase import create_client, Client
import google.generativeai as genai

# Configuración de Supabase
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

class AIManager:
    def __init__(self):
        self.cached_keys = []
        self.last_cache_update = 0
        
    def get_optimal_model(self, task_type="general"):
        """
        Busca la mejor IA disponible según la tarea.
        task_type: 'velocidad' (Flash), 'inteligencia' (Pro), 'general'
        """
        print(f"--- 🧠 AI MANAGER: Buscando cerebro para tarea: {task_type} ---")
        
        # 1. Buscamos modelos en Supabase que coincidan con la tarea
        #    Prioridad: FREE primero, luego PAID. Que no hayan superado su límite hoy.
        
        # Intentamos primero con cuentas GRATIS (account_type = 'FREE')
        candidate = self._find_available_key(task_type, account_tier='FREE')
        
        # Si no hay gratis disponibles, buscamos PAGAS (account_type = 'PAID')
        if not candidate:
            print("⚠️ No hay cuentas GRATIS disponibles. Buscando en RESERVA (PAID)...")
            candidate = self._find_available_key(task_type, account_tier='PAID')
            
        if not candidate:
            raise Exception("❌ ERROR CRÍTICO: Todas las IAs están ocupadas o saturadas.")

        # 2. Configuramos la IA con la llave encontrada
        api_key = candidate['ai_vault']['api_key']
        model_name = candidate['model_name']
        
        # Configurar Google Gemini
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        
        print(f"✅ Cerebro Asignado: {model_name} (Dueño: {candidate['ai_vault']['owner_email']})")
        
        # 3. Retornamos el objeto modelo y el ID para registrar el uso después
        return model, candidate['id']

    def _find_available_key(self, task_type, account_tier):
        """
        Lógica interna para consultar Supabase
        """
        try:
            # Seleccionamos modelos donde:
            # - La llave padre está ACTIVA y es del tipo (FREE/PAID)
            # - El modelo coincide con el propósito (o es general)
            # - El uso de hoy + margen < limite diario
            
            response = supabase.table('ai_models').select(
                'id, model_name, usage_today, daily_limit, safety_margin, ai_vault!inner(api_key, owner_email, account_type, is_active)'
            ).eq('ai_vault.is_active', True)\
             .eq('ai_vault.account_type', account_tier)\
             .filter('purpose', 'in', f'("general","{task_type}")')\
             .execute()
            
            valid_candidates = []
            
            for item in response.data:
                # Verificación matemática de seguridad
                limite_seguro = item['daily_limit'] - item['safety_margin']
                if item['usage_today'] < limite_seguro:
                    valid_candidates.append(item)
            
            if valid_candidates:
                # Elegimos uno al azar para balancear la carga entre cuentas del mismo tipo
                return random.choice(valid_candidates)
            return None

        except Exception as e:
            print(f"Error consultando DB de IA: {e}")
            return None

    def register_usage(self, model_id):
        """
        Suma +1 al contador de uso de ese modelo específico.
        """
        try:
            # Primero obtenemos el valor actual para sumar 1 (o usamos rpc si creamos función SQL, 
            # pero por ahora hacemos lectura-escritura simple para no complicarte con más SQL)
            
            # Forma simple: llamar a un RPC de Supabase es lo ideal para atomicidad,
            # pero aquí haremos un update directo por simplicidad.
            
            # 1. Leer dato actual
            data = supabase.table('ai_models').select('usage_today').eq('id', model_id).single().execute()
            current_usage = data.data['usage_today'] or 0
            
            # 2. Actualizar
            supabase.table('ai_models').update({'usage_today': current_usage + 1}).eq('id', model_id).execute()
            # print(f"📈 Contador actualizado para modelo {model_id}")
            
        except Exception as e:
            print(f"Error actualizando contador de uso: {e}")

# Instancia global para importar en otros archivos
brain = AIManager()
