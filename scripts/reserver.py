#!/usr/bin/env python3

import os
import re
import sys
import time
import sched
from datetime import datetime
from selenium.webdriver.common.by import By

from modules import sql
from modules import genqr
from modules import mydate
from modules import firefox

from modules.const import *


# firefox の操作
def run(driver):
    print(f"Start:  {datetime.now()}", file=sys.stderr)
    login(driver)

    tmplist = retr_reserve_data(driver)
    result = retr_reserve_code(driver, tmplist)
    sql.insert_reserve_data(result)

    for day, hour, min in [(2, 12, 30)]:
        start_time = mydate.next_unix_time(day, hour, min)
        print(start_time)
        reserve(driver, start_time)
        driver.get(RESERVE_URL)
        click_more(driver)

    time.sleep(3)

    print(f"Finish: {datetime.now()}", file=sys.stderr)


def retr_reserve_data(driver):
    driver.get(ACCOUNT_URL)
    driver.wait_sync(By.CLASS_NAME, "list_item")
    elems = driver.find_elements(By.CLASS_NAME, "list_item")
    # compile
    regex = list(map(re.compile, RAW_REGEX))
    result = []
    for elem in elems:
        result.append([re.findall(rg, elem.text)[0] for rg in regex])

        # reserve_date (e.g. 2023/05/19 -> 2023-05-19)
        iso_date = re.sub(r"/", "-", result[-1][1])

        # reserve_time (e.g. 13:00 - 13:30 -> 13:00, 13:30)
        tm = result[-1][2].split(" - ")
        result[-1] += [
            # isoformat to unixtime (e.g. 2023-05-19T13:00 -> 1684468800)
            int(datetime.fromisoformat("T".join([iso_date, t])).timestamp())
            for t in tm
        ]

    return result


# retr_reserve_data で取得したリストを引数に取る
# 引数に、乱数付きの予約番号を追加したリストを返す
def retr_reserve_code(driver, reserve_data_list: list[str]):
    try:
        driver.get(ACCOUNT_URL)
        for i, data in enumerate(reserve_data_list):
            id = data[0]
            driver.click_visible(
                By.XPATH,
                f'//div/span/a[@href="#"][@onclick="mypage.openBooking(\'{id}\');return false;"]',
            )
            qr_elem = driver.retr_element(By.ID, "my_reservation_qrcode")
            reserve_data_list[i].append(qr_elem.get_attribute("title").split(";")[2])
            driver.click_visible(By.ID, "button_閉じる")
        return reserve_data_list
    except Exception as e:
        print(e)
        return


def cancel(driver, reserve_id):
    try:
        driver.get(ACCOUNT_URL)
        driver.click_visible(
            By.XPATH,
            f'//div/span/a[@href="#"][@onclick="mypage.openBooking(\'{reserve_id}\');return false;"]',
        )
        driver.click_visible(By.ID, "booking_cancel")
        driver.click_visible(By.ID, "button_送信する")
        driver.click_alert_confirm()
        driver.click_visible(By.ID, "button_閉じる")
    except Exception as e:
        print(e)
        return


def reserve(driver, start_time, place):
    try:
        driver.click_visible(
            By.XPATH,
            f'//div[@data-start_unixtime="{start_time}"][@data-calendar_id="S001.{place}..{start_time}.{start_time + 1800}"]',
        )
        driver.click_visible(By.NAME, "confirm")
        driver.click_visible(By.ID, "button_予約する")
        driver.click_visible(By.ID, "button_確認しました")
    except Exception as e:
        print(e)
        return


def click_more(driver):
    driver.get(RESERVE_URL)
    for _ in range(next_count):
        driver.click_visible(By.XPATH, "//div[@onclick=\"target_area_of[''].more()\"]")


def count_more(driver):
    driver.get(RESERVE_URL)
    while True:
        try:
            driver.click_visible(
                By.XPATH, "//div[@onclick=\"target_area_of[''].more()\"]"
            )
            next_count += 1
        except:
            break


def login(driver):
    global next_count
    driver.get(RESERVE_URL)

    driver.click_visible(
        By.XPATH, '//span[@onclick="stage.openCustomerLoginDialog();"]'
    )
    driver.input_form(By.NAME, "login_id", ID)
    driver.input_form(By.NAME, "customer_password", PW)
    driver.click_visible(By.ID, "customer_login_button")
    driver.wait_sync(By.ID, "stage_action_button_reservation_")


def scheduler(driver):
    now = datetime.now()
    now = datetime(now.year, now.month, now.day, now.hour, now.minute, now.second)
    comp = datetime.strptime(SCHEDULE, "%Y-%m-%d %H:%M:%S.%f")
    diff = comp - now

    if diff.days < 0:
        print("error: the scheduled time went over.", file=sys.stderr)
        return

    print(
        f"waiting {diff}, until {datetime.strptime(SCHEDULE, '%Y-%m-%d %H:%M:%S.%f')}",
        file=sys.stderr,
    )
    scheduler = sched.scheduler(time.time, time.sleep)
    scheduler.enter(diff.seconds, 1, run, (driver,))
    scheduler.run()


def main():
    with firefox.FirefoxDriver("normal", WAIT_TIME) as driver:
        run(driver)


if __name__ == "__main__":
    main()
