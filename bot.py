import datetime
import os
import time
import requests

# Lê as credenciais das Variáveis de Ambiente do Render
EBAY_CLIENT_ID = os.environ.get("EBAY_CLIENT_ID", "").strip()
EBAY_CLIENT_SECRET = os.environ.get("EBAY_CLIENT_SECRET", "").strip()
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

SEARCH_KEYWORDS = "(Panini, Topps) soccer (autograph, auto)"
CATEGORY_ID = "212"
ALERT_THRESHOLD_MINUTES = 30

notified_items = set()


def get_ebay_access_token():
    url = "https://api.ebay.com/identity/v1/oauth2/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "client_credentials",
        "scope": "https://api.ebay.com/oauth/api_scope",
    }
    response = requests.post(
        url,
        headers=headers,
        data=data,
        auth=(EBAY_CLIENT_ID, EBAY_CLIENT_SECRET),
    )
    if response.status_code == 200:
        return response.json().get("access_token")
    return None


def send_telegram_alert(
    item_title, price, currency, shipping_str, end_time_str, item_url
):
    message = (
        f"✍️ **CARD AUTOGRAFADO (TOPPS/PANINI)**\n"
        f"🚨 **LEILÃO ENCERRANDO EM BREVE!**\n\n"
        f"⚽ **Item:** {item_title}\n"
        f"💰 **Lance Atual:** {currency} {price}\n"
        f"📦 **Frete Estimado (BR):** {shipping_str}\n"
        f"⏱️ **Término:** {end_time_str} UTC\n\n"
        f"🔗 [Ver Leilão no eBay]({item_url})"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
    }
    requests.post(url, json=payload)


def check_auctions(token):
    url = "https://api.ebay.com/buy/browse/v1/item_summary/search"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
        "X-EBAY-C-ENDUSERCTX": "contextualLocation=country=BR",
    }
    params = {
        "q": SEARCH_KEYWORDS,
        "category_ids": CATEGORY_ID,
        "filter": "buyingOptions:{AUCTION}",
        "sort": "endingSoonest",
        "limit": 50,
    }

    res = requests.get(url, headers=headers, params=params)
    if res.status_code == 200:
        items = res.json().get("itemSummaries", [])
        now_utc = datetime.datetime.now(datetime.timezone.utc)

        for item in items:
            item_id = item.get("itemId")
            if item_id in notified_items:
                continue

            shipping_options = item.get("shippingOptions", [])
            if shipping_options:
                cost_info = shipping_options[0].get("shippingCost", {})
                val = cost_info.get("value")
                curr = cost_info.get("currency", "USD")
                shipping_str = (
                    f"{curr} {val}" if val is not None else "Calcular no site"
                )
            else:
                shipping_str = "Não especificado"

            item_end_str = item.get("itemEndDate")
            if not item_end_str:
                continue

            end_datetime = datetime.datetime.fromisoformat(
                item_end_str.replace("Z", "+00:00")
            )
            minutes_remaining = (end_datetime - now_utc).total_seconds() / 60.0

            if 0 < minutes_remaining <= ALERT_THRESHOLD_MINUTES:
                title = item.get("title", "Card de Futebol Autografado")
                price_info = item.get("price", {})
                price = price_info.get("value", "0")
                currency = price_info.get("currency", "USD")
                item_url = item.get("itemWebUrl", "")
                formatted_end_time = end_datetime.strftime("%H:%M:%S (%d/%m)")

                send_telegram_alert(
                    title,
                    price,
                    currency,
                    shipping_str,
                    formatted_end_time,
                    item_url,
                )
                notified_items.add(item_id)


if __name__ == "__main__":
    print("🤖 Bot iniciado no Render 24/7!")
    access_token = get_ebay_access_token()

    if access_token:
        token_fetch_time = time.time()
        while True:
            if time.time() - token_fetch_time > 5400:
                access_token = get_ebay_access_token()
                token_fetch_time = time.time()

            check_auctions(access_token)
            time.sleep(300)
