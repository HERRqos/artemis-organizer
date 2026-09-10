"""WhatsApp Cloud API send client.

Free-form text only works inside the 24h customer service window.
Anything proactive (reminders) must use an approved template.
"""
import httpx

from .config import Settings


class WhatsAppClient:
    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        self._s = settings
        self._url = (
            f"https://graph.facebook.com/{settings.graph_api_version}"
            f"/{settings.whatsapp_phone_number_id}/messages"
        )
        self._http = client or httpx.Client(timeout=15)

    def _post(self, body: dict) -> dict:
        r = self._http.post(
            self._url,
            json=body,
            headers={"Authorization": f"Bearer {self._s.whatsapp_token}"},
        )
        r.raise_for_status()
        return r.json()

    def send_text(self, to: str, text: str) -> dict:
        return self._post(
            {"messaging_product": "whatsapp", "to": to,
             "type": "text", "text": {"body": text}}
        )

    def send_template(self, to: str, name: str, params: list[str], lang: str = "es") -> dict:
        return self._post(
            {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "template",
                "template": {
                    "name": name,
                    "language": {"code": lang},
                    "components": [
                        {"type": "body",
                         "parameters": [{"type": "text", "text": p} for p in params]}
                    ],
                },
            }
        )
