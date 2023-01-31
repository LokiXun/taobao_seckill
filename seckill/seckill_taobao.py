#!/usr/bin/env python3
# encoding=utf-8


import os
import json
import platform
from time import sleep
from random import choice
from datetime import datetime

from selenium import webdriver
from selenium.common.exceptions import WebDriverException, NoSuchElementException

import seckill.settings as utils_settings
from utils.utils import get_useragent_data
from utils.utils import notify_user

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 抢购失败最大次数
max_retry_count = 100  # TODO: modify here
submit_order_retry_times = 100
msg_token = "010aa82de6a67dcb02f612495d2a977827cab70a"


def default_chrome_path():
    driver_dir = getattr(utils_settings, "DRIVER_DIR", None)
    if platform.system() == "Windows":
        if driver_dir:
            return os.path.abspath(os.path.join(driver_dir, "chromedriver.exe"))

        raise Exception("The chromedriver drive path attribute is not found.")
    else:
        if driver_dir:
            return os.path.abspath(os.path.join(driver_dir, "chromedriver"))

        raise Exception("The chromedriver drive path attribute is not found.")


class ChromeDrive:

    def __init__(self, chrome_path: str = default_chrome_path(), seckill_time: str = None, password: str = None):
        self.chrome_path = chrome_path
        self.seckill_time = seckill_time
        self.seckill_time_obj = datetime.strptime(self.seckill_time, '%Y-%m-%d %H:%M:%S')
        self.password = password

    def start_driver(self):
        try:
            driver = self.find_chromedriver()
        except WebDriverException:
            print("Unable to find chromedriver, Please check the drive path.")
        else:
            return driver

    def find_chromedriver(self):
        """Creates a new instance of the chrome driver."""
        try:
            driver = webdriver.Chrome()

        except WebDriverException:
            print(f"find_chromedriver: WebDriverException error={WebDriverException}")
            try:
                driver = webdriver.Chrome(executable_path=self.chrome_path, chrome_options=self.build_chrome_options())

            except WebDriverException:
                raise
        return driver

    def build_chrome_options(self):
        """配置启动项"""
        chrome_options = webdriver.ChromeOptions()
        chrome_options.accept_untrusted_certs = True
        chrome_options.assume_untrusted_cert_issuer = True
        arguments = ['--no-sandbox', '--disable-impl-side-painting', '--disable-setuid-sandbox',
                     '--disable-seccomp-filter-sandbox',
                     '--disable-breakpad', '--disable-client-side-phishing-detection', '--disable-cast',
                     '--disable-cast-streaming-hw-encoding', '--disable-cloud-import', '--disable-popup-blocking',
                     '--ignore-certificate-errors', '--disable-session-crashed-bubble', '--disable-ipv6',
                     '--allow-http-screen-capture', '--start-maximized']
        for arg in arguments:
            chrome_options.add_argument(arg)
        chrome_options.add_argument(f'--user-agent={choice(get_useragent_data())}')
        return chrome_options

    def login(self, login_url: str = "https://www.taobao.com"):
        if login_url:
            self.driver = self.start_driver()
            print(f"initialize driver success!")
        else:
            print("Please input the login url.")
            raise Exception("Please input the login url.")

        while True:
            self.driver.get(login_url)
            try:
                if self.driver.find_element_by_link_text("亲，请登录"):
                    print("没登录，开始点击登录按钮...")
                    self.driver.find_element_by_link_text("亲，请登录").click()
                    print("请在30s内扫码登陆!!")
                    sleep(30)
                    if self.driver.find_element_by_xpath('//*[@id="J_SiteNavMytaobao"]/div[1]/a/span'):
                        print("登陆成功")
                        break
                    else:
                        print("登陆失败, 刷新重试, 请尽快登陆!!!")
                        continue
            except Exception as e:
                print(str(e))
                continue

    def keep_wait(self):
        self.login()
        print("等待到点抢购...")
        while True:
            current_time = datetime.now()
            if self.seckill_time_obj > current_time and (self.seckill_time_obj - current_time).seconds > 180:
                # 避免超过秒杀时间进入，无法购买的情况
                self.driver.get("https://cart.taobao.com/cart.htm")
                print("每分钟刷新一次界面，防止登录超时...")
                sleep(60)
            else:
                self.get_cookie()
                print("抢购时间点将近，停止自动刷新，准备进入抢购阶段...")
                break

    def sec_kill(self):
        self.keep_wait()
        self.driver.get("https://cart.taobao.com/cart.htm")
        sleep(1)

        try:
            self.driver.find_element_by_id("J_SelectAll1").click()
            print("已经选中全部商品！！！")
        except NoSuchElementException as e:
            raise Exception(f"购物车无商品！error={e}")

        submit_succ = False
        retry_count = 0

        while True:
            now = datetime.now()
            if now >= self.seckill_time_obj:
                print(f"开始抢购, 尝试次数： {str(retry_count)}")
                if submit_succ:
                    print("订单已经提交成功，无需继续抢购...")
                    break
                if retry_count > max_retry_count:
                    print("重试抢购次数达到上限，放弃重试...")
                    break

                retry_count += 1

                try:
                    # 1. 结算
                    # TODO: 判断结算按钮点击完成，点击结算按钮后存在未响应的情况
                    # 避免结算按钮点击后延迟响应，先判断是否已经进入 提交订单
                    current_page_url = self.driver.current_url
                    if "confirm_order" not in current_page_url:
                        print(f"当前页面 current_page_url={current_page_url}，仍未结算")
                        try:
                            web_element = self.driver.find_element_by_id("J_Go")
                            if not web_element.is_enabled():
                                print(f"结算按钮 当前灰色不可用")
                                continue
                            web_element.click()
                            print("已经点击结算按钮...")
                        except NoSuchElementException:
                            print(f"没有找到‘结算’按钮！error={NoSuchElementException}")
                            continue

                    # 2. 转入提交订单页面
                    click_submit_times = 0
                    while True:
                        # 判断是否进入提交订单页面，可能存在结算按钮点击后，未响应的情况
                        current_page_url = self.driver.current_url
                        if "confirm_order" not in current_page_url:
                            print(f"未跳转入‘结算订单’页面，重新结算购物车")
                            break

                        try:
                            try:
                                web_element = self.driver.find_element_by_link_text('提交订单')
                            except NoSuchElementException:
                                print(f"没有找到‘提交订单’按钮！error={NoSuchElementException}")

                            if click_submit_times < submit_order_retry_times:
                                web_element.click()
                                print("已经点击提交订单按钮")
                                submit_succ = True
                                break
                            else:
                                print(f"提交订单失败...click_submit_times={click_submit_times}")
                        except Exception as e:
                            print(f"没发现提交按钮, 页面未加载, 重试...click_submit_times={click_submit_times},"
                                  f" error={e}")
                            click_submit_times = click_submit_times + 1
                            sleep(0.1)
                except Exception as e:
                    print(e)
                    print("临时写的脚本, 可能出了点问题!!!")

            sleep(0.1)

        # 3. 付款
        if submit_succ:
            self.pay()

    def pay(self, pay_by_balance_repo_flag: bool = True):
        """
        pay the bill:
        :param pay_by_balance_repo_flag: select ways to pay, default False: debit card; if True, using balance repo
        :return:
        """
        try:
            # 1. 选择支付方式
            print(f"choose a way to pay the bill")
            if pay_by_balance_repo_flag:
                self.select_payment_using_balance_repo()

            # 2. 输入支付密码
            print(f"enter payment password")
            element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="payPassword_rsainput"]'))
            )
            element.send_keys(self.password)

            # 3. 点击确定
            print(f"press confirm")
            confirm_payment_element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "validateButton")))
            confirm_payment_element.click()

            # element = WebDriverWait(self.driver, 10).until(
            #     EC.presence_of_element_located((By.CLASS_NAME, 'sixDigitPassword')))
            # element.send_keys(self.password)
            # WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.ID, 'J_authSubmit'))).click()
            notify_user(msg="付款成功", token=msg_token)
            print(f"付款成功！")
        except Exception as e:
            error_msg = f"付款失败！error={e}"
            print(error_msg)
            notify_user(msg=error_msg, token=msg_token)
        finally:
            print(f"手动支付 in 10 min!")
            sleep(600)
            self.driver.quit()

    def select_payment_using_balance_repo(self):
        """用余额宝付款"""
        try:
            self.driver.find_element_by_xpath('//*[@id="channels"]/div/div/button[0]/span').click()  # 其他方式付款
            self.driver.find_element_by_xpath(
                '//*[@id="channels"]/div/li[2]/div/label/div[1]/span[1]').click()  # 选择余额宝
            print(f"修改支付方式 success: 当前选择为余额宝方式付款！")
        except Exception as e:
            raise Exception(f"选择余额宝方式失败! sleep 5s, error={e}")

    def get_cookie(self):
        cookies = self.driver.get_cookies()
        cookie_json = json.dumps(cookies)
        with open('./cookies.txt', 'w', encoding='utf-8') as f:
            f.write(cookie_json)
