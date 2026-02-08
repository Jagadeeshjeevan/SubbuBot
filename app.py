import os
import logging
from flask import Flask, request, jsonify
import requests
from dotenv import load_dotenv

load_dotenv()

APP = Flask(__name__)
logging.basicConfig(level=logging.INFO)

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "verify_token")
WELCOME_MEDIA_URL = os.getenv("WELCOME_MEDIA_URL")

SEEN_SENDERS = set()

USER_STATE = {}

try:
    import emoji
    em = lambda s: emoji.emojize(s, language='alias')
except Exception:
    em = lambda s: s


def send_text_message(to: str, text: str) -> requests.Response:
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "text": {"body": text},
    }
    resp = requests.post(url, headers=headers, json=payload)
    logging.info("Sent message to %s, status=%s", to, resp.status_code)
    return resp


def send_media_message(to: str, link: str, media_type: str = "image", caption: str = None) -> requests.Response:
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    media_obj = {"link": link}
    if caption:
        media_obj["caption"] = caption
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": media_type,
        media_type: media_obj,
    }
    resp = requests.post(url, headers=headers, json=payload)
    logging.info("Sent %s to %s status=%s", media_type, to, resp.status_code)
    return resp


def send_media_message(to: str, link: str, media_type: str = "image", caption: str = None) -> requests.Response:
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    media_field = {media_type: {"link": link}}
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": media_type,
        **({ "caption": caption } if caption and media_type == "image" else {}),
    }
    # payload must include the media object under the media type key
    payload[media_type] = media_field[media_type]
    return requests.post(url, headers=headers, json=payload)


def send_interactive_buttons(to: str) -> requests.Response:
    """Send an interactive button message with 3 service choices."""
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": "Welcome to SubbuBot! Please select a service:"},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": "service_car_wash", "title": "1. Car wash"}},
                    {"type": "reply", "reply": {"id": "service_painting", "title": "2. Painting"}},
                    {"type": "reply", "reply": {"id": "service_led", "title": "3. LED"}},
                ]
            }
        }
    }
    resp = requests.post(url, headers=headers, json=payload)
    logging.info("Sent interactive buttons to %s status=%s", to, resp.status_code)
    return resp


@APP.route("/webhook", methods=["GET"])
def verify_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    logging.info("Webhook received: %s", request)
    print(request)
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Verification token mismatch", 403


@APP.route("/webhook", methods=["POST"])
def receive_webhook():
    data = request.get_json()
    logging.info("Webhook received: %s", data)

    if data and data.get("entry"):
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages") or []
                for message in messages:
                    from_phone = message.get("from")
                    if not from_phone:
                        continue

                    # Extract text or button/list reply payload if present
                    text = ""
                    payload_reply = None
                    mtype = message.get("type")
                    if mtype == "text":
                        text = message.get("text", {}).get("body", "").strip()
                    elif mtype == "button":
                        # older payload format
                        btn = message.get("button", {})
                        payload_reply = btn.get("payload") or btn.get("text")
                    elif mtype == "interactive":
                        interactive = message.get("interactive", {})
                        # button_reply or list_reply
                        br = interactive.get("button_reply") or interactive.get("list_reply")
                        if br:
                            payload_reply = br.get("id") or br.get("title") or br.get("reply")

                    # New sender or greeting: send welcome menu and set awaiting state
                    text_norm = text.lower()
                    is_greeting = any(g in text_norm for g in ("hi", "hello", "hey"))
                    if from_phone not in SEEN_SENDERS or is_greeting:
                        welcome = em(
                            ":sparkles: Welcome to SubbuBot! :sparkles:\n\n"
                            "Please select the specific service:\n"
                            "1️⃣  Car wash\n"
                            "2️⃣  Painting\n"
                            "3️⃣  💡 LED"
                        )
                        # If a welcome media URL is configured, send it first (animated GIF/MP4)
                        if WELCOME_MEDIA_URL:
                            try:
                                send_media_message(from_phone, WELCOME_MEDIA_URL, media_type="image", caption="Welcome to SubbuBot")
                            except Exception:
                                logging.exception("Failed to send welcome media")
                        # Send interactive buttons for selection (preferred UX)
                        try:
                            send_interactive_buttons(from_phone)
                        except Exception:
                            logging.exception("Failed to send interactive buttons, falling back to text menu")
                            send_text_message(from_phone, welcome)
                        SEEN_SENDERS.add(from_phone)
                        USER_STATE[from_phone] = "AWAITING_SELECTION"
                        continue

                    # Check user state and interpret selection (support button payloads and text)
                    state = USER_STATE.get(from_phone)
                    choice = None
                    if payload_reply:
                        choice = payload_reply.lower()
                    else:
                        choice = text.lower()

                    if state == "AWAITING_SELECTION":
                        if choice in ("1", "1. car wash", "car wash", "service_car_wash"):
                            send_text_message(from_phone, "You selected: Car wash. We'll contact you shortly.")
                            USER_STATE.pop(from_phone, None)
                        elif choice in ("2", "2. painting", "painting", "service_painting"):
                            send_text_message(from_phone, "You selected: Painting. We'll share options soon.")
                            USER_STATE.pop(from_phone, None)
                        elif choice in ("3", "3. led", "led", "service_led"):
                            send_text_message(from_phone, "You selected: LED. We'll share packages soon.")
                            USER_STATE.pop(from_phone, None)
                        else:
                            send_text_message(from_phone, "Please reply with 1, 2, or 3 to select a service.")
                    else:
                        # Default acknowledgement for other messages
                        send_text_message(from_phone, "Thanks for updating ")

    return jsonify({"status": "received"}), 200


@APP.route("/", methods=["GET"])
def health_check():
    return "Hello World, App is active", 200


if __name__ == "__main__":
    APP.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
