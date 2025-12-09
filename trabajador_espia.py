import os
import re
import logging
import requests
import psycopg2
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# --- CONFIGURACIÓN ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - SUPER ESPIA - %(levelname)s - %(message)s')

DATABASE_URL = os.environ.get("DATABASE_URL")

# --- LISTA NEGRA DE EMAILS BASURA (Para no guardar basura) ---
EMAILS_IGNORAR = [
    "sentry", "noreply", "no-reply", "example", "domain", "email", 
    "nombre", "tusitio", "usuario", "wixpress", "wordpress", 
    ".png", ".jpg", ".jpeg", ".gif", ".webp", "2x.png"
]

# --- CABECERAS PARA PARECER UN NAVEGADOR REAL (Evita bloqueos 403) ---
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Connection': 'keep-alive',
}

class SuperEspiaWeb:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def es_email_valido(self, email):
        """ Filtra emails falsos, imágenes o de librerías JS """
        email = email.lower()
        if len(email) < 6 or len(email) > 50: return False
        if any(bad in email for bad in EMAILS_IGNORAR): return False
        # Verificar estructura real
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email): return False
        return True

    def extraer_emails_de_texto(self, texto):
        """ Usa Regex para sacar emails de cualquier sopa de letras """
        if not texto: return set()
        # Regex mejorada para evitar falsos positivos
        raw_emails = set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', texto))
        return {e for e in raw_emails if self.es_email_valido(e)}

    def escanear_pagina(self, url):
        """ Descarga y analiza una URL específica """
        try:
            resp = self.session.get(url, timeout=10) # Timeout corto para ser rápido
            if resp.status_code != 200: return set()
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # 1. Buscar en mailto: links (Lo más efectivo)
            emails_encontrados = set()
            for link in soup.select('a[href^="mailto:"]'):
                email = link.get('href').replace('mailto:', '').split('?')[0]
                if self.es_email_valido(email):
                    emails_encontrados.add(email)
            
            # 2. Buscar en el texto visible
            emails_encontrados.update(self.extraer_emails_de_texto(soup.get_text()))
            
            return emails_encontrados
        except Exception:
            return set()

    def infiltrarse_en_sitio(self, url_base):
        """ 
        Estrategia Maestra:
        1. Escanea la Home.
        2. Busca links a 'Contacto', 'About', 'Nosotros'.
        3. Escanea esas páginas internas.
        """
        if not url_base: return None
        if not url_base.startswith('http'): url_base = 'http://' + url_base

        emails_totales = set()
        print(f"🕵️ Infiltrándose en: {url_base}")

        try:
            # 1. Escaneo Home
            resp = self.session.get(url_base, timeout=15)
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Sacar emails de Home
            emails_totales.update(self.extraer_emails_de_texto(soup.get_text()))
            for link in soup.select('a[href^="mailto:"]'):
                emails_totales.add(link.get('href').replace('mailto:', '').split('?')[0])

            # 2. Buscar páginas satélite (Contacto, About)
            links_internos = set()
            palabras_clave = ['contact', 'contac', 'about', 'nosotros', 'equipo', 'team']
            
            for a in soup.find_all('a', href=True):
                href = a['href']
                if any(k in href.lower() for k in palabras_clave):
                    full_url = urljoin(url_base, href)
                    # Asegurar que sea del mismo dominio
                    if urlparse(full_url).netloc == urlparse(url_base).netloc:
                        links_internos.add(full_url)

            # 3. Escanear Satélites (Máximo 3 para no tardar años)
            for link_interno in list(links_internos)[:3]:
                # print(f"   -> Revisando sub-página: {link_interno}")
                emails_totales.update(self.escanear_pagina(link_interno))

        except Exception as e:
            logging.warning(f"⚠️ Sitio web blindado o caído ({url_base}): {str(e)[:50]}")
            return None

        # Filtrar final
        validos = [e for e in emails_totales if self.es_email_valido(e)]
        
        if validos:
            # Prioridad: Info, Contacto, Admin
            prioritarios = [e for e in validos if any(x in e for x in ['info', 'contact', 'hello', 'hola', 'admin'])]
            return prioritarios[0] if prioritarios else validos[0]
        
        return None

# --- FUNCIÓN PRINCIPAL (LA QUE LLAMA EL ORQUESTADOR) ---

def ejecutar_espia(campana_id, limite_diario_contratado=4):
    logging.info(f"🕵️ SUPER ESPÍA WEB ACTIVO | Campaña: {campana_id}")
    
    agente007 = SuperEspiaWeb()
    conn = None
    
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()

        # 1. AUDITORÍA GRATUITA (Mover los que ya tienen datos)
        cur.execute("""
            UPDATE prospects SET status = 'espiado', updated_at = NOW()
            WHERE campaign_id = %s AND status = 'cazado' 
            AND captured_email IS NOT NULL AND length(captured_email) > 5
        """, (campana_id,))
        if cur.rowcount > 0:
            logging.info(f"✨ {cur.rowcount} prospectos ya tenían email. Promovidos gratis.")
        conn.commit()

        # 2. SELECCIONAR OBJETIVOS (Tienen Web pero no Email)
        query = """
            SELECT id, website_url, business_name
            FROM prospects
            WHERE campaign_id = %s
            AND status = 'cazado'
            AND website_url IS NOT NULL
            AND (captured_email IS NULL OR length(captured_email) < 5)
            LIMIT 10; -- Lote pequeño para ser rápido
        """
        cur.execute(query, (campana_id,))
        objetivos = cur.fetchall()

        if not objetivos:
            logging.info("💤 No hay webs pendientes para espiar.")
            return

        logging.info(f"🎯 Objetivos en la mira: {len(objetivos)}")
        
        for pid, web, nombre in objetivos:
            nuevo_email = agente007.infiltrarse_en_sitio(web)
            
            if nuevo_email:
                logging.info(f"✅ ¡ÉXITO! Email robado de {web}: {nuevo_email}")
                cur.execute("""
                    UPDATE prospects 
                    SET captured_email = %s, status = 'espiado', updated_at = NOW()
                    WHERE id = %s
                """, (nuevo_email, pid))
            else:
                logging.info(f"❌ Misión fallida en {web}. Marcado como revisado.")
                # Lo pasamos a 'espiado' igual, para que el Analista decida si sirve sin email (o con teléfono)
                # O lo marcamos como 'revisado_sin_email' si quieres ser estricto.
                # Por ahora, lo pasamos para no trancar el flujo.
                cur.execute("UPDATE prospects SET status = 'espiado', updated_at = NOW() WHERE id = %s", (pid,))
            
            conn.commit()

    except Exception as e:
        logging.error(f"🔥 Error Crítico del Espía: {e}")
        if conn: conn.rollback()
    finally:
        if conn: conn.close()

if __name__ == "__main__":
    # Prueba manual
    print("Modo prueba...")
    # ejecutar_espia("ID_DE_CAMPAÑA_AQUI")
