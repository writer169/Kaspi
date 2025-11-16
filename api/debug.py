# api/debug.py - Отладка парсинга
from http.server import BaseHTTPRequestHandler
import requests
import json
from datetime import datetime
from bs4 import BeautifulSoup
import os
from urllib.parse import urlparse, parse_qs

KASPI_URL = os.getenv("KASPI_URL")
API_KEY = os.getenv("API_KEY")
SCRAPER_API_KEY = os.getenv("SCRAPER_API_KEY")

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urlparse(self.path)
        params = parse_qs(parsed_url.query)
        provided_key = params.get('key', [None])[0]
        
        if not API_KEY or provided_key != API_KEY:
            self.send_response(403)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid API key"}).encode())
            return
        
        try:
            # Получаем страницу через ScraperAPI
            response = requests.get(
                "https://api.scraperapi.com",
                params={
                    "api_key": SCRAPER_API_KEY,
                    "url": KASPI_URL
                },
                timeout=60
            )
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Ищем все возможные источники данных
            debug_info = {
                "url": KASPI_URL,
                "status_code": response.status_code,
                "html_length": len(response.text),
                "timestamp": datetime.now().isoformat()
            }
            
            # 1. JSON-LD блок
            json_ld = soup.find("script", {"type": "application/ld+json"})
            if json_ld:
                try:
                    json_data = json.loads(json_ld.text)
                    debug_info["json_ld"] = {
                        "found": True,
                        "name": json_data.get("name"),
                        "offers": json_data.get("offers"),
                        "full_data": json_data
                    }
                except:
                    debug_info["json_ld"] = {"found": True, "parse_error": True}
            else:
                debug_info["json_ld"] = {"found": False}
            
            # 2. Meta теги
            meta_tags = {
                "og:title": soup.find("meta", {"property": "og:title"}),
                "og:description": soup.find("meta", {"property": "og:description"}),
                "product:price:amount": soup.find("meta", {"property": "product:price:amount"}),
                "product:availability": soup.find("meta", {"property": "product:availability"})
            }
            
            debug_info["meta_tags"] = {}
            for key, tag in meta_tags.items():
                if tag:
                    debug_info["meta_tags"][key] = tag.get("content")
            
            # 3. Ищем кнопки и элементы UI
            buy_button = soup.find("button", {"data-role": "add-to-cart"})
            debug_info["buy_button"] = {"found": bool(buy_button)}
            
            # 4. Ищем ценовые элементы
            price_elements = soup.find_all(class_=lambda x: x and 'price' in x.lower() if x else False)
            debug_info["price_elements_count"] = len(price_elements)
            
            # 5. Ищем availability элементы
            availability_elements = soup.find_all(text=lambda x: x and any(word in x.lower() for word in ['наличии', 'stock', 'доступен']) if x else False)
            debug_info["availability_texts"] = [text.strip() for text in availability_elements[:5]]
            
            # 6. Структура страницы
            debug_info["page_structure"] = {
                "title": soup.title.text if soup.title else None,
                "h1_count": len(soup.find_all("h1")),
                "script_count": len(soup.find_all("script")),
                "has_react": bool(soup.find("div", {"id": "root"}) or soup.find("div", {"id": "app"}))
            }
            
            # 7. Первые 500 символов HTML для анализа
            debug_info["html_preview"] = response.text[:500]
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(debug_info, ensure_ascii=False, indent=2).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            error = {"error": str(e), "type": type(e).__name__}
            self.wfile.write(json.dumps(error, ensure_ascii=False, indent=2).encode())
            return
