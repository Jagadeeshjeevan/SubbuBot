# Flask WhatsApp Echo Bot (Meta Cloud API)

This repository contains a minimal Flask webhook receiver and sender using the Meta (WhatsApp) Cloud API. It implements a simple echo bot for testing.

Setup

1. Create a virtualenv and install dependencies:

```bash
python -m venv venv
venv\Scripts\activate    # Windows
pip install -r requirements.txt
```

2. Copy `.env.example` to `.env` and set `WHATSAPP_TOKEN`, `PHONE_NUMBER_ID`, and `VERIFY_TOKEN`.

Running locally

1. Start the Flask app:

```bash
python app.py
```

2. Expose your localhost with `ngrok` (or another tunnel):

```bash
ngrok http 5000
```

3. In the Meta developer console (or the WhatsApp app setup), set the webhook URL to:

```
https://<your-ngrok-host>/webhook
```

Use the same `VERIFY_TOKEN` value when configuring the webhook so the GET verification succeeds.

Testing the webhook receiver

You can simulate Meta's webhook by POSTing a sample payload to `/webhook`:

```bash
curl -X POST http://localhost:5000/webhook \
  -H "Content-Type: application/json" \
  -d '{"entry":[{"changes":[{"value": {"messages":[{"from":"1234567890","type":"text","text":{"body":"hello"}}]}}]}]}'
```

The bot will attempt to call the WhatsApp Cloud API to echo messages. For real operation, incoming messages will arrive from Meta's servers.

Next steps you might want

- Add message verification / signature checking
- Add command parsing (`/help`, `/status`)
- Integrate an NLP service for conversational replies
- Deploy to a cloud service (Heroku, AWS, Azure)
