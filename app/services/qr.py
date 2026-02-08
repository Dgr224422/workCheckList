from pathlib import Path
import cv2
from pyzbar.pyzbar import decode



def decode_qr(image_path: str) -> str | None:
    path = Path(image_path)
    img = cv2.imread(str(path))
    if img is None:
        return None
    decoded = decode(img)
    if not decoded:
        return None
    return decoded[0].data.decode("utf-8")
