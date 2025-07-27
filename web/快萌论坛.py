"""
作者: 临渊
日期: 2025/6/8
name: 快萌论坛
入口: 网站 (https://kmacg20.com/)
功能: 登录、签到
变量: kmacg='邮箱&密码' 或者 'cookie'
        自动检测，多个账号用换行分割
        使用邮箱密码将会进行登录（必须有ocr服务地址）
        使用cookie将会直接使用
定时: 一天两次
cron: 10 9,10 * * *
------------更新日志------------
2025/6/8    V1.0    初始化，完成签到功能
2025/7/28   V1.1    修改头部注释，以便拉库
"""

DEFAULT_HOST = "kmacg20.com" # 默认域名

from bs4 import BeautifulSoup
import requests
import os
import re
import urllib.parse
import logging
import traceback
import base64
import random
import time
import json
from datetime import datetime

DDDD_OCR_URL = os.getenv("DDDD_OCR_URL") or "" # dddd_ocr地址

class AutoTask:
    def __init__(self, site_name):
        """
        初始化自动任务类
        :param site_name: 站点名称，用于日志显示
        """
        self.site_name = site_name
        self.cookie_file = f"{site_name}_cookie.json"
        self.setup_logging()

    def setup_logging(self):
        """
        配置日志系统
        """
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s\t- %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            handlers=[
                # logging.FileHandler(f'{self.site_name}_{datetime.now().strftime("%Y%m%d")}.log', encoding='utf-8'), # 保存日志
                logging.StreamHandler()
            ]
        )

    def check_env(self):
        """
        检查环境变量
        :return: 邮箱和密码，或者cookie
        """
        try:
            env = os.getenv("kmacg")
            if not env:
                logging.error("[检查环境变量]没有找到环境变量kmacg")
                return
            # 多个账号用换行分割
            envs = env.split('\n')
            for env in envs:
                if '&' in env:
                    # 解析cookie字符串，提取邮箱和密码
                    email, password = env.split('&')
                    yield email, password, None
                else:
                    # 直接使用cookie
                    yield None, None, env
        except Exception as e:
            logging.error(f"[检查环境变量]发生错误: {str(e)}\n{traceback.format_exc()}")
            raise

    def get_param(self, host, session):
        """
        获取参数
        :param host: 域名
        :param session: 会话对象
        :return: formhash, seccodehash, loginhash
        """
        try:
            # 访问首页
            url = f"https://{host}/member.php?mod=logging&action=login"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36 Edg/137.0.0.0',
                'Host': host
            }
            response = session.get(url, headers=headers)
            response.raise_for_status()

            # 使用正则表达式匹配
            # formhash 格式: name="formhash" value="5448b1bc"
            pattern = r'name="formhash" value="([a-zA-Z0-9]{8})"'
            match = re.search(pattern, response.text)
            if match:
                formhash = match.group(1)
            else:
                logging.error("[获取formhash]无法获取formhash")
                return None, None, None
            # # seccodehash 格式: seccode_cSAbDg cSAbDg
            # pattern = r'seccode_([a-zA-Z0-9]{6})'
            # match = re.search(pattern, response.text)
            # if match:
            #     seccodehash = match.group(1)
            # else:
            #     logging.error("[获取seccodehash]无法获取seccodehash")
            #     return None, None, None
            # loginhash 格式: main_messaqge_LCpo4 LCpo4
            seccodehash = 'test'
            pattern = r'main_messaqge_([a-zA-Z0-9]{5})'
            match = re.search(pattern, response.text)
            if match:
                loginhash = match.group(1)
            else:
                logging.error("[获取loginhash]无法获取loginhash")
                return None, None, None
            return formhash, seccodehash, loginhash
        except requests.RequestException as e:
            logging.warning(f"[获取参数]发生网络错误: {str(e)}\n{traceback.format_exc()}")
            return None, None, None
        except Exception as e:
            logging.error(f"[获取参数]发生未知错误: {str(e)}\n{traceback.format_exc()}")
            return None, None, None

    def get_captcha_img(self, host, seccodehash, session):
        """
        获取验证码图片
        :param host: 域名
        :param seccodehash: seccodehash
        :param session: 会话对象
        :return: 验证码图片
        """
        try:
            url = f"https://{host}/misc.php?mod=seccode&update={random.randint(10000, 99999)}&idhash={seccodehash}"
            headers = {
                'referer': f'https://{host}/member.php?mod=logging&action=login',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36 Edg/137.0.0.0',
                'Host': host
            }
            response = session.get(url, headers=headers)
            # 图片转为base64
            img_base64 = base64.b64encode(response.content).decode('utf-8')
            return img_base64
        except Exception as e:
            logging.error(f"[获取验证码图片]发生未知错误: {str(e)}\n{traceback.format_exc()}")
            return None

    def get_captcha_text(self, img_base64):
        """
        获取验证码文字
        :param img_base64: 验证码base64
        :return: 验证码文字
        """
        try:
            url = DDDD_OCR_URL
            payload = {
                'image': img_base64
            }
            response = requests.post(url, data=payload).json()
            if response['code'] == 200:
                return response['data']
            else:
                logging.error(f"[获取验证码]发生错误: {response['message']}")
                return None
        except Exception as e:
            logging.error(f"[获取验证码]发生错误: {str(e)}\n{traceback.format_exc()}")
            return None

    def check_captcha(self, host, captcha, session, seccodehash):
        """
        检查验证码
        :param host: 域名
        :param captcha: 验证码文字
        :param session: 会话对象
        :param seccodehash: seccodehash
        :return: 是否正确
        """
        try:
            url = f"https://{host}/misc.php?mod=seccode&action=check&inajax=1&modid=member::logging&idhash={seccodehash}&secverify={captcha}"
            headers = {
                'referer': f'https://{host}/member.php?mod=logging&action=login',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36 Edg/137.0.0.0',
                'Host': host
            }
            response = session.get(url, headers=headers)
            response.raise_for_status()

            pattern = r'<!\[CDATA\[(.*?)\]\]>'
            match = re.search(pattern, response.text)
            if match:
                text = match.group(1)
                if "succeed" in text:
                    return True
                else:
                    return False
            else:
                logging.warning("[检查验证码]响应格式异常")
                return False
        except requests.RequestException as e:
            logging.error(f"[检查验证码]发生网络错误: {str(e)}\n{traceback.format_exc()}")
            return False
        except Exception as e:
            logging.error(f"[检查验证码]发生未知错误: {str(e)}\n{traceback.format_exc()}")
            return False

    def login_in(self, host, username, password, formhash, captcha, session, loginhash, seccodehash):
        """
        登录
        :param host: 域名
        :param username: 邮箱
        :param password: 密码
        :param formhash: formhash
        :param captcha: 验证码文字
        :param session: 会话对象
        :param loginhash: loginhash
        :param seccodehash: seccodehash
        :return: 是否成功
        """
        try:
            url = f"https://{host}/member.php?mod=logging&action=login&loginsubmit=yes&loginhash={loginhash}&inajax=1"
            payload = f"formhash={formhash}&referer=https://{host}/home.php?mod=spacecp&ac=credit&showcredit=1&loginfield=email&username={username}&password={password}&questionid=0&answer=&seccodehash={seccodehash}&seccodemodid=member::logging&seccodeverify={captcha}&cookietime=2592000"
            headers = {
                'Referer': f'https://{host}/home.php?mod=spacecp&ac=credit&showcredit=1',
                'content-type': 'application/x-www-form-urlencoded',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36 Edg/137.0.0.0',
                'Host': host
            }
            # payload转为url编码，/替换为%2F
            payload = urllib.parse.quote(payload, safe='=&')
            response = session.post(url, headers=headers, data=payload)
            response.raise_for_status()
            pattern = r'<!\[CDATA\[(.*?)\]\]>'
            match = re.search(pattern, response.text)
            if match:
                text = match.group(1)
                if "欢迎您回来" in text:
                    # 匹配
                    username_pattern = r'欢迎您回来，(.*?)，现在将转入登录前页面'
                    username_match = re.search(username_pattern, text)
                    if username_match:
                        matched_username = username_match.group(1)
                        logging.info(f"[登录]成功，当前账号: {matched_username}")
                        return True
                else:
                    logging.warning("[登录]登录失败")
                    return False
            else:
                logging.warning("[登录]响应格式异常")
                return False
        except requests.RequestException as e:
            logging.error(f"[登录]发生网络错误: {str(e)}\n{traceback.format_exc()}")
            return False
        except Exception as e:
            logging.error(f"[登录]发生未知错误: {str(e)}\n{traceback.format_exc()}")
            return False

    def get_sign_hash(self, host, session):
        """
        获取签到hash
        :param host: 域名
        :param session: 会话对象
        :return: 签到hash
        """
        try:
            url = f"https://{host}/dsu_paulsign-sign.html"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36 Edg/137.0.0.0',
                'Host': host
            }
            response = session.get(url, headers=headers)
            response.raise_for_status()
            pattern = r'formhash=([a-zA-Z0-9]{8})'
            match = re.search(pattern, response.text)
            if match:
                formhash = match.group(1)
                return formhash
            else:
                logging.warning("[获取签到hash]无法获取签到hash")
                return None
        except requests.RequestException as e:
            logging.error(f"[获取签到hash]发生网络错误: {str(e)}\n{traceback.format_exc()}")
            return None

    def get_sign_result(self, html):
        """
        获取签到结果
        :param html: 签到结果
        :return: 签到结果
        """
        # 提取CDATA中的HTML内容
        start_cdata = html.find('<![CDATA[') + len('<![CDATA[')
        end_cdata = html.find(']]>')
        html_content = html[start_cdata:end_cdata]
        soup = BeautifulSoup(html_content, 'html.parser')
        sign_res = soup.find('div', class_='c')
        if sign_res:
            return sign_res.text.strip()
        else:
            return None

    def signin(self, host, session, sign_hash):
        """
        签到
        :param host: 域名
        :param session: 会话对象
        :param sign_hash: 签到hash
        """
        try:
            if not sign_hash:
                logging.error("sign_hash为空，无法进行签到")
                return

            url = f"https://{host}/plugin.php?id=dsu_paulsign:sign&operation=qiandao&infloat=1&inajax=1"
            payload = f"formhash={sign_hash}&qdxq=ym&qdmode=2&todaysay=&fastreply=0"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36 Edg/137.0.0.0',
                'Host': host,
                'Content-Type': 'application/x-www-form-urlencoded',
                'Referer': f'https://{host}/dsu_paulsign-sign.html'
            }
            response = session.post(url, headers=headers, data=payload)
            response.raise_for_status()
            sign_result = self.get_sign_result(response.text)
            logging.info(f"[签到]签到结果: {sign_result}")
        except requests.RequestException as e:
            logging.error(f"[签到]发生网络错误: {str(e)}\n{traceback.format_exc()}")
        except Exception as e:
            logging.error(f"[签到]发生未知错误: {str(e)}\n{traceback.format_exc()}")

    def do_task(self, host, session):
        """
        执行任务
        :param host: 域名
        :param session: 会话对象
        """
        try:
            sign_hash = self.get_sign_hash(host, session)
            if sign_hash:
                self.signin(host, session, sign_hash)
        except Exception as e:
            logging.error(f"[执行任务]发生未知错误: {str(e)}\n{traceback.format_exc()}")

    def read_cookie_file(self):
        """
        读取cookie文件
        :return: cookie字符串或None
        """
        try:
            if os.path.exists(self.cookie_file):
                with open(self.cookie_file, 'r', encoding='utf-8') as f:
                    cookie_data = json.load(f)
                    if cookie_data.get('accounts'):
                        logging.info(f"[读取Cookie文件]成功读取{self.cookie_file}")
                        return cookie_data['accounts']
            return None
        except Exception as e:
            logging.error(f"[读取Cookie文件]发生错误: {str(e)}\n{traceback.format_exc()}")
            return None

    def write_cookie_file(self, cookies, email=None):
        """
        写入cookie文件
        :param cookies: cookie字符串
        :param email: 账号邮箱，用于标识不同账号
        """
        try:
            # 读取现有cookie文件
            existing_data = {}
            if os.path.exists(self.cookie_file):
                with open(self.cookie_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)

            # 准备新的cookie数据
            cookie_data = {
                'site_name': self.site_name,
                'host': DEFAULT_HOST,
                'accounts': existing_data.get('accounts', {}),
                'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }

            # 更新或添加账号cookie
            if email:
                cookie_data['accounts'][email] = {
                    'cookies': cookies,
                    'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            else:
                # 如果没有提供email，使用默认键
                cookie_data['accounts']['default'] = {
                    'cookies': cookies,
                    'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }

            with open(self.cookie_file, 'w', encoding='utf-8') as f:
                json.dump(cookie_data, f, ensure_ascii=False, indent=2)
            logging.info(f"[写入Cookie文件]成功写入{self.cookie_file}")
        except Exception as e:
            logging.error(f"[写入Cookie文件]发生错误: {str(e)}\n{traceback.format_exc()}")

    def get_session_cookies(self, session):
        """
        获取session的cookies字符串
        :param session: 会话对象
        :return: cookie字符串
        """
        try:
            cookies = []
            for cookie in session.cookies:
                cookies.append(f"{cookie.name}={cookie.value}")
            return '; '.join(cookies)
        except Exception as e:
            logging.error(f"[获取Session Cookies]发生错误: {str(e)}\n{traceback.format_exc()}")
            return None

    def check_cookie_valid(self, host, session):
        """
        检查cookie是否有效
        :param host: 域名
        :param session: 会话对象
        :return: 是否有效
        """
        try:
            url = f"https://{host}/home.php?mod=space"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36 Edg/137.0.0.0',
                'Host': host
            }
            response = session.get(url, headers=headers)
            response.raise_for_status()

            if "请先登录" in response.text:
                return False
            return True
        except Exception as e:
            logging.error(f"[Cookie检测]发生错误: {str(e)}\n{traceback.format_exc()}")
            return False

    def run(self):
        """
        执行签到任务的主函数
        """
        try:
            logging.info(f"【{self.site_name}】开始执行签到任务")

            # 首先尝试读取cookie文件
            accounts = self.read_cookie_file()
            if accounts:
                logging.info("[Cookie文件]检测到cookie文件，将尝试使用")
                for email, account_data in accounts.items():
                    session = requests.Session()
                    for cookie_item in account_data['cookies'].split(';'):
                        key, value = cookie_item.split('=', 1)
                        session.cookies.set(key.strip(), value.strip())

                    # 检查cookie是否有效
                    if self.check_cookie_valid(DEFAULT_HOST, session):
                        logging.info("")
                        logging.info(f"[Cookie检测]账号 {email} 的Cookie有效")
                        # 执行签到任务
                        self.do_task(DEFAULT_HOST, session)
                        logging.info("")
                        # 如果是最后一个账号，执行return
                        if email == list(accounts.keys())[-1]:
                            return
                    else:
                        logging.warning(f"[Cookie文件]账号 {email} 的Cookie已失效")

                logging.info("[Cookie文件]所有账号的Cookie都已失效，尝试使用邮箱密码登录")
                # 检查环境变量中是否有邮箱密码
                env = os.getenv("kmacg")
                if not env or '&' not in env:
                    logging.error("[Cookie文件]所有Cookie已失效且环境变量中未找到邮箱密码，无法继续")
                    return
                # 删除失效的cookie文件
                try:
                    os.remove(self.cookie_file)
                    logging.info(f"[Cookie文件]已删除失效的cookie文件: {self.cookie_file}")
                except Exception as e:
                    logging.error(f"[Cookie文件]删除失效cookie文件失败: {str(e)}")

            host = DEFAULT_HOST
            for index, (email, password, cookie) in enumerate(self.check_env(), 1):
                logging.info("")
                logging.info(f"------【账号{index}】开始执行任务------")

                # 创建会话
                session = requests.Session()

                if cookie:
                    # 直接使用cookie
                    logging.info(f"[检查环境变量]检测到cookie，将直接使用并保存到文件")
                    for cookie_item in cookie.split(';'):
                        key, value = cookie_item.split('=', 1)
                        session.cookies.set(key.strip(), value.strip())
                    self.write_cookie_file(cookie, email)

                    # 检查cookie是否有效
                    if self.check_cookie_valid(host, session):
                        logging.info(f"[Cookie]账号 {email} 的Cookie有效")
                        # 执行签到任务
                        self.do_task(host, session)
                        return
                    else:
                        logging.warning(f"[Cookie]账号 {email} 的Cookie已失效")
                        continue
                else:
                    logging.info(f"[检查环境变量]检测到邮箱密码，将进行登录")
                    # 获取参数
                    formhash, seccodehash, loginhash = self.get_param(host, session)
                    if not all([formhash, seccodehash, loginhash]):
                        logging.error("获取参数失败，跳过当前账号")
                        continue

                    # 验证码重试逻辑
                    max_retries = 3
                    retry_count = 0
                    while retry_count < max_retries:
                        login_in_captcha = self.get_captcha_img(host, seccodehash, session)
                        login_in_captcha_text = self.get_captcha_text(login_in_captcha)
                        if self.check_captcha(host, login_in_captcha_text, session, seccodehash):
                            break

                        retry_count += 1
                        if retry_count < max_retries:
                            logging.warning(f"[验证码]验证失败，第{retry_count}次重试")
                            time.sleep(5)
                        else:
                            logging.error("[验证码]验证失败，已达到最大重试次数")
                            continue

                    if not self.login_in(host, email, password, formhash, login_in_captcha_text, session, loginhash, seccodehash):
                        logging.error("登录失败，跳过当前账号")
                        continue

                    # 登录成功后保存cookie到文件
                    cookies = self.get_session_cookies(session)
                    if cookies:
                        self.write_cookie_file(cookies, email)

                    # 登录成功后执行签到任务
                    self.do_task(host, session)

                logging.info(f"------【账号{index}】执行任务完成------")
                logging.info("")
        except Exception as e:
            logging.error(f"【{self.site_name}】执行过程中发生错误: {str(e)}\n{traceback.format_exc()}")

if __name__ == "__main__":
    auto_task = AutoTask("快萌论坛")
    auto_task.run()
