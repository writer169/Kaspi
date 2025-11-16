# api/check.py - Версия со ScraperAPI
from http.server import BaseHTTPRequestHandler
import requests
import json
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from urllib.parse import urlparse, parse_qs, quote
from bs4 import BeautifulSoup

# Переменные окружения
KASPI_URL = os.getenv("KASPI_URL")
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_TO = os.getenv("EMAIL_TO")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
API_KEY = os.getenv("API_KEY")
SCRAPER_API_KEY = os.getenv("SCRAPER_API_KEY")  # Новая переменная!
SEND_EMAIL = os.getenv("SEND_EMAIL", "true").lower() == "true"
USE_SCRAPER_API = os.getenv("USE_SCRAPER_API", "true").lower() == "true"

def log_message(message, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"[{timestamp}] [{level}] {message}\n"

def send_email_notification(subject, body):
    if not SEND_EMAIL or not all([EMAIL_FROM, EMAIL_TO, EMAIL_PASSWORD]):
        return "Email отключен или не настроен"
    
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = EMAIL_FROM
        msg["To"] = EMAIL_TO
        
        html_body = f"""
        <html>
          <body style="font-family: Arial, sans-serif; padding: 20px;">
            <h2 style="color: #4CAF50;">🎉 {subject}</h2>
            <p style="font-size: 16px;">{body}</p>
            <hr style="margin: 20px 0;">
            <p>
              <a href="{KASPI_URL}" 
                 style="background-color: #4CAF50; color: white; 
                        padding: 12px 24px; text-decoration: none; 
                        border-radius: 5px; display: inline-block;">
                Открыть на Kaspi.kz
              </a>
            </p>
            <p style="color: #666; font-size: 12px; margin-top: 20px;">
              {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            </p>
          </body>
        </html>
        """
        
        msg.attach(MIMEText(body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))
        
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(EMAIL_FROM, EMAIL_PASSWORD)
        server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())
        server.quit()
        
        return "✅ Email отправлен"
    except Exception as e:
        return f"❌ Ошибка email: {str(e)}"

def check_with_scraper_api():
    """Проверка через ScraperAPI - обходит любую защиту"""
    logs = []
    logs.append(log_message("Используем ScraperAPI для обхода блокировки"))
    
    if not SCRAPER_API_KEY:
        logs.append(log_message("SCRAPER_API_KEY не установлен", "ERROR"))
        return {"success": False, "logs": logs, "error": "ScraperAPI key not configured"}
    
    try:
        # ScraperAPI - используем только бесплатные параметры!
        api_url = "https://api.scraperapi.com"
        
        # Только базовые параметры для FREE плана
        params = {
            "api_key": SCRAPER_API_KEY,
            "url": KASPI_URL
            # НЕ используем: render, country_code, premium_proxy и др.
        }
        
        logs.append(log_message(f"Отправляем запрос через ScraperAPI (FREE plan)..."))
        logs.append(log_message(f"API Key preview: {SCRAPER_API_KEY[:10]}***"))
        logs.append(log_message(f"Target URL: {KASPI_URL}"))
        
        response = requests.get(api_url, params=params, timeout=60)
        logs.append(log_message(f"Статус: {response.status_code}"))
        
        if response.status_code == 403:
            logs.append(log_message("⚠️ Ошибка 403 - проблема с API ключом", "ERROR"))
            logs.append(log_message("Проверьте:", "ERROR"))
            logs.append(log_message("1. Правильность API ключа", "ERROR"))
            logs.append(log_message("2. Наличие credits в аккаунте", "ERROR"))
            logs.append(log_message("3. https://dashboard.scraperapi.com/", "ERROR"))
            return {"success": False, "logs": logs, "error": "Invalid ScraperAPI key or no credits"}
        
        if response.status_code == 422:
            logs.append(log_message("⚠️ Ошибка 422 - некорректный запрос", "ERROR"))
            return {"success": False, "logs": logs, "error": "Invalid request parameters"}
        
        if response.status_code != 200:
            error_text = response.text[:300] if response.text else "No error message"
            logs.append(log_message(f"ScraperAPI error: {error_text}", "ERROR"))
            return {"success": False, "logs": logs, "error": f"ScraperAPI returned {response.status_code}"}
        
        logs.append(log_message("✅ Страница успешно получена"))
        logs.append(log_message(f"Размер ответа: {len(response.text)} байт"))
        logs.append(log_message("Парсим HTML..."))
        
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Ищем JSON-LD данные
        data_block = soup.find("script", {"type": "application/ld+json"})
        
        if not data_block:
            logs.append(log_message("JSON-блок не найден, пробуем альтернативные методы...", "WARNING"))
            
            # Альтернатива 1: Meta теги
            title = soup.find("meta", {"property": "og:title"})
            price_meta = soup.find("meta", {"property": "product:price:amount"})
            
            if title:
                product_name = title.get("content", "Неизвестный товар")
                logs.append(log_message(f"Найден товар через meta: {product_name}"))
                
                # Пробуем найти информацию о наличии
                availability_text = "Неизвестно"
                # Ищем кнопку "Купить" или текст "В наличии"
                buy_button = soup.find("button", {"data-role": "add-to-cart"})
                if buy_button:
                    availability_text = "В наличии"
                    in_stock = True
                else:
                    in_stock = False
                
                return {
                    "success": True,
                    "in_stock": in_stock,
                    "product_name": product_name,
                    "price": price_meta.get("content") if price_meta else "Не указана",
                    "availability": availability_text,
                    "method": "scraperapi-meta",
                    "logs": logs
                }
            
            return {"success": False, "logs": logs, "error": "Could not find product data"}
        
        logs.append(log_message("JSON-блок найден, парсим..."))
        data = json.loads(data_block.text)
        
        product_name = data.get("name", "Неизвестный товар")
        offers = data.get("offers", {})
        price = offers.get("price", "Не указана")
        currency = offers.get("priceCurrency", "")
        availability = offers.get("availability", "")
        
        in_stock = "InStock" in availability
        
        logs.append(log_message(f"📦 Товар: {product_name}"))
        logs.append(log_message(f"💰 Цена: {price} {currency}"))
        logs.append(log_message(f"📊 Статус: {availability}"))
        
        if in_stock:
            logs.append(log_message("✅ ТОВАР В НАЛИЧИИ!", "SUCCESS"))
        else:
            logs.append(log_message("❌ Товара нет в наличии", "INFO"))
        
        return {
            "success": True,
            "in_stock": in_stock,
            "product_name": product_name,
            "price": f"{price} {currency}",
            "availability": availability,
            "method": "scraperapi",
            "logs": logs
        }
        
    except requests.exceptions.Timeout:
        logs.append(log_message("Таймаут запроса к ScraperAPI (60 сек)", "ERROR"))
        return {"success": False, "logs": logs, "error": "ScraperAPI timeout"}
    except json.JSONDecodeError as e:
        logs.append(log_message(f"Ошибка парсинга JSON: {str(e)}", "ERROR"))
        return {"success": False, "logs": logs, "error": "JSON parse error"}
    except Exception as e:
        logs.append(log_message(f"Ошибка: {str(e)}", "ERROR"))
        return {"success": False, "logs": logs, "error": str(e)}

def check_direct(retry_count=0):
    """Прямой запрос с улучшенными headers (запасной метод)"""
    logs = []
    logs.append(log_message(f"Прямой запрос к Kaspi (попытка {retry_count + 1})"))
    
    # Максимально реалистичные headers
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
        "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"'
    }
    
    try:
        import time
        if retry_count > 0:
            wait_time = retry_count * 5
            logs.append(log_message(f"Ожидание {wait_time} секунд перед повторной попыткой..."))
            time.sleep(wait_time)
        else:
            time.sleep(2)
        
        session = requests.Session()
        session.headers.update(headers)
        
        logs.append(log_message("Отправляем запрос..."))
        r = session.get(KASPI_URL, timeout=20, allow_redirects=True)
        logs.append(log_message(f"Статус: {r.status_code}"))
        
        if r.status_code == 429:
            if retry_count < 2:
                logs.append(log_message("Rate limit, повторяем через 5 сек...", "WARNING"))
                return check_direct(retry_count + 1)
            else:
                logs.append(log_message("⚠️ Rate limit после нескольких попыток", "ERROR"))
                return {"success": False, "logs": logs, "error": "Rate limit exceeded after retries"}
        
        if r.status_code == 403:
            logs.append(log_message("❌ Доступ запрещен (403)", "ERROR"))
            return {"success": False, "logs": logs, "error": "Access forbidden (403)"}
        
        if r.status_code != 200:
            return {"success": False, "logs": logs, "error": f"Status {r.status_code}"}
        
        soup = BeautifulSoup(r.text, "html.parser")
        data_block = soup.find("script", {"type": "application/ld+json"})
        
        if not data_block:
            return {"success": False, "logs": logs, "error": "JSON block not found"}
        
        data = json.loads(data_block.text)
        product_name = data.get("name", "Неизвестный товар")
        offers = data.get("offers", {})
        price = offers.get("price", "")
        currency = offers.get("priceCurrency", "")
        availability = offers.get("availability", "")
        in_stock = "InStock" in availability
        
        logs.append(log_message(f"Товар: {product_name}"))
        logs.append(log_message(f"Цена: {price} {currency}"))
        logs.append(log_message("✅ В наличии" if in_stock else "❌ Нет в наличии"))
        
        return {
            "success": True,
            "in_stock": in_stock,
            "product_name": product_name,
            "price": f"{price} {currency}",
            "availability": availability,
            "method": "direct",
            "logs": logs
        }
        
    except Exception as e:
        logs.append(log_message(f"Ошибка: {str(e)}", "ERROR"))
        return {"success": False, "logs": logs, "error": str(e)}

def check_kaspi_availability():
    """Главная функция с выбором метода"""
    logs = []
    logs.append(log_message("=== KASPI MONITOR START ==="))
    logs.append(log_message(f"URL: {KASPI_URL}"))
    
    result = None
    
    # Приоритет 1: ScraperAPI (если включен и настроен)
    if USE_SCRAPER_API and SCRAPER_API_KEY:
        logs.append(log_message("Метод: ScraperAPI (обход блокировок)"))
        result = check_with_scraper_api()
    else:
        logs.append(log_message("ScraperAPI отключен или не настроен", "WARNING"))
        logs.append(log_message("Метод: Прямой запрос"))
        result = check_direct()
    
    # Объединяем логи
    all_logs = logs + result.get("logs", [])
    result["logs"] = all_logs
    result["logs_text"] = "".join(all_logs)
    result["url"] = KASPI_URL
    result["timestamp"] = datetime.now().isoformat()
    
    # Отправляем email если товар в наличии
    if result.get("success") and result.get("in_stock") and SEND_EMAIL:
        email_result = send_email_notification(
            "🎉 Товар появился на Kaspi!",
            f"Товар '{result.get('product_name')}' теперь в наличии!\n\nЦена: {result.get('price')}\n\nСсылка: {KASPI_URL}"
        )
        result["logs"].append(log_message(email_result))
        result["logs_text"] = "".join(result["logs"])
        result["email_sent"] = "sent" in email_result
    
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
            response = {"error": "API_KEY not configured"}
            self.wfile.write(json.dumps(response, ensure_ascii=False, indent=2).encode())
            return
        
        if provided_key != API_KEY:
            self.send_response(403)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {"error": "Invalid API key"}
            self.wfile.write(json.dumps(response, ensure_ascii=False, indent=2).encode())
            return
        
        result = check_kaspi_availability()
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(result, ensure_ascii=False, indent=2).encode())
        return
