import os
import re
import json
import logging
import requests
from flask import Flask, request, jsonify

# ============================================
# LOGGING
# ============================================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================
# GET ENVIRONMENT VARIABLES
# ============================================
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
EXCHANGE_API_KEY = os.environ.get("EXCHANGE_API_KEY", "free")
PORT = int(os.environ.get("PORT", 8080))

# Log the status
if TELEGRAM_TOKEN:
    logger.info("✅ TELEGRAM_TOKEN found!")
else:
    logger.error("❌ TELEGRAM_TOKEN NOT SET! Please add it to Railway variables.")

# ============================================
# CONSTANTS
# ============================================
EXCHANGE_API_URL = "https://api.exchangerate-api.com/v4/latest/"

SUPPORTED_CURRENCIES = {
    "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "AUD": "A$",
    "CAD": "C$", "CHF": "Fr", "CNY": "¥", "INR": "₹", "BRL": "R$",
    "ZAR": "R", "NZD": "NZ$", "KRW": "₩", "SGD": "S$", "MXN": "Mex$",
    "HKD": "HK$", "RUB": "₽", "TRY": "₺", "AED": "د.إ", "SAR": "﷼",
    "NGN": "₦", "KES": "KSh", "GHS": "GH₵", "EGP": "E£", "MAD": "د.م.",
    "DZD": "دج", "TND": "د.ت", "LKR": "Rs", "BDT": "৳", "PKR": "₨",
    "PHP": "₱", "THB": "฿", "VND": "₫", "IDR": "Rp", "MYR": "RM"
}

# ============================================
# HELPER FUNCTIONS
# ============================================

def get_exchange_rates(base_currency="USD"):
    """Fetch live exchange rates."""
    try:
        url = f"{EXCHANGE_API_URL}{base_currency}"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return data.get("rates", {})
        else:
            logger.error(f"API Error: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"API Error: {str(e)}")
        return None

def parse_convert_input(text):
    """Parse conversion input."""
    patterns = [
        r'^(\d+\.?\d*)\s+([A-Za-z]{3})\s+(?:to|in|into|->|=>)\s+([A-Za-z]{3})$',
        r'^(\d+\.?\d*)\s+([A-Za-z]{3})\s*[/=]\s*([A-Za-z]{3})$',
        r'^convert\s+(\d+\.?\d*)\s+([A-Za-z]{3})\s+(?:to|in|into)\s+([A-Za-z]{3})$',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            amount = float(match.group(1))
            from_cur = match.group(2).upper()
            to_cur = match.group(3).upper()
            return amount, from_cur, to_cur
    return None

def format_currency(amount, currency_code):
    """Format amount with currency symbol."""
    symbol = SUPPORTED_CURRENCIES.get(currency_code, "")
    return f"{symbol}{amount:,.2f}" if symbol else f"{amount:.2f} {currency_code}"

def perform_conversion(amount, from_currency, to_currency):
    """Perform currency conversion."""
    if from_currency not in SUPPORTED_CURRENCIES:
        return None, f"Currency {from_currency} not supported"
    if to_currency not in SUPPORTED_CURRENCIES:
        return None, f"Currency {to_currency} not supported"
    
    if from_currency == to_currency:
        return amount, 1.0, 1.0
    
    rates = get_exchange_rates(from_currency)
    if not rates:
        return None, "Failed to fetch exchange rates"
    
    if to_currency not in rates:
        return None, f"Rate for {to_currency} not found"
    
    rate = rates[to_currency]
    converted_amount = amount * rate
    inverse_rate = 1 / rate if rate != 0 else 0
    
    return converted_amount, rate, inverse_rate

def send_telegram_message(chat_id, text, parse_mode="Markdown"):
    """Send message to Telegram."""
    if not TELEGRAM_TOKEN:
        logger.error("Cannot send message: TELEGRAM_TOKEN not set")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode
    }
    
    try:
        response = requests.post(url, json=data, timeout=10)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Failed to send message: {str(e)}")
        return False

def get_currency_list_text():
    """Get formatted currency list."""
    currencies = sorted(SUPPORTED_CURRENCIES.keys())
    chunks = [currencies[i:i+10] for i in range(0, len(currencies), 10)]
    text = f"📋 *Supported Currencies ({len(currencies)} total)*\n\n"
    for chunk in chunks:
        text += "• " + " • ".join([f"`{c}`" for c in chunk]) + "\n"
    return text

# ============================================
# TELEGRAM WEBHOOK HANDLER
# ============================================

def handle_telegram_update(update_data):
    """Process incoming Telegram updates."""
    try:
        if "message" not in update_data:
            return
        
        message = update_data["message"]
        chat_id = message["chat"]["id"]
        text = message.get("text", "").strip()
        
        if not text:
            return
        
        logger.info(f"Received message from {chat_id}: {text}")
        
        # Handle commands
        if text.startswith("/"):
            command = text.split()[0].lower()
            
            if command == "/start":
                response = (
                    "💰 *Welcome to Currency66 Converter Bot!*\n\n"
                    "I convert currencies using live exchange rates.\n\n"
                    "*Quick Examples:*\n"
                    "• `100 USD to EUR`\n"
                    "• `5000 NGN in USD`\n"
                    "• `convert 200 GBP to JPY`\n\n"
                    "*Commands:*\n"
                    "/convert - Convert currency\n"
                    "/rates - Show exchange rates\n"
                    "/list - Show all currencies\n"
                    "/help - Show help"
                )
                send_telegram_message(chat_id, response)
                
            elif command == "/help":
                response = (
                    "❓ *How to Use*\n\n"
                    "*Commands:*\n"
                    "• `/start` - Welcome\n"
                    "• `/convert 100 USD to EUR` - Convert\n"
                    "• `/rates USD` - Show rates\n"
                    "• `/list` - All currencies\n\n"
                    "*Quick Convert:*\n"
                    "`100 USD to EUR`\n"
                    "`50 EUR in GBP`\n"
                    "`25 USD -> NGN`"
                )
                send_telegram_message(chat_id, response)
                
            elif command == "/convert":
                parts = text.split()[1:]
                if len(parts) >= 4:
                    try:
                        amount = float(parts[0])
                        from_cur = parts[1].upper()
                        to_cur = parts[3].upper()
                        
                        result = perform_conversion(amount, from_cur, to_cur)
                        if result[0] is None:
                            response = f"❌ {result[1]}"
                        else:
                            converted, rate, inverse = result
                            response = (
                                f"💱 *Conversion*\n\n"
                                f"{format_currency(amount, from_cur)} = {format_currency(converted, to_cur)}\n\n"
                                f"📈 1 {from_cur} = {rate:.4f} {to_cur}\n"
                                f"🔄 1 {to_cur} = {inverse:.4f} {from_cur}"
                            )
                        send_telegram_message(chat_id, response)
                    except:
                        send_telegram_message(chat_id, "❌ Invalid format. Use: /convert 100 USD to EUR")
                else:
                    send_telegram_message(chat_id, "❌ Usage: /convert <amount> <from> to <to>")
                    
            elif command == "/rates":
                parts = text.split()
                if len(parts) >= 2:
                    base = parts[1].upper()
                    if base not in SUPPORTED_CURRENCIES:
                        send_telegram_message(chat_id, f"❌ {base} not supported. Use /list")
                        return
                    
                    rates = get_exchange_rates(base)
                    if not rates:
                        send_telegram_message(chat_id, "❌ Failed to fetch rates")
                        return
                    
                    response = f"📊 *Rates (Base: {base})*\n\n"
                    top = ["USD", "EUR", "GBP", "JPY", "NGN", "INR", "CNY", "CAD", "AUD", "CHF"]
                    count = 0
                    for cur in top:
                        if cur in rates and cur != base:
                            response += f"• {cur}: `{rates[cur]:.4f}`\n"
                            count += 1
                    response += f"\n_Showing {count} major currencies_"
                    send_telegram_message(chat_id, response)
                else:
                    send_telegram_message(chat_id, "❌ Usage: /rates USD")
                    
            elif command == "/list":
                response = get_currency_list_text()
                send_telegram_message(chat_id, response)
            else:
                send_telegram_message(chat_id, "❌ Unknown command. Send /help")
            return
        
        # Quick conversion
        parsed = parse_convert_input(text)
        if parsed:
            amount, from_cur, to_cur = parsed
            result = perform_conversion(amount, from_cur, to_cur)
            if result[0] is None:
                response = f"❌ {result[1]}"
            else:
                converted, rate, inverse = result
                response = (
                    f"💱 *Conversion*\n\n"
                    f"{format_currency(amount, from_cur)} = {format_currency(converted, to_cur)}\n\n"
                    f"📈 1 {from_cur} = {rate:.4f} {to_cur}\n"
                    f"🔄 1 {to_cur} = {inverse:.4f} {from_cur}"
                )
            send_telegram_message(chat_id, response)
            return
        
        # Check if just a currency code
        if text.upper() in SUPPORTED_CURRENCIES:
            base = text.upper()
            rates = get_exchange_rates(base)
            if rates:
                response = f"📊 *Rates (Base: {base})*\n\n"
                top = ["USD", "EUR", "GBP", "JPY", "NGN", "INR"]
                for cur in top:
                    if cur in rates and cur != base:
                        response += f"• {cur}: `{rates[cur]:.4f}`\n"
                send_telegram_message(chat_id, response)
            return
        
        # No match
        response = (
            "❓ I didn't understand.\n\n"
            "*Try:*\n"
            "• `100 USD to EUR`\n"
            "• `5000 NGN in USD`\n"
            "• `/rates USD`\n"
            "• `/list`\n\n"
            "Send /help for more info."
        )
        send_telegram_message(chat_id, response)
        
    except Exception as e:
        logger.error(f"Error handling update: {str(e)}")

# ============================================
# FLASK APP
# ============================================

app = Flask(__name__)

@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "bot": "Currency66 Converter Bot",
        "token_set": bool(TELEGRAM_TOKEN),
        "version": "2.0.0",
        "python_version": "3.13"
    })

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle webhook from Telegram."""
    if not TELEGRAM_TOKEN:
        return jsonify({"error": "TELEGRAM_TOKEN not set"}), 500
    
    try:
        update_data = request.get_json()
        if update_data:
            logger.info("Received webhook update")
            handle_telegram_update(update_data)
            return jsonify({"status": "ok"}), 200
        return jsonify({"error": "No data"}), 400
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/setwebhook', methods=['GET'])
def set_webhook():
    """Set the webhook URL."""
    if not TELEGRAM_TOKEN:
        return jsonify({"error": "TELEGRAM_TOKEN not set"}), 500
    
    webhook_url = f"https://{request.host}/webhook"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={webhook_url}"
    
    try:
        response = requests.get(url)
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ============================================
# MAIN
# ============================================

if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("Starting Currency66 Converter Bot (Python 3.13)")
    logger.info("=" * 50)
    
    if not TELEGRAM_TOKEN:
        logger.error("❌❌❌ CRITICAL ERROR ❌❌❌")
        logger.error("TELEGRAM_TOKEN is NOT set in environment variables!")
        logger.error("Please add TELEGRAM_TOKEN to Railway variables")
    
    logger.info(f"PORT: {PORT}")
    logger.info(f"EXCHANGE_API_KEY: {EXCHANGE_API_KEY}")
    logger.info(f"TELEGRAM_TOKEN: {'✅ SET' if TELEGRAM_TOKEN else '❌ NOT SET'}")
    logger.info("=" * 50)
    
    app.run(host='0.0.0.0', port=PORT)
