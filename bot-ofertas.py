# app.py
from flask import Flask, render_template, jsonify, request
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time
from datetime import datetime
import json
import os
import urllib.parse
import threading

app = Flask(__name__)

class FalabellaOfertasBot:
    def __init__(self, whatsapp_number, descuento_min=98, descuento_max=100):
        self.whatsapp_number = whatsapp_number
        self.ofertas_vistas = set()
        self.ofertas_encontradas = []
        self.bot_activo = False
        self.ultimo_chequeo = None
        self.urls_monitorear = []
        self.descuento_min = descuento_min
        self.descuento_max = descuento_max
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
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        driver = None
        try:
            driver = webdriver.Chrome(options=chrome_options)
            driver.get(url)
            time.sleep(5)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            ofertas = []
            
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
                    break
            
            if not productos:
                return []
            
            for producto in productos:
                try:
                    nombre_elem = producto.find(['b', 'h2', 'h3', 'span'], class_=lambda x: x and 'name' in x.lower() if x else False)
                    if not nombre_elem:
                        nombre_elem = producto.find(['b', 'h2', 'h3'])
                    nombre = nombre_elem.text.strip() if nombre_elem else 'Sin nombre'
                    
                    precio_elem = producto.find(['span', 'div'], class_=lambda x: x and ('price' in x.lower() or 'precio' in x.lower()) if x else False)
                    precio = precio_elem.text.strip() if precio_elem else 'N/A'
                    
                    descuento_elem = producto.find(['span', 'div'], class_=lambda x: x and ('discount' in x.lower() or 'descuento' in x.lower() or 'off' in x.lower()) if x else False)
                    
                    if descuento_elem:
                        descuento_texto = descuento_elem.text.strip()
                        import re
                        numeros = re.findall(r'\d+', descuento_texto)
                        if numeros:
                            descuento = int(numeros[0])
                            
                            if self.descuento_min <= descuento <= self.descuento_max:
                                link_elem = producto.find('a', href=True)
                                link = link_elem['href'] if link_elem else ''
                                if link and not link.startswith('http'):
                                    link = 'https://www.falabella.com' + link
                                
                                oferta = {
                                    'nombre': nombre[:100],
                                    'descuento': descuento,
                                    'precio': precio,
                                    'link': link,
                                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                }
                                ofertas.append(oferta)
                except Exception as e:
                    continue
            
            return ofertas
        
        except Exception as e:
            print(f"Error al hacer scraping: {e}")
            return []
        
        finally:
            if driver:
                driver.quit()
    
    def enviar_whatsapp_callmebot(self, mensaje):
        api_key = '8215263'
        mensaje_codificado = urllib.parse.quote(mensaje)
        url = f'https://api.callmebot.com/whatsapp.php?phone={self.whatsapp_number.replace("+", "")}&text={mensaje_codificado}&apikey={api_key}'
        
        try:
            response = requests.get(url)
            return response.status_code == 200
        except Exception as e:
            print(f"Error: {e}")
            return False
    
    def formatear_mensaje(self, ofertas):
        mensaje = "🔥 OFERTAS DETECTADAS 🔥\n\n"
        for oferta in ofertas:
            mensaje += f"📦 {oferta['nombre']}\n"
            mensaje += f"💰 Precio: {oferta['precio']}\n"
            mensaje += f"🎯 Descuento: {oferta['descuento']}%\n"
            mensaje += f"🔗 {oferta['link']}\n\n"
        return mensaje
    
    def ciclo_monitoreo(self, intervalo=60):
        """Ciclo de monitoreo continuo"""
        while self.bot_activo:
            try:
                ofertas_nuevas = []
                self.ultimo_chequeo = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                for url in self.urls_monitorear:
                    ofertas = self.scrape_falabella(url)
                    
                    for oferta in ofertas:
                        oferta_id = oferta['link']
                        if oferta_id not in self.ofertas_vistas:
                            ofertas_nuevas.append(oferta)
                            self.ofertas_vistas.add(oferta_id)
                            self.ofertas_encontradas.insert(0, oferta)
                
                if ofertas_nuevas:
                    mensaje = self.formatear_mensaje(ofertas_nuevas)
                    self.enviar_whatsapp_callmebot(mensaje)
                    self.guardar_ofertas_vistas()
                
                time.sleep(intervalo)
                
            except Exception as e:
                print(f"Error en ciclo: {e}")
                time.sleep(intervalo)

# Instancia global del bot
bot = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/iniciar', methods=['POST'])
def iniciar_bot():
    global bot
    data = request.json
    
    whatsapp = data.get('whatsapp', '+56936394560')
    urls = data.get('urls', ['https://www.falabella.com/falabella-cl/page/ultimas-oportunidades'])
    intervalo = data.get('intervalo', 60)
    
    if bot is None or not bot.bot_activo:
        bot = FalabellaOfertasBot(whatsapp)
        bot.urls_monitorear = urls
        bot.bot_activo = True
        
        # Iniciar en un hilo separado
        thread = threading.Thread(target=bot.ciclo_monitoreo, args=(intervalo,))
        thread.daemon = True
        thread.start()
        
        return jsonify({'status': 'success', 'mensaje': 'Bot iniciado correctamente'})
    else:
        return jsonify({'status': 'error', 'mensaje': 'El bot ya está activo'})

@app.route('/api/detener', methods=['POST'])
def detener_bot():
    global bot
    if bot and bot.bot_activo:
        bot.bot_activo = False
        bot.guardar_ofertas_vistas()
        return jsonify({'status': 'success', 'mensaje': 'Bot detenido'})
    else:
        return jsonify({'status': 'error', 'mensaje': 'El bot no está activo'})

@app.route('/api/estado', methods=['GET'])
def estado_bot():
    global bot
    if bot:
        return jsonify({
            'activo': bot.bot_activo,
            'ultimo_chequeo': bot.ultimo_chequeo,
            'ofertas_encontradas': len(bot.ofertas_encontradas),
            'ofertas_vistas': len(bot.ofertas_vistas),
            'urls': bot.urls_monitorear
        })
    else:
        return jsonify({
            'activo': False,
            'ultimo_chequeo': None,
            'ofertas_encontradas': 0,
            'ofertas_vistas': 0,
            'urls': []
        })

@app.route('/api/ofertas', methods=['GET'])
def obtener_ofertas():
    global bot
    if bot:
        return jsonify({'ofertas': bot.ofertas_encontradas[:20]})  # Últimas 20
    else:
        return jsonify({'ofertas': []})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)