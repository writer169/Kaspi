# api/check.py (АЛЬТЕРНАТИВНАЯ ВЕРСИЯ через Kaspi API)
from http.server import BaseHTTPRequestHandler
import requests
import json
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from urllib.parse import urlparse, parse_qs
import re

# Получаем настройки из переменных окружения Vercel
KASPI_URL = os.getenv("KASPI_URL", "https://kaspi.kz/shop/p/ehrmann-puding-vanil-bezlaktoznyi-1-5-200-g-102110634/?c=750000000")
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_TO = os.getenv("EMAIL_TO")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
API_KEY = os.getenv("API_KEY")
SEND_EMAIL = os.getenv("SEND_EMAIL", "true").lower() == "true"

def log_message(message, level="INFO"):
    """Форматированный лог"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"[{timestamp}] [{level}] {message}\n"

def extract_product_id(url):
    """Извлекает ID товара из URL"""
    # Пример: https://kaspi.kz/shop/p/ehrmann-puding-vanil-bezlaktoznyi-1-5-200-g-102110634/?c=750000000
    # ID: 102110634
    match = re.search(r'/p/[^/]+-(\d+)/', url)
    if match:
        return match.group(1)
    return None

def send_email_notification(subject, body):
    """Отправка email уведомления"""
    if not SEND_EMAIL:
        return "Email отправка отключена"
    
    if not all([EMAIL_FROM, EMAIL_TO, EMAIL_PASSWORD]):
        return "Email настройки не настроены в переменных окружения"
    
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = EMAIL_FROM
        msg["To"] = EMAIL_TO
        
        text_body = body
        
        html_body = f"""
        <html>
          <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2 style="color: #4CAF50;">🎉 {subject}</h2>
            <p style="font-size: 16px; line-height: 1.6;">{body}</p>
            <hr style="margin: 20px 0;">
            <p>
              <a href="{KASPI_URL}" 
                 style="background-color: #4CAF50; 
                        color: white; 
                        padding: 12px 24px; 
                        text-decoration: none; 
                        border-radius: 5px;
                        display: inline-block;">
                Открыть товар на Kaspi.kz
              </a>
            </p>
            <p style="color: #666; font-size: 12px; margin-top: 20px;">
              Время проверки: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            </p>
          </body>
        </html>
        """
        
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))
        
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(EMAIL_FROM, EMAIL_PASSWORD)
        server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        server.quit()
        
        return "✅ Email успешно отправлен"
        
    except Exception as e:
        return f"❌ Ошибка отправки email: {str(e)}"

def check_kaspi_api(product_id):
    """Проверка через мобильное API Kaspi (менее строгое)"""
    logs = []
    logs.append(log_message(f"Используем Kaspi Mobile API для продукта: {product_id}"))
    
    try:
        # Мобильное API Kaspi (обычно менее защищено от rate limiting)
        api_url = f"https://kaspi.kz/yml/offer-view/offers/{product_id}"
        
        headers = {
            "User-Agent": "Kaspi.kz/11.4.1 (Android 13; SM-G998B)",
            "X-Requested-With": "kz.kaspi.mobile",
            "Accept": "application/json"
        }
        
        logs.append(log_message("Отправляем запрос к API..."))
        r = requests.get(api_url, headers=headers, timeout=10)
        logs.append(log_message(f"Статус код API: {r.status_code}"))
        
        if r.status_code == 200:
            data = r.json()
            logs.append(log_message("API вернул данные"))
            
            # Проверяем наличие
            if 'offers' in data and len(data['offers']) > 0:
                offer = data['offers'][0]
                available = offer.get('available', False)
                name = offer.get('name', 'Неизвестный товар')
                price = offer.get('price', 0)
                
                logs.append(log_message(f"Товар: {name}"))
                logs.append(log_message(f"Цена: {price} ₸"))
                logs.append(log_message(f"В наличии: {available}"))
                
                return {
                    "success": True,
                    "in_stock": available,
                    "product_name": name,
                    "price": f"{price} ₸",
                    "method": "api",
                    "logs": logs
                }
        
        return {"success": False, "logs": logs, "error": f"API returned {r.status_code}"}
        
    except Exception as e:
        logs.append(log_message(f"Ошибка API: {str(e)}", "ERROR"))
        return {"success": False, "logs": logs, "error": str(e)}

def check_kaspi_html():
    """Проверка через HTML парсинг (запасной метод)"""
    logs = []
    logs.append(log_message("Используем HTML парсинг"))
    logs.append(log_message(f"URL: {KASPI_URL}"))
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Cache-Control": "max-age=0",
        "DNT": "1"
    }
    
    try:
        import time
        time.sleep(2)  # Задержка для избежания rate limit
        
        logs.append(log_message("Отправляем запрос..."))
        session = requests.Session()
        session.headers.update(headers)
        
        r = session.get(KASPI_URL, timeout=15, allow_redirects=True)
        logs.append(log_message(f"Статус код: {r.status_code}"))
        
        if r.status_code == 429:
            logs.append(log_message("⚠️ Rate limit (429) - слишком много запросов", "WARNING"))
            return {
                "success": False,
                "in_stock": False,
                "logs": logs,
                "error": "Rate limit exceeded. Try again in 5-10 minutes.",
                "recommendation": "Use longer intervals between checks (5+ minutes)"
            }
        
        if r.status_code != 200:
            return {"success": False, "logs": logs, "error": f"Status code: {r.status_code}"}
        
        from bs4 import BeautifulSoup
        
        logs.append(log_message("Парсим HTML..."))
        soup = BeautifulSoup(r.text, "html.parser")
        
        data_block = soup.find("script", {"type": "application/ld+json"})
        
        if not data_block:
            logs.append(log_message("JSON-блок не найден", "WARNING"))
            return {"success": False, "logs": logs, "error": "JSON block not found"}
        
        data = json.loads(data_block.text)
        
        product_name = data.get("name", "Неизвестный товар")
        offers = data.get("offers", {})
        price = offers.get("price", "Не указана")
        currency = offers.get("priceCurrency", "")
        availability = offers.get("availability", "")
        
        in_stock = "InStock" in availability
        
        logs.append(log_message(f"Товар: {product_name}"))
        logs.append(log_message(f"Цена: {price} {currency}"))
        logs.append(log_message(f"Статус: {availability}"))
        logs.append(log_message("✅ В НАЛИЧИИ!" if in_stock else "❌ Нет в наличии"))
        
        return {
            "success": True,
            "in_stock": in_stock,
            "product_name": product_name,
            "price": f"{price} {currency}",
            "availability": availability,
            "method": "html",
            "logs": logs
        }
        
    except Exception as e:
        logs.append(log_message(f"Ошибка: {str(e)}", "ERROR"))
        return {"success": False, "logs": logs, "error": str(e)}

def check_kaspi_availability():
    """Главная функция с fallback методами"""
    logs = []
    logs.append(log_message("=== Начало проверки товара на Kaspi ==="))
    
    # Пробуем извлечь ID товара
    product_id = extract_product_id(KASPI_URL)
    
    if product_id:
        logs.append(log_message(f"Извлечен ID товара: {product_id}"))
        logs.append(log_message("Метод 1: Пробуем API..."))
        
        result = check_kaspi_api(product_id)
        
        if result.get("success"):
            logs.extend(result.get("logs", []))
            result["logs"] = logs
            
            # Отправляем email если товар в наличии
            if result.get("in_stock") and SEND_EMAIL:
                email_result = send_email_notification(
                    "Товар появился на Kaspi!",
                    f"Товар '{result.get('product_name')}' появился в наличии!\n\nЦена: {result.get('price')}\n\nСсылка: {KASPI_URL}"
                )
                logs.append(log_message(email_result))
                result["logs"] = logs
            
            return result
        
        logs.extend(result.get("logs", []))
        logs.append(log_message("API не сработал, переключаемся на HTML парсинг...", "WARNING"))
    
    # Fallback на HTML парсинг
    logs.append(log_message("Метод 2: Используем HTML парсинг..."))
    result = check_kaspi_html()
    
    all_logs = logs + result.get("logs", [])
    result["logs"] = all_logs
    result["logs_text"] = "".join(all_logs)
    result["url"] = KASPI_URL
    result["timestamp"] = datetime.now().isoformat()
    
    # Отправляем email если товар в наличии
    if result.get("success") and result.get("in_stock") and SEND_EMAIL:
        email_result = send_email_notification(
            "Товар появился на Kaspi!",
            f"Товар '{result.get('product_name')}' появился в наличии!\n\nЦена: {result.get('price')}\n\nСсылка: {KASPI_URL}"
        )
        result["logs"].append(log_message(email_result))
        result["logs_text"] = "".join(result["logs"])
    
    return result

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urlparse(self.path)
        params = parse_qs(parsed_url.query)
        
        provided_key = params.get('key', [None])[0]
        
        if not API_KEY:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                "error": "API_KEY not configured in environment variables",
                "message": "Please set API_KEY in Vercel environment variables"
            }
            self.wfile.write(json.dumps(response, ensure_ascii=False, indent=2).encode())
            return
        
        if provided_key != API_KEY:
            self.send_response(403)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                "error": "Forbidden",
                "message": "Invalid or missing API key. Use: /api/check?key=YOUR_API_KEY"
            }
            self.wfile.write(json.dumps(response, ensure_ascii=False, indent=2).encode())
            return
        
        result = check_kaspi_availability()
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.end_headers()
        
        self.wfile.write(json.dumps(result, ensure_ascii=False, indent=2).encode())
        return
