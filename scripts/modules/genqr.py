import base64
from time import sleep
from selenium.webdriver.common.by import By
from myconst import *


def generate_qr(driver, reserve_code):
    for _ in range(5):
        try:
            driver.get(TOKEN_URL)
        except Exception as err:
            print(f"Error: {err}")
            sleep(2)
        else:
            break
    else:
        print("Abort: could not connect to QR generation server.")
        exit(1)

    token = driver.find_element(By.XPATH, "/html/body").text
    driver.get(f"http://apache?qr={token};0;{reserve_code}")
    result = driver.find_element(By.XPATH, "/html/body/div/img")
    b64png = result.get_attribute("src").replace("data:image/png;base64,", "")
    rawpng = base64.b64decode(b64png)
    filename = f"/tmp/{reserve_code}_{token}.png"

    with open(filename, mode="wb") as f:
        f.write(rawpng)

    return filename
