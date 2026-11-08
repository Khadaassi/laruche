"""Envoi d'e-mails par l'API HTTPS de Brevo.

L'offre gratuite de Render bloque les ports SMTP (25, 465, 587) : on passe donc par
l'API web de Brevo (https://api.brevo.com/v3/smtp/email), sans dépendance de plus.
Clé : variable d'environnement `BREVO_API_KEY` ; expéditeur : `DEFAULT_FROM_EMAIL`
(adresse validée dans Brevo). Sans clé, l'envoi par e-mail est désactivé
(`settings.EMAIL_ENABLED`) et l'interface le dit au lieu de faire semblant.
"""

import json
import logging
import urllib.error
import urllib.request
from email.utils import parseaddr

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

API_URL = "https://api.brevo.com/v3/smtp/email"
TIMEOUT_SECONDS = 10


def _contact(address: str) -> dict:
    name, email = parseaddr(address)
    return {"email": email, "name": name} if name else {"email": email}


class BrevoEmailBackend(BaseEmailBackend):
    """Backend Django : un appel HTTPS par message (texte, et HTML s'il y en a un)."""

    def send_messages(self, email_messages) -> int:
        sent = 0
        for message in email_messages:
            try:
                self._send(message)
            except (urllib.error.URLError, TimeoutError, ValueError):
                logger.exception("Envoi d'e-mail impossible (Brevo)")
                if not self.fail_silently:
                    raise
            else:
                sent += 1
        return sent

    def _send(self, message) -> None:
        payload = {
            "sender": _contact(message.from_email or settings.DEFAULT_FROM_EMAIL),
            "to": [_contact(address) for address in message.recipients()],
            "subject": message.subject,
            "textContent": message.body,
        }
        for content, mimetype in getattr(message, "alternatives", []):
            if mimetype == "text/html":
                payload["htmlContent"] = content
        request = urllib.request.Request(  # noqa: S310 (URL https fixe)
            API_URL,
            data=json.dumps(payload).encode(),
            method="POST",
            headers={
                "api-key": settings.BREVO_API_KEY,
                "accept": "application/json",
                "content-type": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
            if response.status >= 300:
                raise ValueError(f"Brevo a répondu {response.status}")
