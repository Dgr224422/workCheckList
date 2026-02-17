from pathlib import Path
from typing import Optional

import cv2


def decode_qr(image_path: str) -> Optional[str]:
    path = Path(image_path)
    img = cv2.imread(str(path))
    if img is None:
        return None

    detector = cv2.QRCodeDetector()
    data, _, _ = detector.detectAndDecode(img)
    if data:
        return data

    try:
        from pyzbar.pyzbar import decode
    except ImportError:
        return None

    decoded = decode(img)
    if decoded:
        return decoded[0].data.decode("utf-8")
    return None
