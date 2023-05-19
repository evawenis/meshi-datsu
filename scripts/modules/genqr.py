import requests
import qrcode
from time import sleep

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/113.0",
    "Accept": "*/*",
    "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
    "Accept-Encoding": "gzip, deflate",
    "X-Requested-With": "XMLHttpRequest",
    "Dnt": "1",
    "Referer": "<URL>",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "Te": "trailers",
    "Connection": "close",
}

for _ in range(5):
    try:
        r = requests.get("<QR RAND URL>", headers=headers)
        r.raise_for_status()
    except Exception as err:
        print(f'Error: {err}')
        sleep(2)
    else:
        break
else:
    print("Abort: could not connect to QR generation server.")
    exit(1)

qr = qrcode.QRCode(
    version=4,
    error_correction=qrcode.constants.ERROR_CORRECT_H,
    box_size=15,
    border=1,
)

qr.add_data(f"{r.text}<VALUE>")
qr.make(fit=True)
qr.make_image().save("aaa.png")
