# api/check.py - Исправленная версия
from http.server import BaseHTTPRequestHandler
import requests
import json
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup

# Переменные окружения
KASPI_URL = os.getenv("KASPI_URL")
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_TO = os.getenv("EMAIL_TO")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
API_KEY = os.getenv("API_KEY")
SCRAPER_API_KEY = os.getenv("SCRAPER_API_KEY")
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

def parse_product_data_from_soup(soup, logs):
    """
    Универсальная функция для извлечения данных о продукте из HTML.
    Ищет правильный JSON-LD блок типа "Product".
    """
    all_data_blocks = soup.find_all("script", {"type": "application/ld+json"})
    
    if not all_data_blocks:
        logs.append(log_message("JSON-LD блоки не найдены на странице", "ERROR"))
        return None

    product_data_json = None
    for block in all_data_blocks:
        try:
            # Используем .string, т.к. .text может объединять несколько тегов
            data = json.loads(block.string)
            # Главное условие: ищем блок, который описывает именно "Product"
            if data.get("@type") == "Product":
                product_data_json = data
                logs.append(log_message("✅ Найден JSON-LD блок с данными о товаре"))
                break 
        except (json.JSONDecodeError, AttributeError):
            # Игнорируем некорректные или пустые JSON-блоки
            continue

    if not product_data_json:
        logs.append(log_message("JSON-LD блок типа 'Product' не найден", "ERROR"))
        return None

    return product_data_json

def check_with_scraper_api():
    """Проверка через ScraperAPI - обходит любую защиту"""
    logs = []
    logs.append(log_message("Используем ScraperAPI для обхода блокировки"))
    
    if not SCRAPER_API_KEY:
        logs.append(log_message("SCRAPER_API_KEY не установлен", "ERROR"))
        return {"success": False, "logs": logs, "error": "ScraperAPI key not configured"}
    
    try:
        api_url = "https://api.scraperapi.com"
        params = { "api_key": SCRAPER_API_KEY, "url": KASPI_URL }
        
        logs.append(log_message("Отправляем запрос через ScraperAPI..."))
        response = requests.get(api_url, params=params, timeout=60)
        logs.append(log_message(f"Статус: {response.status_code}"))
        
        if response.status_code != 200:
            error_text = response.text[:200] if response.text else "No error message"
            logs.append(log_message(f"ScraperAPI error: {error_text}", "ERROR"))
            return {"success": False, "logs": logs, "error": f"ScraperAPI returned {response.status_code}"}
        
        logs.append(log_message("✅ Страница успешно получена, парсим HTML..."))
        soup = BeautifulSoup(response.text, "html.parser")
        
        # === ИЗМЕНЕННАЯ ЛОГИКА ПАРСИНГА ===
        data = parse_product_data_from_soup(soup, logs)
        if not data:
            return {"success": False, "logs": logs, "error": "Не удалось извлечь данные о продукте"}

        product_name = data.get("name", "Неизвестный товар")
        offers = data.get("offers", [])
        price, currency, availability = "Не указана", "", ""

        # Ищем актуальное предложение в списке, так как "offers" - это массив
        for offer in offers:
            if offer.get("@type") == "Offer":
                price = offer.get("price", "Не указана")
                currency = offer.get("priceCurrency", "")
                availability = offer.get("availability", "")
                break # Нашли, выходим

        in_stock = "InStock" in availability
        # ==================================
        
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
        logs.append(log_message("Таймаут запроса к ScraperAPI", "ERROR"))
        return {"success": False, "logs": logs, "error": "ScraperAPI timeout"}
    except Exception as e:
        logs.append(log_message(f"Ошибка: {str(e)}", "ERROR"))
        return {"success": False, "logs": logs, "error": str(e)}

def check_direct():
    """Прямой запрос (запасной метод)"""
    logs = []
    logs.append(log_message(f"Прямой запрос к Kaspi"))
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    
    try:
        session = requests.Session()
        session.headers.update(headers)
        
        logs.append(log_message("Отправляем запрос..."))
        r = session.get(KASPI_URL, timeout=20, allow_redirects=True)
        logs.append(log_message(f"Статус: {r.status_code}"))
        
        if r.status_code != 200:
            return {"success": False, "logs": logs, "error": f"Статус {r.status_code}"}
        
        soup = BeautifulSoup(r.text, "html.parser")
        
        # === ИЗМЕНЕННАЯ ЛОГИКА ПАРСИНГА ===
        data = parse_product_data_from_soup(soup, logs)
        if not data:
            return {"success": False, "logs": logs, "error": "Не удалось извлечь данные о продукте"}

        product_name = data.get("name", "Неизвестный товар")
        offers = data.get("offers", [])
        price, currency, availability = "Не указана", "", ""

        for offer in offers:
            if offer.get("@type") == "Offer":
                price = offer.get("price", "Не указана")
                currency = offer.get("priceCurrency", "")
                availability = offer.get("availability", "")
                break
        
        in_stock = "InStock" in availability
        # ==================================
        
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
    
    result = None
    if USE_SCRAPER_API and SCRAPER_API_KEY:
        logs.append(log_message("Метод: ScraperAPI"))
        result = check_with_scraper_api()
    else:
        logs.append(log_message("Метод: Прямой запрос"))
        result = check_direct()
    
    all_logs = logs + result.get("logs", [])
    result["logs"] = all_logs
    result["logs_text"] = "".join(all_logs)
    result["url"] = KASPI_URL
    result["timestamp"] = datetime.now().isoformat()
    
    if result.get("success") and result.get("in_stock") and SEND_EMAIL:
        email_result = send_email_notification(
            "🎉 Товар появился на Kaspi!",
            f"Товар '{result.get('product_name')}' теперь в наличии!\n\nЦена: {result.get('price')}\n\nСсылка: {KASPI_URL}"
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
            self.wfile.write(json.dumps({"error": "API_KEY not configured"}, ensure_ascii=False).encode())
            return
        
        if provided_key != API_KEY:
            self.send_response(403)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid API key"}, ensure_ascii=False).encode())
            return
        
        result = check_kaspi_availability()
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(result, ensure_ascii=False, indent=2).encode())
        return
