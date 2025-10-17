import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
from datetime import datetime
import json
import os
import urllib.parse

class FalabellaOfertasBot:
    def __init__(self, whatsapp_number):
        self.whatsapp_number = whatsapp_number
        self.ofertas_vistas = set()
        self.cargar_ofertas_vistas()
        
    def cargar_ofertas_vistas(self):
        """Carga las ofertas ya vistas desde un archivo"""
        if os.path.exists('ofertas_vistas.json'):
            with open('ofertas_vistas.json', 'r') as f:
                self.ofertas_vistas = set(json.load(f))
    
    def guardar_ofertas_vistas(self):
        """Guarda las ofertas vistas en un archivo"""
        with open('ofertas_vistas.json', 'w') as f:
            json.dump(list(self.ofertas_vistas), f)
    
    def scrape_falabella(self, url):
        """Realiza el scraping de la página de Falabella usando Selenium"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')  # Ejecutar sin abrir ventana
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        driver = None
        try:
            driver = webdriver.Chrome(options=chrome_options)
            driver.get(url)
            
            # Esperar a que carguen los productos
            time.sleep(5)
            
            # Hacer scroll para cargar más productos
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            ofertas = []
            
            # Intentar múltiples selectores comunes de Falabella
            posibles_selectores = [
                'div.pod-4-grid',
                'div[class*="search-results"]',
                'div[class*="product"]',
                'article[class*="product"]',
                'div.grid-pod'
            ]
            
            productos = []
            for selector in posibles_selectores:
                productos = soup.select(selector)
                if productos:
                    print(f"✅ Encontrados {len(productos)} productos con selector: {selector}")
                    break
            
            if not productos:
                print("⚠️  No se encontraron productos. La estructura HTML puede haber cambiado.")
                return []
            
            for producto in productos:
                try:
                    # Buscar nombre del producto
                    nombre_elem = producto.find(['b', 'h2', 'h3', 'span'], class_=lambda x: x and 'name' in x.lower() if x else False)
                    if not nombre_elem:
                        nombre_elem = producto.find(['b', 'h2', 'h3'])
                    nombre = nombre_elem.text.strip() if nombre_elem else 'Sin nombre'
                    
                    # Buscar precio
                    precio_elem = producto.find(['span', 'div'], class_=lambda x: x and ('price' in x.lower() or 'precio' in x.lower()) if x else False)
                    precio = precio_elem.text.strip() if precio_elem else 'N/A'
                    
                    # Buscar descuento
                    descuento_elem = producto.find(['span', 'div'], class_=lambda x: x and ('discount' in x.lower() or 'descuento' in x.lower() or 'off' in x.lower()) if x else False)
                    
                    if descuento_elem:
                        descuento_texto = descuento_elem.text.strip()
                        # Extraer número del descuento
                        import re
                        numeros = re.findall(r'\d+', descuento_texto)
                        if numeros:
                            descuento = int(numeros[0])
                            
                            if 98 <= descuento <= 100:
                                # Buscar link
                                link_elem = producto.find('a', href=True)
                                link = link_elem['href'] if link_elem else ''
                                if link and not link.startswith('http'):
                                    link = 'https://www.falabella.com' + link
                                
                                oferta = {
                                    'nombre': nombre[:100],  # Limitar longitud
                                    'descuento': descuento,
                                    'precio': precio,
                                    'link': link,
                                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                }
                                ofertas.append(oferta)
                                print(f"🎯 Oferta encontrada: {nombre[:50]} - {descuento}% OFF")
                except Exception as e:
                    continue
            
            return ofertas
        
        except Exception as e:
            print(f"❌ Error al hacer scraping: {e}")
            return []
        
        finally:
            if driver:
                driver.quit()
    
    def enviar_whatsapp_twilio(self, mensaje):
        """Envía mensaje por WhatsApp usando Twilio"""
        # Necesitas configurar estas credenciales en Twilio
        account_sid = 'TU_ACCOUNT_SID'
        auth_token = 'TU_AUTH_TOKEN'
        twilio_whatsapp = 'whatsapp:+14155238886'  # Número de Twilio Sandbox
        
        url = f'https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json'
        
        data = {
            'From': twilio_whatsapp,
            'To': f'whatsapp:{self.whatsapp_number}',
            'Body': mensaje
        }
        
        try:
            response = requests.post(url, data=data, auth=(account_sid, auth_token))
            if response.status_code == 201:
                print("✅ Mensaje enviado correctamente")
                return True
            else:
                print(f"❌ Error enviando mensaje: {response.text}")
                return False
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    def enviar_whatsapp_callmebot(self, mensaje):
        """Alternativa: Envía mensaje usando CallMeBot (más simple)"""
        # Primero debes registrar tu número en: https://www.callmebot.com/blog/free-api-whatsapp-messages/
        api_key = 'TU_API_KEY'  # La recibirás por WhatsApp al registrarte
        
        url = f'https://api.callmebot.com/whatsapp.php?phone={self.whatsapp_number.replace("+", "")}&text={mensaje}&apikey={api_key}'
        
        try:
            response = requests.get(url)
            if response.status_code == 200:
                print("✅ Mensaje enviado correctamente")
                return True
            else:
                print(f"❌ Error enviando mensaje")
                return False
        except Exception as e:
            print(f"❌ Error: {e}")
            return False
    
    def formatear_mensaje(self, ofertas):
        """Formatea el mensaje con las ofertas encontradas"""
        mensaje = f"🔥 *OFERTAS DETECTADAS* 🔥\n\n"
        
        for oferta in ofertas:
            mensaje += f"📦 *{oferta['nombre']}*\n"
            mensaje += f"💰 Precio: {oferta['precio']}\n"
            mensaje += f"🎯 Descuento: {oferta['descuento']}%\n"
            mensaje += f"🔗 {oferta['link']}\n"
            mensaje += f"⏰ {oferta['timestamp']}\n\n"
        
        return mensaje
    
    def monitorear(self, urls, intervalo=60):
        """Monitorea las URLs cada X segundos"""
        print(f"🤖 Bot iniciado. Monitoreando cada {intervalo} segundos...")
        print(f"📱 Notificaciones a: {self.whatsapp_number}\n")
        
        while True:
            try:
                ofertas_nuevas = []
                
                for url in urls:
                    print(f"🔍 Revisando: {url}")
                    ofertas = self.scrape_falabella(url)
                    
                    for oferta in ofertas:
                        oferta_id = oferta['link']
                        if oferta_id not in self.ofertas_vistas:
                            ofertas_nuevas.append(oferta)
                            self.ofertas_vistas.add(oferta_id)
                
                if ofertas_nuevas:
                    print(f"🎉 ¡{len(ofertas_nuevas)} nueva(s) oferta(s) encontrada(s)!")
                    mensaje = self.formatear_mensaje(ofertas_nuevas)
                    
                    # Descomentar el método que vayas a usar:
                    # self.enviar_whatsapp_twilio(mensaje)
                    # self.enviar_whatsapp_callmebot(mensaje)
                    
                    print(mensaje)
                    self.guardar_ofertas_vistas()
                else:
                    print("ℹ️  No hay nuevas ofertas")
                
                print(f"⏳ Esperando {intervalo} segundos...\n")
                time.sleep(intervalo)
                
            except KeyboardInterrupt:
                print("\n🛑 Bot detenido por el usuario")
                self.guardar_ofertas_vistas()
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                time.sleep(intervalo)


# CONFIGURACIÓN Y EJECUCIÓN
if __name__ == "__main__":
    # Tu número de WhatsApp
    NUMERO_WHATSAPP = "+56936394560"
    
    # URLs a monitorear (puedes agregar más)
    URLS_MONITOREAR = [
        "https://www.falabella.com/falabella-cl/page/ultimas-oportunidades",
        # Agrega más URLs aquí si quieres
    ]
    
    # Crear el bot
    bot = FalabellaOfertasBot(NUMERO_WHATSAPP)
    
    # Iniciar monitoreo (revisa cada 60 segundos)
    bot.monitorear(URLS_MONITOREAR, intervalo=60)
