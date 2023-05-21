#!/usr/bin/env python3

import os
import re
import sys
import time
import base64
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions

from .myconst import *


class FirefoxDriver:
    # strategy には、normal や eager を指定できる
    def __init__(self, strategy=STRATEGY, wait_time=WAIT_TIME):
        self.strategy = strategy
        self.wait_time = wait_time

    def __enter__(self):
        options = webdriver.FirefoxOptions()
        options.page_load_strategy = self.strategy

        self.driver = webdriver.Remote(
            command_executor=os.environ["SELENIUM_URL"], options=options
        )

        # ロボット検知を回避
        self.driver.execute_script(
            "const newProto = navigator.__proto__;"
            "delete newProto.webdriver;"
            "navigator.__proto__ = newProto;"
        )

        # 出力が None のとき、ロボットと検知されない
        print(
            "navigator.webdriver:",
            self.driver.execute_script("return navigator.webdriver"),
            file=sys.stderr,
        )

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.driver.quit()

    def get(self, url: str):
        return self.driver.get(url)

    def wait_sync(self, kind, ident):
        WebDriverWait(self.driver, self.wait_time).until(
            expected_conditions.presence_of_all_elements_located((kind, ident))
        )

    def wait_until_disappear(self, kind, ident):
        WebDriverWait(self.driver, self.wait_time).until(
            expected_conditions.invisibility_of_element_located((kind, ident))
        )

    def wait_until_clickable(self, kind, ident):
        WebDriverWait(self.driver, self.wait_time).until(
            expected_conditions.element_to_be_clickable((kind, ident))
        )

    def scroll(self, kind, ident, elem=None):
        if elem is None:
            elem = self.retr_element(kind, ident)
        self.driver.execute_script("arguments[0].scrollIntoView(true);", elem)
        WebDriverWait(self.driver, self.wait_time).until(
            expected_conditions.visibility_of_element_located((kind, ident))
        )

    def retr_element(self, kind, ident):
        self.wait_sync(kind, ident)
        return self.driver.find_element(kind, ident)

    def retr_elements(self, kind, ident):
        self.wait_sync(kind, ident)
        return self.driver.find_elements(kind, ident)

    def click_alert_confirm(self):
        webdriver.common.alert.Alert(self.driver).accept()

    def click_visible(self, kind, ident):
        elem = self.retr_element(kind, ident)
        self.wait_until_clickable(kind, ident)
        self.scroll(kind, ident, elem)
        elem.click()

    def click_invisible(self, kind, ident):
        elem = self.retr_element(kind, ident)
        self.driver.execute_script("arguments[0].click();", elem)

    def select_pulldown(self, kind, ident, string):
        self.wait_sync(kind, ident)
        self.scroll(kind, ident)
        Select(self.driver.find_element(kind, ident)).select_by_value(string)

    def input_form(self, kind, ident, input):
        elem = self.retr_element(kind, ident)
        self.scroll(kind, ident, elem)
        elem.send_keys(input)

    def delete_all_cookies(self):
        self.driver.delete_all_cookies()


class MeshiDatsuDriver(FirefoxDriver):
    def __init__(
        self,
        strategy=STRATEGY,
        wait_time=WAIT_TIME,
        user_id=ID,
        passwd=PW,
        account_url=ACCOUNT_URL,
        reserve_url=RESERVE_URL,
        token_url=TOKEN_URL,
    ):
        super().__init__(strategy, wait_time)
        self.next_count = 0
        self.user_id = user_id
        self.passwd = passwd
        self.account_url = account_url
        self.reserve_url = reserve_url
        self.token_url = token_url

    def __enter__(self):
        super().__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        super().__exit__(exc_type, exc_val, exc_tb)

    # ログイン状態を確認
    def is_login(self):
        super().get(self.reserve_url)
        try:
            super().retr_element(By.XPATH, '//span[@onclick="stage.customerLogout();"]')
            return True
        except:
            try:
                super().retr_element(
                    By.XPATH, '//span[@onclick="stage.openCustomerLoginDialog();"]'
                )
                return False
            except Exception as e:
                raise Exception(
                    "エラー：ログインとログアウトどちらも確認できませんでした。"
                    f"仕様が変更された可能性があります。is_login でエラーが発生しました。{str(e)}"
                )

    # ログインする関数
    def login(self):
        if self.is_login():
            return

        super().click_visible(
            By.XPATH, '//span[@onclick="stage.openCustomerLoginDialog();"]'
        )
        super().input_form(By.NAME, "login_id", self.user_id)
        super().input_form(By.NAME, "customer_password", self.passwd)
        super().click_visible(By.ID, "customer_login_button")
        super().wait_sync(By.ID, "stage_action_button_reservation_")

    def logout(self):
        if not self.is_login():
            return
        super().click_visible(By.XPATH, '//span[@onclick="stage.customerLogout();"]')
        self.wait_sync(By.XPATH, '//span[@onclick="stage.openCustomerLoginDialog();"]')

        super().delete_all_cookies()

    # 予約日がすべて表示されるまで「もっと探す」をクリックし、
    # その回数を記録する
    def count_more(self):
        if self.next_count != 0:
            return
        super().get(self.reserve_url)
        while True:
            try:
                super().click_visible(
                    By.XPATH, "//div[@onclick=\"target_area_of[''].more()\"]"
                )
                self.next_count += 1
            except:
                break

    def click_more(self):
        self.count_more()
        super().get(self.reserve_url)
        for _ in range(self.next_count):
            super().click_visible(
                By.XPATH, "//div[@onclick=\"target_area_of[''].more()\"]"
            )

    def reserve(self, start_time, place: int):
        self.login()
        self.click_more()

        element = (
            f'//div[@data-start_unixtime="{start_time}"]'
            f'[@data-calendar_id="S001.{FUKURAS if place else CERULEAN}..'
            f'{start_time}.{start_time + 1800}"]'
        )

        # 受付前の文字列は今後確認し、実装する必要あり
        # 指定日時が予約可能であるか確認
        text = super().retr_element(By.XPATH, element).text
        if "受付終了" in text:
            return "受付終了（予約失敗）"

        super().click_visible(By.XPATH, element)

        # 予約制限を超えていないか確認
        is_exceeded = re.compile(r"^[^こ]+これ以上予約できません。")
        text = super().retr_element(By.ID, "modal_body").text
        if is_exceeded.match(text):
            raise Exception(is_exceeded.findall(text)[0])

        super().click_visible(By.NAME, "confirm")
        super().click_visible(By.ID, "button_予約する")
        # 2 度現れる！
        super().wait_until_disappear(By.ID, "message_box")
        super().wait_until_disappear(By.ID, "message_box")
        super().click_visible(By.ID, "button_確認しました")

        return "予約成功"

    def cancel(self, reserve_id):
        self.login()
        super().get(self.account_url)
        super().click_visible(
            By.XPATH,
            f'//div/span/a[@href="#"][@onclick="mypage.openBooking(\'{reserve_id}\');return false;"]',
        )
        super().click_visible(By.ID, "booking_cancel")
        super().click_visible(By.ID, "button_送信する")
        super().click_alert_confirm()
        # 2 度現れる！
        super().wait_until_disappear(By.ID, "message_box")
        super().wait_until_disappear(By.ID, "message_box")
        super().click_visible(By.ID, "button_閉じる")

    # 乱数付き予約番号を引数に取る
    # QR コードを生成して、ファイルを作成する
    # ファイル名のフルパスを返す
    def generate_qr(self, reserve_code):
        for _ in range(5):
            try:
                super().get(self.token_url)
            except Exception as err:
                print(f"Error: {err}")
                time.sleep(2)
            else:
                break
        else:
            raise Exception(
                "QR コードのトークンを生成するサーバへ正常に接続できませんでした。generate_qr でエラーが発生しました。"
            )

        token = super().retr_element(By.XPATH, "/html/body").text
        super().get(f"http://apache?qr={token};0;{reserve_code}")
        result = super().retr_element(By.XPATH, "/html/body/div/img")
        b64png = result.get_attribute("src").replace("data:image/png;base64,", "")
        rawpng = base64.b64decode(b64png)
        filename = f"/tmp/{reserve_code}_{token}.png"

        with open(filename, mode="wb") as f:
            f.write(rawpng)

        return filename

    # 現在ログイン中のアカウントの予約データをすべて取得する
    # [['R0345833', '2023/05/23', '13:00 - 13:30', '<PLACE2>', 1684814400, 1684816200], ...]
    def retr_reserved_data_from_account(self):
        self.login()
        super().get(self.account_url)
        super().wait_sync(By.CLASS_NAME, "list_item")
        elems = super().retr_elements(By.CLASS_NAME, "list_item")
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

    # 前提：ログイン中
    # retr_reserve_data_from_account で取得したリストを引数に取る
    # 引数に、乱数付きの予約番号を追加したリストを返す
    # [['R0345833', '2023/05/23', '13:00 - 13:30', '<PLACE2>', 1684814400, 1684816200, 'R0345833_768c'], ...]
    def retr_reserved_with_rand_from_account(self, reserve_data_list: list[str]):
        super().get(self.account_url)
        for i, data in enumerate(reserve_data_list):
            id = data[RSV_ID]
            super().click_visible(
                By.XPATH,
                f'//div/span/a[@href="#"][@onclick="mypage.openBooking(\'{id}\');return false;"]',
            )
            qr_elem = super().retr_element(By.ID, "my_reservation_qrcode")
            reserve_data_list[i].append(qr_elem.get_attribute("title").split(";")[2])
            super().click_visible(By.ID, "button_閉じる")
        return reserve_data_list
