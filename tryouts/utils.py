import io

import qrcode
from django.conf import settings


def generate_checkin_qr(checkin_token, base_url=None):
    """Generate a QR code PNG for a player's check-in token.

    Returns bytes (PNG image data).
    """
    if base_url is None:
        base_url = getattr(settings, 'SITE_URL', 'http://localhost:8001')

    url = f"{base_url}/checkin/{checkin_token}/"

    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()
