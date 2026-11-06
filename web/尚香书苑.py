"""
作者: 临渊
日期: 2025/6/8
name: 尚香书苑
入口: 发布页 (https://sxsy.pw/)
功能: 登录、签到
变量: sxsy='邮箱&密码' 或者 'cookie'
        自动检测，多个账号用换行分割
        使用邮箱密码将会进行登录（必须有ocr服务地址）
        使用cookie将会直接使用
定时: 一天两次
cron: 10 9,10 * * *
------------更新日志------------
2025/6/8    V1.0    初始化，完成签到功能
2025/6/11   V1.1    变量增加邮箱密码支持
2025/6/17   V1.2    增加cookie存储功能
2025/7/28   V1.3    修改头部注释，以便拉库
2025/8/27   V1.4    修改默认域名
2026/11/6   V1.5    从发布页 https://sxsy.pw/ 获取最新域名，适配新版 sx_signin 签到插件（带图形验证码）
"""

DEFAULT_HOST = "sxsy33.com" # 默认域名
GUIDE_URL = "https://sxsy.pw/" # 发布页，用于获取最新域名
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36 Edg/137.0.0.0"

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
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

DDDD_OCR_URL = os.getenv("DDDD_OCR_URL") or "" # dddd_ocr地址

class HTTP11Adapter(HTTPAdapter):
    """
    强制使用 HTTP/1.1，站点对 HTTP/2 支持不稳定，容易出现 SSLEOFError
    """
    def init_poolmanager(self, *args, **kwargs):
        context = create_urllib3_context()
        context.set_alpn_protocols(['http/1.1'])
        kwargs['ssl_context'] = context
        return super().init_poolmanager(*args, **kwargs)

def new_session():
    session = requests.Session()
    adapter = HTTP11Adapter()
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    session.headers.update({'User-Agent': UA})
    return session

def request(session, method, url, retries=4, **kwargs):
    """
    带重试的请求，站点偶尔会直接断开连接（SSLEOFError / 超时）
    """
    kwargs.setdefault('timeout', 60)
    for i in range(retries):
        try:
            return session.request(method, url, **kwargs)
        except requests.RequestException as e:
            if i == retries - 1:
                raise
            wait = 3 * (i + 1)
            logging.warning(f"[网络]请求失败({str(e)})，{wait}秒后第{i + 1}次重试")
            time.sleep(wait)

class AutoTask:
    def __init__(self, site_name):
        """
        初始化自动任务类
        :param site_name: 站点名称，用于日志显示
        """
        self.site_name = site_name
        self.cookie_file = f"{site_name}_cookie.json"
        self.host = DEFAULT_HOST
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
            env = os.getenv("sxsy")
            if not env:
                logging.error("[检查环境变量]没有找到环境变量sxsy")
                return
            # 多个账号用换行分割
            envs = env.split('\n')
            for env in envs:
                env = env.strip()
                if not env:
                    continue
                if '&' in env:
                    # 邮箱和密码以第一个 & 分隔，密码可包含 &
                    email, password = env.split('&', 1)
                    yield email, password, None
                else:
                    # 直接使用cookie
                    yield None, None, env
        except Exception as e:
            logging.error(f"[检查环境变量]发生错误: {str(e)}\n{traceback.format_exc()}")
            raise

    def get_host(self):
        """
        从发布页获取最新域名
        :return: host
        """
        try:
            # 访问发布页（该站响应较慢，超时放宽）
            headers = {
                'User-Agent': UA
            }
            response = request(new_session(), "GET", GUIDE_URL, headers=headers, timeout=60)
            response.raise_for_status()

            # 发布页为静态页面，域名写在 CONFIG 中：latestDomain:"sxsy33.com"
            pattern = r'latestDomain\s*:\s*"([^"]+)"'
            match = re.search(pattern, response.text)
            if match:
                host = match.group(1)
                # 兼容带协议头或路径的写法
                host = re.sub(r'^https?://', '', host).strip('/').strip()
                logging.info(f"[获取host]{host}")
                self.host = host
                return host
            # 兼容旧版发布页：直接给出跳转链接
            pattern = r'href="https://(.*?)/'
            match = re.search(pattern, response.text)
            if match:
                host = match.group(1)
                logging.info(f"[获取host]{host}")
                self.host = host
                return host
            logging.warning("[获取host]无法获取host，使用默认域名")
            return DEFAULT_HOST  # 如果无法获取，返回默认域名
        except requests.RequestException as e:
            logging.warning(f"[获取host]发生网络错误({str(e)})，使用默认域名")
            return DEFAULT_HOST
        except Exception as e:
            logging.error(f"[获取host]发生未知错误: {str(e)}\n{traceback.format_exc()}")
            return DEFAULT_HOST

    def get_param(self, host, session):
        """
        获取参数
        :param host: 域名
        :param session: 会话对象
        :return: formhash, seccodehash, loginhash
        """
        try:
            # 访问首页
            url = f"https://{host}/member.php?mod=logging&action=login&infloat=yes&frommessage&inajax=1&ajaxtarget=messagelogin"
            headers = {
                'User-Agent': UA,
                'Host': host
            }
            response = request(session, "GET", url, headers=headers)
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
            # seccodehash 格式: seccode_cSAbDg cSAbDg
            pattern = r'seccode_([a-zA-Z0-9]{6})'
            match = re.search(pattern, response.text)
            if match:
                seccodehash = match.group(1)
            else:
                logging.error("[获取seccodehash]无法获取seccodehash")
                return None, None, None
            # loginhash 格式: main_messaqge_LCpo4 LCpo4
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
                'User-Agent': UA,
                'Host': host
            }
            response = request(session, "GET", url, headers=headers)
            response.raise_for_status()
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
            if not DDDD_OCR_URL:
                logging.error("[获取验证码]未配置 DDDD_OCR_URL")
                return None
            url = DDDD_OCR_URL
            payload = {
                'image': img_base64
            }
            response = requests.post(url, data=payload, timeout=60).json()
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
                'User-Agent': UA,
                'Host': host
            }
            response = request(session, "GET", url, headers=headers)
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
                'User-Agent': UA,
                'Host': host
            }
            # payload转为url编码，/替换为%2F
            payload = urllib.parse.quote(payload, safe='=&')
            response = request(session, "POST", url, headers=headers, data=payload)
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

    def get_sign_config(self, host, session):
        """
        获取签到插件配置（新版插件 sx_signin）
        :param host: 域名
        :param session: 会话对象
        :return: SIGNIN 配置字典
        """
        try:
            url = f"https://{host}/plugin.php?id=sx_signin:index"
            headers = {
                'User-Agent': UA,
                'Host': host
            }
            response = request(session, "GET", url, headers=headers)
            response.raise_for_status()

            # 页面内联脚本: window.SIGNIN = {"ajax":"...","formhash":"...","signed":0,...};
            pattern = r'window\.SIGNIN\s*=\s*(\{.*?\});\s*</script>'
            match = re.search(pattern, response.text, re.S)
            if match:
                config = json.loads(match.group(1))
                # 已签到时配置里没有连续签到天数，从页面元素补充
                streak = re.search(r'id="signin-streak">(\d+)<', response.text)
                total = re.search(r'id="signin-total">(\d+)<', response.text)
                if streak:
                    config['streak'] = streak.group(1)
                if total:
                    config['total'] = total.group(1)
                return config
            logging.warning("[签到]未找到签到插件配置，可能是旧版插件或未登录")
            return None
        except Exception as e:
            logging.error(f"[签到]获取签到配置失败: {str(e)}\n{traceback.format_exc()}")
            return None

    def signin(self, host, session, config):
        """
        签到（新版 sx_signin 插件，需要图形验证码）
        :param host: 域名
        :param session: 会话对象
        :param config: 签到插件配置
        """
        try:
            if not config:
                logging.error("[签到]签到配置为空，无法进行签到")
                return
            if config.get('signed'):
                logging.info(f"[签到]今日已签到，连续签到 {config.get('streak', '?')} 天")
                return
            if config.get('captcha') and not DDDD_OCR_URL:
                logging.error("[签到]签到需要图形验证码，请配置 DDDD_OCR_URL")
                return

            headers = {
                'User-Agent': UA,
                'Host': host,
                'Referer': f'https://{host}/plugin.php?id=sx_signin:index'
            }
            max_retries = 5
            for i in range(1, max_retries + 1):
                # 验证码图片
                captcha_url = f"{config['captchaUrl']}&t={int(time.time() * 1000)}"
                img = request(session, "GET", captcha_url, headers=headers)
                img.raise_for_status()
                captcha = self.get_captcha_text(base64.b64encode(img.content).decode('utf-8'))
                if not captcha:
                    logging.warning(f"[签到]验证码识别失败，第{i}次重试")
                    time.sleep(3)
                    continue

                payload = {
                    'op': 'signin',
                    'formhash': config['formhash'],
                    'seccode': captcha
                }
                response = request(session, "POST", config['ajax'], headers=headers, data=payload)
                result = response.json()
                code = result.get('code')
                if code in (0, 2):
                    # 0: 签到成功, 2: 今天已经签到过了
                    logging.info(f"[签到]{result.get('msg')}")
                    data = result.get('data') or {}
                    if data:
                        logging.info(f"[签到]连续签到 {data.get('streak', '?')} 天，"
                                     f"累计 {data.get('total', '?')} 天，本次奖励 {data.get('today_credit', '?')} 金钱")
                    return
                if code == 11:
                    logging.warning(f"[签到]验证码错误，第{i}次重试")
                    time.sleep(2)
                    continue
                logging.warning(f"[签到]签到失败: {result.get('msg')}")
                return
            logging.error(f"[签到]验证码连续 {max_retries} 次识别失败，签到未完成")
        except Exception as e:
            logging.error(f"[签到]发生未知错误: {str(e)}\n{traceback.format_exc()}")

    def get_user_info(self, host, session, print_info=False):
        """
        获取用户信息
        :param host: 域名
        :param session: 会话对象
        :param print_info: 是否打印信息
        :return: uid
        """
        try:
            url = f"https://{host}/home.php?mod=spacecp&ac=credit&showcredit=1"
            headers = {
                'User-Agent': UA,
                'Host': host
            }
            response = request(session, "GET", url, headers=headers)
            response.raise_for_status()

            # 使用正则表达式匹配金钱数量
            money_pattern = r'金钱: </em>(\d+)'
            match = re.search(money_pattern, response.text)
            uid_pattern = r'uid=(\d+)'
            uid_match = re.search(uid_pattern, response.text)
            if match:
                money = match.group(1)
                uid = uid_match.group(1) if uid_match else None
                if print_info:
                    logging.info(f"[用户{uid}]现有金钱 {money}")
                return uid
            logging.warning("[获取用户信息]无法获取用户金钱信息")
            return None
        except requests.RequestException as e:
            logging.error(f"[获取用户信息]发生网络错误: {str(e)}\n{traceback.format_exc()}")
            return None
        except Exception as e:
            logging.error(f"[获取用户信息]发生未知错误: {str(e)}\n{traceback.format_exc()}")
            return None

    def get_promotion_reward(self, host, uid):
        """
        获取推广奖励
        :param host: 域名
        :param uid: uid
        """
        try:
            if not uid:
                return
            url = f"https://{host}/?fromuid={uid}"
            headers = {
                'User-Agent': UA,
                'Host': host,
                'Referer': f'https://{host}/'
            }
            # 不带cookie直接访问
            response = request(new_session(), "GET", url, headers=headers, retries=2)
            response.raise_for_status()
        except requests.RequestException as e:
            logging.warning(f"[获取推广奖励]访问失败: {str(e)}")
        except Exception as e:
            logging.error(f"[获取推广奖励]发生未知错误: {str(e)}\n{traceback.format_exc()}")

    def do_task(self, host, session):
        """
        执行任务
        :param host: 域名
        :param session: 会话对象
        """
        try:
            config = self.get_sign_config(host, session)
            if config:
                self.signin(host, session, config)
            uid = self.get_user_info(host, session, print_info=True)
            self.get_promotion_reward(host, uid)
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
                'host': self.host or DEFAULT_HOST,
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
                'User-Agent': UA,
                'Host': host
            }
            response = request(session, "GET", url, headers=headers)
            response.raise_for_status()

            # 未登录时 discuz_uid 为 '0'，登录后为真实 uid
            uid_match = re.search(r"discuz_uid = '(\d+)'", response.text)
            return bool(uid_match and uid_match.group(1) != '0')
        except Exception as e:
            logging.error(f"[Cookie检测]发生错误: {str(e)}\n{traceback.format_exc()}")
            return False

    def create_session(self, cookie=None):
        """
        创建会话
        :param cookie: cookie字符串，可为空
        :return: 会话对象
        """
        session = new_session()
        if cookie:
            for cookie_item in cookie.split(';'):
                if '=' not in cookie_item:
                    continue
                key, value = cookie_item.split('=', 1)
                session.cookies.set(key.strip(), value.strip())
        return session

    def login(self, host, email, password, session):
        """
        邮箱密码登录（含验证码重试）
        :param host: 域名
        :param email: 邮箱
        :param password: 密码
        :param session: 会话对象
        :return: 是否成功
        """
        if not DDDD_OCR_URL:
            logging.error("[登录]未配置 DDDD_OCR_URL，无法识别验证码")
            return False

        max_retries = 3
        for retry in range(1, max_retries + 1):
            formhash, seccodehash, loginhash = self.get_param(host, session)
            if not all([formhash, seccodehash, loginhash]):
                logging.error("获取参数失败，跳过当前账号")
                return False

            captcha_img = self.get_captcha_img(host, seccodehash, session)
            if not captcha_img:
                logging.warning(f"[验证码]获取验证码图片失败，第{retry}次重试")
                time.sleep(3)
                continue
            captcha_text = self.get_captcha_text(captcha_img)
            if not captcha_text:
                logging.warning(f"[验证码]验证码识别失败，第{retry}次重试")
                time.sleep(3)
                continue
            if not self.check_captcha(host, captcha_text, session, seccodehash):
                logging.warning(f"[验证码]验证失败，第{retry}次重试")
                time.sleep(3)
                continue

            return self.login_in(host, email, password, formhash, captcha_text, session, loginhash, seccodehash)

        logging.error("[验证码]验证失败，已达到最大重试次数")
        return False

    def run(self):
        """
        执行签到任务的主函数
        """
        try:
            logging.info(f"【{self.site_name}】开始执行签到任务")

            # 先获取最新域名
            host = self.get_host()

            # 尝试使用本地保存的cookie
            accounts = self.read_cookie_file()
            if accounts:
                logging.info("[Cookie文件]检测到cookie文件，将尝试使用")
                logged_email = None
                for email, account_data in accounts.items():
                    session = self.create_session(account_data.get('cookies'))
                    if self.check_cookie_valid(host, session):
                        logging.info(f"[Cookie检测]账号 {email} 的Cookie有效")
                        logging.info("")
                        self.do_task(host, session)
                        logging.info("")
                        logged_email = email
                    else:
                        logging.warning(f"[Cookie文件]账号 {email} 的Cookie已失效")

                # 已用cookie文件完成全部任务
                if logged_email:
                    logging.info("【Cookie文件】任务执行完成")
                    return

                logging.info("[Cookie文件]所有账号的Cookie都已失效，尝试使用邮箱密码登录")
                # 检查环境变量中是否有邮箱密码
                env = os.getenv("sxsy")
                if not env or '&' not in env:
                    logging.error("[Cookie文件]所有Cookie已失效且环境变量中未找到邮箱密码，无法继续")
                    return
                # 删除失效的cookie文件
                try:
                    os.remove(self.cookie_file)
                    logging.info(f"[Cookie文件]已删除失效的cookie文件: {self.cookie_file}")
                except Exception as e:
                    logging.error(f"[Cookie文件]删除失效cookie文件失败: {str(e)}")

            for index, (email, password, cookie) in enumerate(self.check_env(), 1):
                logging.info("")
                logging.info(f"------【账号{index}】开始执行任务------")

                session = self.create_session(cookie)

                if cookie:
                    # 直接使用cookie
                    logging.info("[检查环境变量]检测到cookie，将直接使用")
                    if not self.check_cookie_valid(host, session):
                        logging.warning(f"[Cookie]账号 {email} 的Cookie已失效")
                        continue
                    self.write_cookie_file(cookie, email)
                    logging.info(f"[Cookie]账号 {email} 的Cookie有效")
                    self.do_task(host, session)
                else:
                    logging.info("[检查环境变量]检测到邮箱密码，将进行登录")
                    if not self.login(host, email, password, session):
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
    auto_task = AutoTask("尚香书苑")
    auto_task.run()
