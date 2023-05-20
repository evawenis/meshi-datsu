import os
import sys
from selenium import webdriver
from selenium.webdriver.support.select import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions


class FirefoxDriver:
    # strategy には、normal や eager を指定できる
    def __init__(self, strategy="normal", wait_time=3):
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

    def find_elements(self, kind, ident):
        return self.driver.find_elements(kind, ident)

    def wait_sync(self, kind, ident):
        WebDriverWait(self.driver, self.wait_time).until(
            expected_conditions.presence_of_all_elements_located((kind, ident))
        )

    def scroll(self, kind, ident, elem=None):
        if elem is None:
            # elem = driver.find_element(kind, ident)
            elem = self.retr_element(kind, ident)
        self.driver.execute_script("arguments[0].scrollIntoView(true);", elem)
        WebDriverWait(self.driver, self.wait_time).until(
            expected_conditions.visibility_of_element_located((kind, ident))
        )

    def retr_element(self, kind, ident):
        self.wait_sync(kind, ident)
        return self.driver.find_element(kind, ident)

    def click_alert_confirm(self):
        webdriver.common.alert.Alert(self.driver).accept()

    def click_visible(self, kind, ident):
        elem = self.retr_element(kind, ident)
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
