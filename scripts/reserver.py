#!/usr/bin/env python3

import os
import sys
import time
import sched
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.select import Select
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options

# ------- パラメータ開始 -------

geckodriver_path = "<GECKO DRIVER PATH>"

url = "<YOUR MESHI RESERVE URL>"

schedule = "2023-05-05 12:00:00.00"

secret1 = "S0000063"
secret2 = "S0000064"

basho = secret2

id = "<YOUR MAILADDR>"
pw = "<YOUR PASSWD>"

wait_time = 3

next_count = 0


# firefox の操作
def run(driver):
    print(f"Start:  {datetime.now()}", file=sys.stderr)
    driver.get("https://google.com")
    # initial(driver)

    # arr = [1683604800, 1683691200, 1683777600, 1683864000,
    #        1684123200, 1684209600, 1684296000, 1684382400, 1684468800]
    # for start_time in arr:
    #     reserve(driver, start_time)
    #     driver.get(url)
    #     for _ in range(next_count):
    #         click_visible(driver, By.XPATH,
    #                       '//div[@onclick="target_area_of[\'\'].more()"]')

    # print(f'Finish: {datetime.now()}', file=sys.stderr)


def reserve(driver, start_time):
    try:
        click_visible(
            driver,
            By.XPATH,
            f'//div[@data-start_unixtime="{start_time}"][@data-calendar_id="S001.{basho}..{start_time}.{start_time + 600}"]',
        )
        click_visible(driver, By.NAME, "confirm")
        click_visible(driver, By.ID, "button_予約する")
        # click_visible(driver, By.ID, 'button_確認しました')
    except:
        return


def initial(driver):
    global next_count
    driver.get(url)

    click_visible(driver, By.XPATH, "/html/body/div/div[4]/div[1]/div/span")
    input_form(driver, By.NAME, "login_id", id)
    input_form(driver, By.NAME, "customer_password", pw)
    click_visible(driver, By.ID, "customer_login_button")
    driver.get(url)

    while True:
        try:
            click_visible(
                driver, By.XPATH, "//div[@onclick=\"target_area_of[''].more()\"]"
            )
            next_count += 1
        except:
            break


# ------- パラメータ終わり -------

# geckodriver
# https://github.com/mozilla/geckodriver

# References
# https://ai-inter1.com/python-selenium/
# https://kurozumi.github.io/selenium-python/locating-elements.html
# https://qiita.com/r_ishimori/items/4ed251f0d166d5c9cee1
# https://scrapbox.io/kb84tkhr-pub/Selenium_-_%E3%81%8B%E3%81%AA%E3%82%89%E3%81%9Awebdriver%E3%82%92%E9%96%89%E3%81%98%E3%82%8B
# https://qiita.com/tkdayo/items/5a110e24abad85822b8f
# https://1024.hateblo.jp/entry/2022/01/15/011604
# https://qiita.com/aonisai/items/29308611cece0897e949
# https://qiita.com/ha_ru/items/86dfaae4c92e4a7be13f

def wait_sync(driver, kind, ident):
    WebDriverWait(driver, wait_time).until(
        expected_conditions.presence_of_all_elements_located((kind, ident))
    )


def scroll(driver, kind, ident, elem=None):
    if elem is None:
        elem = driver.find_element(kind, ident)
    driver.execute_script("arguments[0].scrollIntoView(true);", elem)
    WebDriverWait(driver, wait_time).until(
        expected_conditions.visibility_of_element_located((kind, ident))
    )


def click_visible(driver, kind, ident):
    wait_sync(driver, kind, ident)
    elem = driver.find_element(kind, ident)
    scroll(driver, kind, ident, elem)
    elem.click()


def click_invisible(driver, kind, ident):
    wait_sync(driver, kind, ident)
    elem = driver.find_element(kind, ident)
    driver.execute_script("arguments[0].click();", elem)


def select_pulldown(driver, kind, ident, string):
    wait_sync(driver, kind, ident)
    scroll(driver, kind, ident)
    Select(driver.find_element(kind, ident)).select_by_value(string)


def input_form(driver, kind, ident, input):
    wait_sync(driver, kind, ident)
    elem = driver.find_element(kind, ident)
    scroll(driver, kind, ident, elem)
    elem.send_keys(input)


def scheduler(driver):
    now = datetime.now()
    now = datetime(now.year, now.month, now.day, now.hour, now.minute, now.second)
    comp = datetime.strptime(schedule, "%Y-%m-%d %H:%M:%S.%f")
    diff = comp - now

    if diff.days < 0:
        print("error: the scheduled time went over.", file=sys.stderr)
        return

    print(
        f"waiting {diff}, until {datetime.strptime(schedule, '%Y-%m-%d %H:%M:%S.%f')}",
        file=sys.stderr,
    )
    scheduler = sched.scheduler(time.time, time.sleep)
    scheduler.enter(diff.seconds, 1, run, (driver,))
    scheduler.run()


def main():
    options = webdriver.FirefoxOptions()
    options.page_load_strategy = "eager"

    # firefox_service = Service(geckodriver_path)
    # driver = webdriver.Firefox(service=firefox_service, options=options)
    driver = webdriver.Remote(
        command_executor=os.environ["SELENIUM_URL"], options=options
    )

    # ロボット検知を回避
    driver.execute_script(
        "const newProto = navigator.__proto__;"
        "delete newProto.webdriver;"
        "navigator.__proto__ = newProto;"
    )

    # 出力が None のとき、ロボットと検知されない
    print(
        "navigator.webdriver:",
        driver.execute_script("return navigator.webdriver"),
        file=sys.stderr,
    )

    print("opened a browser, please do not close it", file=sys.stderr)
    # scheduler(driver)
    run(driver)


if __name__ == "__main__":
    main()
