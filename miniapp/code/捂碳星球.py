"""
 作者： 临渊
 日期： 2025/6/24
 小程序：   捂碳星球
 功能： 签到、满余额提现
 变量： soy_wxid_data soy_wxphone_data (微信id和微信手机号，必须一一对应，不知道号码就换行跳过) 多个账号用换行分割 
 定时： 一天一次
 cron： 10 8 * * *
 更新日志：
 2025/6/24 V1.0 初始化脚本
 2025/6/24 V1.1 添加代理
 2025/6/24 V1.2 添加代理检查
 2025/7/7  V1.3 适配更多协议
"""

DEFAULT_WITHDRAW_BALANCE = 1 # 默认超过该金额进行提现，需大于等于1
MULTI_ACCOUNT_SPLIT = ["\n", "@"] # 分隔符列表

import hashlib
import random
import time
import requests
import os
import logging
import traceback
import base64
import json
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from datetime import datetime

class WXBizDataCryptUtil:
    """
    微信小程序加解密工具
    """
    def __init__(self, sessionKey):
        self.sessionKey = sessionKey

    def encrypt(self, data, iv=None):
        """
        data: dict或str，若为dict自动转为json字符串
        iv: base64字符串，若为None自动生成
        返回: (加密数据base64, iv base64)
        """
        if isinstance(data, dict):
            data = json.dumps(data, separators=(',', ':'))
        if iv is None:
            iv_bytes = get_random_bytes(16)
            iv = base64.b64encode(iv_bytes).decode('utf-8')
        else:
            iv_bytes = base64.b64decode(iv)
        sessionKey = base64.b64decode(self.sessionKey)
        cipher = AES.new(sessionKey, AES.MODE_CBC, iv_bytes)
        padded = self._pad(data.encode('utf-8'))
        encrypted = cipher.encrypt(padded)
        encrypted_b64 = base64.b64encode(encrypted).decode('utf-8')
        return encrypted_b64, iv

    def decrypt(self, encryptedData, iv):
        """
        encryptedData: base64字符串
        iv: base64字符串
        返回: dict或str
        """
        sessionKey = base64.b64decode(self.sessionKey)
        encryptedData = base64.b64decode(encryptedData)
        iv = base64.b64decode(iv)
        cipher = AES.new(sessionKey, AES.MODE_CBC, iv)
        decrypted = self._unpad(cipher.decrypt(encryptedData))
        try:
            return json.loads(decrypted)
        except Exception:
            return decrypted.decode('utf-8')

    def _pad(self, s):
        pad_len = 16 - len(s) % 16
        return s + bytes([pad_len] * pad_len)

    def _unpad(self, s):
        return s[:-s[-1]]

class AutoTask:
    def __init__(self, site_name):
        """
        初始化自动任务类
        :param site_name: 站点名称，用于日志显示
        """
        self.site_name = site_name
        self.proxy_url = os.getenv("PROXY_API_URL") # 代理api，返回一条txt文本，内容为代理ip:端口
        self.wx_appid = "wx54c4768a6050a90e" # 微信小程序id
        self.wx_code_url = os.getenv("soy_codeurl_data")
        self.wx_code_token = os.getenv("soy_codetoken_data")
        self.host = "wt.api.5tan.com"
        self.user_agent = "Mozilla/5.0 (Linux; Android 12; M2012K11AC Build/SKQ1.220303.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/134.0.6998.136 Mobile Safari/537.36 XWEB/1340129 MMWEBSDK/20240301 MMWEBID/9871 MicroMessenger/8.0.48.2580(0x28003036) WeChat/arm64 Weixin NetType/WIFI Language/zh_CN ABI/arm64 MiniProgramEnv/android"
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
                # logging.FileHandler(f'{self.site_name}_{datetime.now().strftime("%Y%m%d")}.log', encoding='utf-8'),  # 保存日志
                logging.StreamHandler()
            ]
        )

    def get_proxy(self):
        """
        获取代理
        :return: 代理
        """
        if not self.proxy_url:
            logging.warning("[获取代理]没有找到环境变量PROXY_API_URL，不使用代理")
            return None
        url = self.proxy_url
        response = requests.get(url)
        proxy = response.text
        logging.info(f"[获取代理]: {proxy}")
        return proxy
    
    def check_proxy(self, proxy, session):
        """
        检查代理
        :param proxy: 代理
        :param session: session
        :return: 是否可用
        """
        try:
            url = f"http://{self.host}/api/user/index?platform=1"
            session.headers["Authorization"] = "Bearer"
            response = session.get(url, timeout=5)
            response_json = response.json()
            if response_json['code'] == 200:
                logging.info(f"[检查代理]: {proxy} 应该可用")
                return True
            else:
                logging.info(f"[检查代理]: {response_json['msg']}")
                return False
        except Exception as e:
            return False
        

    def check_env(self):
        """
        检查环境变量
        :return: 环境变量字符串
        """
        try:
            # 从环境变量获取cookie
            soy_wxid_data = os.getenv(f"soy_wxid_data")
            soy_wxphone_data = os.getenv(f"soy_wxphone_data")
            if not soy_wxid_data or not soy_wxphone_data:
                logging.error(f"[检查环境变量]没有找到环境变量soy_wxid_data或soy_wxphone_data，请检查环境变量")
                return None

            # 新增：自动检测分隔符
            split_char = None
            for sep in MULTI_ACCOUNT_SPLIT:
                if sep in soy_wxid_data and sep in soy_wxphone_data:
                    split_char = sep
                    break
            if not split_char:
                # 如果都没有分隔符，默认当作单账号
                soy_wxid_datas = [soy_wxid_data]
                soy_wxphone_datas = [soy_wxphone_data]
            else:
                soy_wxid_datas = soy_wxid_data.split(split_char)
                soy_wxphone_datas = soy_wxphone_data.split(split_char)

            for soy_wxid_data, soy_wxphone_data in zip(soy_wxid_datas, soy_wxphone_datas):
                if "=" in soy_wxid_data:
                    soy_wxid_data = soy_wxid_data.split("=")[1]
                    yield soy_wxid_data, soy_wxphone_data
                else:
                    yield soy_wxid_data, soy_wxphone_data
        except Exception as e:
            logging.error(f"[检查环境变量]发生错误: {str(e)}\n{traceback.format_exc()}")
            raise

    def dict_keys_to_lower(self, obj):
        """
        递归将字典的所有键名转为小写
        """
        if isinstance(obj, dict):
            return {k.lower(): self.dict_keys_to_lower(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self.dict_keys_to_lower(i) for i in obj]
        else:
            return obj
    
    def wx_code_auth(self, wx_id):
        """
        微信授权取code
        :param wx_id: 微信id
        :return: 微信code
        """
        try:
            url = self.wx_code_url
            headers = {
                "Authorization": self.wx_code_token,
                "Content-Type": "application/json"
            }
            payload = {
                "wxid": wx_id,
                "appid": self.wx_appid
            }
            response = requests.post(url, headers=headers, json=payload, timeout=5)
            response.raise_for_status()
            # 将所有键名转为小写
            response_json = self.dict_keys_to_lower(response.json())
            # 直接取授权code，不判断返回码code
            code_value = response_json.get('data', {}).get('code', '')
            if code_value:
                code = code_value
                return code
            else:
                self.log(f"[微信授权] 失败，错误信息: {response_json['message']}", level="error")
                return False
        except requests.RequestException as e:
            self.log(f"[微信授权]发生网络错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        except Exception as e:
            self.log(f"[微信授权]发生未知错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False

    def get_wxlogin(self, session, code):
        """
        获取wxlogin的参数
        :param session: session
        :param code: 微信code
        :return: sessionKey, openid, unionid
        """
        try:
            url = f"https://{self.host}/api/login/getWxLogin"
            session.headers["Authorization"] = "Bearer"
            session.headers["content-type"] = "application/json"
            session.headers["Xweb_xhr"] = "1"
            session.headers["User-Agent"] = self.user_agent
            session.headers["Host"] = self.host
            session.headers["Referer"] = "https://servicewechat.com/wx54c4768a6050a90e/218/page-frame.html"
            session.headers["authority"] = self.host
            payload = {
                "code": code,
            }
            response = session.post(url, json=payload)
            response.raise_for_status()
            response_json = response.json()
            if response_json['code'] == 200:
                return response_json['data']
            else:
                logging.error(f"[获取wxlogin的参数]发生错误: {response_json['msg']}")
                return False
        except requests.RequestException as e:
            logging.error(f"[获取wxlogin的参数]发生网络错误: {str(e)}\n{traceback.format_exc()}")
            return False
        
    def get_encryptedData(self, sessionKey, phone):
        """
        获取加密数据
        :param sessionKey: sessionKey
        :param phone: 手机号
        :return: 加密数据, iv
        """
        try:
            raw_data = {
                'phoneNumber': phone,
                'purePhoneNumber': phone,
                'countryCode': '86',
                'watermark': {
                    'timestamp': int(time.time()),
                    'appid': self.wx_appid
                }
            }
            wx_biz_data_crypt = WXBizDataCryptUtil(sessionKey)
            encrypted_data, iv = wx_biz_data_crypt.encrypt(raw_data)
            return encrypted_data, iv
        except Exception as e:
            logging.error(f"[获取加密数据]发生错误: {str(e)}\n{traceback.format_exc()}")
            return False
        
        
    def wxlogin(self, session, encryptedData, iv, openid, sessionKey, unionid):
        """
        登录
        :param session: session
        :param encryptedData: 加密数据
        :param iv: aes加密的iv
        :param openid: get_wxlogin返回的openid
        :param sessionKey: get_wxlogin返回的sessionKey
        :param unionid: get_wxlogin返回的unionid
        :return: 登录结果
        """
        try:
            url = f"https://{self.host}/api/login/wxLogin"
            payload = {
                "encryptedData": encryptedData,
                "errMsg": "getPhoneNumber:ok",
                "iv": iv,
                "openid": openid,
                "sessionKey": sessionKey,
                "unionid": unionid
            }
            response = session.post(url, json=payload)
            response.raise_for_status()
            response_json = response.json()
            if response_json['code'] == 200:
                logging.info(f"[登录]: user_id: {response_json['data']['user_id']}")
                token = response_json['data']['token']
                session.headers["Authorization"] = f"Bearer {token}"
                return True
            else:
                logging.error(f"[登录]发生错误: {response_json['msg']}")
                return False
        except requests.RequestException as e:
            logging.error(f"[登录]发生网络错误: {str(e)}\n{traceback.format_exc()}")
            return False
        except Exception as e:
            logging.error(f"[登录]发生错误: {str(e)}\n{traceback.format_exc()}")
            return False
        

    def sign_in(self, session):
        """
        签到
        :param session: session
        :return: 签到结果
        """
        try:
            url = f"https://{self.host}/api/signin/addSignIn"
            payload = {
                "platform": 1
            }
            response = session.post(url, json=payload)
            response.raise_for_status()
            response_json = response.json()
            logging.info(f"[签到]: {response_json['msg']}")
        except Exception as e:
            logging.error(f"[签到]发生错误: {str(e)}\n{traceback.format_exc()}")
            return False
        
    def get_user_balance(self, session):
        """
        获取用户余额
        :param session: session
        :return: 用户余额
        """
        try:
            url = f"https://{self.host}/api/logmoney/lst"
            response = session.get(url)
            response.raise_for_status()
            response_json = response.json()
            if response_json['code'] == 200:
                balance = response_json['money']
                logging.info(f"[余额]: {balance}")
                return balance
            else:
                logging.warning(f"[获取用户余额]: {response_json['msg']}")
                return 0
        except Exception as e:
            logging.error(f"[获取用户余额]发生错误: {str(e)}\n{traceback.format_exc()}")
            return 0
        
    def withdraw(self, session, balance):
        """
        提现
        :param session: session
        :param balance: 余额
        :return: 提现结果
        """
        try:
            url = f"https://{self.host}/api/logmoney/cash"
            payload = {
                "money": balance, 
                "platform": 1
            }
            response = session.post(url, json=payload)
            response.raise_for_status()
            response_json = response.json()
            logging.info(f"[提现]: {response_json['msg']}")
        except Exception as e:
            logging.error(f"[提现]发生错误: {str(e)}\n{traceback.format_exc()}")
            return False
        
    def run(self):
        """
        运行任务
        """
        try:
            logging.info(f"【{self.site_name}】开始执行任务")
            
            # 检查环境变量
            for index, (wx_id, wx_phone) in enumerate(self.check_env(), 1):
                logging.info("")
                logging.info(f"------ 【账号{index}】开始执行任务 ------")

                proxy = self.get_proxy()
                if proxy:
                    session = requests.Session()
                    session.proxies.update({"http": f"http://{proxy}", "https": f"http://{proxy}"})
                    # 检查代理，不可用重新获取
                    while not self.check_proxy(proxy, session):
                        proxy = self.get_proxy()
                        session.proxies.update({"http": f"http://{proxy}", "https": f"http://{proxy}"})
                else:
                    session = requests.Session()

                # 执行微信授权
                code = self.wx_code_auth(wx_id)
                if code:
                    # 获取wxlogin参数
                    wxlogin_data = self.get_wxlogin(session, code)
                    if wxlogin_data:
                        encrypted_data, iv = self.get_encryptedData(wxlogin_data['sessionKey'], wx_phone)
                        login_result = self.wxlogin(session, encrypted_data, iv, wxlogin_data['openid'], wxlogin_data['sessionKey'], wxlogin_data['unionid'])
                        if login_result:
                            # 签到
                            self.sign_in(session)
                            # 获取用户余额
                            balance = float(self.get_user_balance(session))
                            if balance >= DEFAULT_WITHDRAW_BALANCE:
                                # 提现
                                self.withdraw(session, balance)
                
                logging.info(f"------ 【账号{index}】执行任务完成 ------")
        except Exception as e:
            logging.error(f"【{self.site_name}】执行过程中发生错误: {str(e)}\n{traceback.format_exc()}")


if __name__ == "__main__":
    auto_task = AutoTask("捂碳星球")
    auto_task.run() 