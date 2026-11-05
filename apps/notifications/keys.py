"""Clés VAPID (identifient l'expéditeur des notifications push).

Par défaut, dérivées de `SECRET_KEY` (HKDF) : rien de plus à configurer sur Render, et
aucune clé dans le code. Surcharge possible par `VAPID_PRIVATE_KEY` (base64url, 32 octets).
Changer `SECRET_KEY` change les clés : les appareils devront réactiver les notifications.
"""

import base64
import functools

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.conf import settings
from py_vapid import Vapid02

# Ordre de la courbe P-256 : la clé privée doit être dans [1, n-1].
P256_ORDER = 0xFFFFFFFF00000000FFFFFFFFFFFFFFFFBCE6FAADA7179E84F3B9CAC2FC632551


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _private_value() -> int:
    raw = getattr(settings, "VAPID_PRIVATE_KEY", "")
    if raw:
        padded = raw + "=" * (-len(raw) % 4)
        return int.from_bytes(base64.urlsafe_b64decode(padded), "big")
    derived = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=b"laruche-vapid", info=b"web-push"
    ).derive(settings.SECRET_KEY.encode())
    return int.from_bytes(derived, "big") % (P256_ORDER - 1) + 1


@functools.cache
def private_key() -> ec.EllipticCurvePrivateKey:
    return ec.derive_private_key(_private_value(), ec.SECP256R1())


def vapid() -> Vapid02:
    return Vapid02.from_raw(
        b64url(private_key().private_numbers().private_value.to_bytes(32, "big")).encode()
    )


def public_key_b64() -> str:
    """Clé publique (point non compressé, base64url) pour `applicationServerKey`."""
    point = (
        private_key()
        .public_key()
        .public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    )
    return b64url(point)
