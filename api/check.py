# api/check.py
from http.server import BaseHTTPRequestHandler
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from urllib.parse import urlparse, parse_qs

# Получаем настройки из переменных окружения Vercel
KASPI_URL = os.getenv("KASPI_URL", "https://kaspi.kz/shop/p/ehrmann-puding-vanil-bezlaktoznyi-1-5-200-g-102110634/?c=750000000")
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_TO = os.getenv("EMAIL_TO")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
API_KEY = os.getenv("API_KEY")  # Секретный ключ для защиты эндпоинта
SEND_EMAIL = os.getenv("SEND_EMAIL", "true").lower() == "true"

def log_message(message, level="INFO"):
    """Форматированный лог"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"[{timestamp}] [{level}] {message}\n"

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
        
        # Текстовая версия
        text_body = body
        
        # HTML версия
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

def check_kaspi_availability():
    """Проверка наличия товара на Kaspi"""
    logs = []
    logs.append(log_message("Начинаем проверку наличия товара..."))
    logs.append(log_message(f"URL: {KASPI_URL}"))
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        logs.append(log_message("Отправляем запрос на Kaspi.kz..."))
        r = requests.get(KASPI_URL, headers=headers, timeout=15)
        logs.append(log_message(f"Статус код: {r.status_code}"))
        
        if r.status_code != 200:
            logs.append(log_message(f"Неожиданный статус код: {r.status_code}", "ERROR"))
            return {
                "success": False,
                "in_stock": False,
                "logs": logs,
                "error": f"Status code: {r.status_code}"
            }
        
        logs.append(log_message("Парсим HTML..."))
        soup = BeautifulSoup(r.text, "html.parser")
        
        logs.append(log_message("Ищем JSON-блок..."))
        data_block = soup.find("script", {"type": "application/ld+json"})
        
        if not data_block:
            logs.append(log_message("JSON-блок не найден", "WARNING"))
            return {
                "success": False,
                "in_stock": False,
                "logs": logs,
                "error": "JSON block not found"
            }
        
        logs.append(log_message("Парсим JSON данные..."))
        data = json.loads(data_block.text)
        
        product_name = data.get("name", "Неизвестный товар")
        logs.append(log_message(f"Товар: {product_name}"))
        
        offers = data.get("offers", {})
        price = offers.get("price", "Не указана")
        currency = offers.get("priceCurrency", "")
        logs.append(log_message(f"Цена: {price} {currency}"))
        
        availability = offers.get("availability", "")
        logs.append(log_message(f"Статус: {availability}"))
        
        in_stock = "InStock" in availability
        
        if in_stock:
            logs.append(log_message("✅ ТОВАР В НАЛИЧИИ!", "SUCCESS"))
            
            # Отправляем email
            if SEND_EMAIL:
                email_result = send_email_notification(
                    "Товар появился на Kaspi!",
                    f"Товар '{product_name}' появился в наличии!\n\nЦена: {price} {currency}\n\nСсылка: {KASPI_URL}"
                )
                logs.append(log_message(email_result))
        else:
            logs.append(log_message("❌ Товара нет в наличии", "INFO"))
        
        return {
            "success": True,
            "in_stock": in_stock,
            "product_name": product_name,
            "price": f"{price} {currency}",
            "availability": availability,
            "url": KASPI_URL,
            "logs": logs,
            "timestamp": datetime.now().isoformat()
        }
        
    except requests.exceptions.Timeout:
        logs.append(log_message("Таймаут запроса", "ERROR"))
        return {"success": False, "in_stock": False, "logs": logs, "error": "Timeout"}
    except Exception as e:
        logs.append(log_message(f"Ошибка: {str(e)}", "ERROR"))
        return {"success": False, "in_stock": False, "logs": logs, "error": str(e)}

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Парсим URL и параметры
        parsed_url = urlparse(self.path)
        params = parse_qs(parsed_url.query)
        
        # Проверяем API ключ
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
        
        # Проверяем наличие товара
        result = check_kaspi_availability()
        
        # Формируем ответ
        self.send_response(200)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.end_headers()
        
        # Добавляем логи в читаемом виде
        result["logs_text"] = "".join(result.get("logs", []))
        
        self.wfile.write(json.dumps(result, ensure_ascii=False, indent=2).encode())
        return
