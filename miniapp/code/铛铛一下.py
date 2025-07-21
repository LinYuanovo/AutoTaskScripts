"""
 作者： 临渊
 日期： 2025/6/24
 小程序：   铛铛一下
 功能： 签到、抽奖
 变量： soy_wxid_data (微信id) 多个账号用换行分割 
       soy_codetoken_data (微信授权token)
       soy_codeurl_data (微信授权url)
       PROXY_API_URL (代理api，返回一条txt文本，内容为代理ip:端口)
 定时： 一天两次
 cron： 10 8,9 * * *
 更新日志：
 2025/6/24  V1.0    初始化脚本
 2025/6/30  V1.1    修复提现问题
 2025/7/7   V1.2    适配更多协议
 2025/7/21  V1.3    适配更多协议
"""

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

DEFAULT_WITHDRAW_BALANCE = 0.3 # 默认超过该金额进行提现，需大于等于0.3
MULTI_ACCOUNT_SPLIT = ["\n", "@"] # 分隔符列表
MULTI_ACCOUNT_PROXY = False # 是否使用多账号代理，默认不使用，True则使用多账号代理
NOTIFY = os.getenv("LY_NOTIFY") or False # 是否推送日志，默认不推送，True则推送

class WechatCodeAdapter:
    def __init__(self):
        """
        初始化微信授权适配器
        """
        self.wx_code_url = os.getenv("soy_codeurl_data")
        self.wx_code_token = os.getenv("soy_codetoken_data")
        self.wx_appid = "wxe378d2d7636c180e" # 微信小程序id
        self.log_msgs = []  # 日志收集
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
                # logging.FileHandler(f'{self.script_name}_{datetime.now().strftime("%Y%m%d")}.log', encoding='utf-8'),  # 保存日志
                logging.StreamHandler()
            ]
        )

    def log(self, msg, level="info"):
        if level == "info":
            logging.info(msg)
        elif level == "error":
            logging.error(msg)
        elif level == "warning":
            logging.warning(msg)
        self.log_msgs.append(msg)

    def get_protocol_type(self):
        """
        获取协议类型
        :return: 协议类型
        """
        end_url = self.wx_code_url.split("/")[-1]
        if end_url == "getMiniProgramCode":
            # 养鸡场
            return 1
        elif end_url == "code":
            # 牛子
            return 2
        elif end_url == "GetAllDevices":
            # WeChatPadPro
            return 3
        elif end_url == "GetAuthKey":
            # iwechat
            return 4
        else:
            # 其他不知道的协议
            return 0
        
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
        
    def get_code_1(self, wx_id):
        """
        养鸡场 获取code
        :param wx_id: 微信id
        :return: code
        """
        try:
            url = self.wx_code_url
            headers = {
                "Authorization": self.wx_code_token,
                "Content-Type": "application/json"
            }
            payload = {"wxid": wx_id, "appid": self.wx_appid}
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
    
    def get_code_2(self, wx_id):
        """
        牛子 获取code
        :param wx_id: 微信id
        :return: code
        """
        try:
            url = self.wx_code_url
            headers = {
                "Content-Type": "application/json"
            }
            payload = {"wxid": wx_id, "appid": self.wx_appid}
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
        
    def get_all_devices(self):
        """
        WeChatPadPro 获取账号授权码列表
        :return: 账号授权码列表
        """
        try:
            url = self.wx_code_url
            params = {
                "key": self.wx_code_token
            }
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            response_json = response.json()
            if response_json.get('Code') == 200:
                all_devices = response_json.get('Data', {}).get('devices', [])
                if all_devices:
                    return all_devices
                else:
                    self.log(f"[获取账号授权码列表] 返回信息: {response_json['Text']}", level="error")
                    return []
            else:
                self.log(f"[获取账号授权码列表] 失败，错误信息: {response_json['Text']}", level="error")
                return []
        except Exception as e:
            self.log(f"[获取账号授权码列表] 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return []
        
    def get_target_key_by_wxid(self, all_keys, wx_id):
        """
        获取指定微信id的授权码
        :param all_keys: 所有账号授权码列表
        :param wx_id: 微信id
        :return: 指定微信id的授权码
        """
        for key in all_keys:
            _wx_id = key.get('deviceId') or key.get('wx_id')
            if _wx_id == wx_id:
                return key.get('authKey') or key.get('license')
        return None
    
    def get_code_3(self, wx_id):
        """
        WeChatPadPro 获取code
        :param wx_id: 微信id
        :return: code
        """
        try:
            all_devices = self.get_all_devices()
            target_key = self.get_target_key_by_wxid(all_devices, wx_id)
            url = self.wx_code_url.split("/admin")[0] + "/applet/JsLogin"
            params = {
                "key": target_key
            }
            payload = {
                "AppId": self.wx_appid,
                "Data": "",
                "Opt": 1,
                "PackageName": "",
                "SdkName": ""
            }
            response = requests.post(url, params=params, json=payload, timeout=5)
            response.raise_for_status()
            response_json = response.json()
            if response_json.get('Code') == 200:
                # self.log(f"[获取code] 成功，code: {response_json.get('Data', {}).get('Code', '')}")
                return response_json.get('Data', {}).get('Code', '')
            else:
                self.log(f"[获取code] 失败，错误信息: {response_json['Text']}", level="error")
                return False
        except Exception as e:
            self.log(f"[获取code] 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def get_auth_keys(self, wx_id):
        """
        iwechat 获取账号授权码列表
        :return: 账号授权码列表
        """
        try:
            url = self.wx_code_url
            params = {
                "key": self.wx_code_token
            }
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            response_json = response.json()
            return response_json
        except Exception as e:
            self.log(f"[获取code] 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def get_code_4(self, wx_id):
        """
        iwechat 获取code
        :param wx_id: 微信id
        :return: code
        """
        try:
            auth_keys = self.get_auth_keys()
            target_key = self.get_target_key_by_wxid(auth_keys, wx_id)
            url = self.wx_code_url.split("/admin")[0] + "/applet/JsLogin"
            params = {
                "key": target_key
            }
            payload = {
                "AppId": self.wx_appid,
                "Data": "",
                "Opt": 1,
                "PackageName": "",
                "SdkName": ""
            }
            response = requests.post(url, params=params, json=payload, timeout=5)
            response.raise_for_status()
            response_json = response.json()
            if response_json.get('Code') == 200:
                self.log(f"[获取code] 成功，code: {response_json.get('Data', {}).get('Code', '')}")
                return response_json.get('Data', {}).get('Code', '')
            else:
                self.log(f"[获取code] 失败，错误信息: {response_json['Text']}", level="error")
                return False
        except Exception as e:
            self.log(f"[获取code] 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def get_code(self, wx_id):
        """
        获取code
        :param wx_id: 微信id
        :return: 指定wxid的code
        """
        protocol_type = self.get_protocol_type()
        if protocol_type == 1:
            return self.get_code_1(wx_id)
        elif protocol_type == 2:
            return self.get_code_2(wx_id)
        elif protocol_type == 3:
            return self.get_code_3(wx_id)
        elif protocol_type == 4:
            return self.get_code_4(wx_id)
        else:
            self.log(f"[获取code] 发生错误: 未知协议类型", level="error")
            return False

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
    def __init__(self, script_name):
        """
        初始化自动任务类
        :param script_name: 站点名称，用于日志显示
        """
        self.script_name = script_name
        self.wechat_code_adapter = WechatCodeAdapter()
        self.proxy_url = os.getenv("PROXY_API_URL") # 代理api，返回一条txt文本，内容为代理ip:端口
        self.host = "vues.dd1x.cn"
        self.user_agent = "Mozilla/5.0 (Linux; Android 12; M2012K11AC Build/SKQ1.220303.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/134.0.6998.136 Mobile Safari/537.36 XWEB/1340129 MMWEBSDK/20240301 MMWEBID/9871 MicroMessenger/8.0.48.2580(0x28003036) WeChat/arm64 Weixin NetType/WIFI Language/zh_CN ABI/arm64 MiniProgramEnv/android"
    
    def log(self, msg, level="info"):
        self.wechat_code_adapter.log(msg, level)

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
            url = f"http://{self.host}/api/v2/get_sign_list"
            session.headers["Token"] = ""
            response = session.get(url, timeout=5)
            if response.status_code == 200:
                logging.info(f"[检查代理]: {proxy} 应该可用")
                return True
            else:
                logging.info(f"[检查代理]: {response.text}")
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
            if not soy_wxid_data:
                logging.error(f"[检查环境变量]没有找到环境变量soy_wxid_data，请检查环境变量")
                return None

            # 自动检测分隔符
            split_char = None
            for sep in MULTI_ACCOUNT_SPLIT:
                if sep in soy_wxid_data:
                    split_char = sep
                    break
            if not split_char:
                # 如果都没有分隔符，默认当作单账号
                soy_wxid_datas = [soy_wxid_data]
            else:
                soy_wxid_datas = soy_wxid_data.split(split_char)

            for soy_wxid_data in soy_wxid_datas:
                if "=" in soy_wxid_data:
                    soy_wxid_data = soy_wxid_data.split("=")[1]
                    yield soy_wxid_data
                else:
                    yield soy_wxid_data
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
        
    def wxlogin(self, session, code):
        """
        登录
        :param session: session
        :param code: 微信code
        :return: 登录结果
        """
        try:
            url = f"https://{self.host}/wechat/login"
            params = {
                "code": code,
                "channelId": 154
            }
            response = session.get(url, params=params)
            response.raise_for_status()
            response_json = response.json()
            if response_json['code'] == 0:
                tel = response_json['data']['tel']
                # 号码中间4位*号代替    
                tel = tel[:3] + "****" + tel[-4:]
                logging.info(f"[登录]成功: 当前账号 {tel}")
                token = response_json['data']['token']
                session.headers["Token"] = token
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
            url = f"https://{self.host}/api/v2/sign_join"
            response = session.get(url)
            response.raise_for_status()
            response_json = response.json()
            if response_json['code'] == 0:
                logging.info(f"[签到]: 成功")
                return True
            else:
                logging.warning(f"[签到]: {response_json['msg']}")
                return False
        except Exception as e:
            logging.error(f"[签到]发生错误: {str(e)}\n{traceback.format_exc()}")
            return False
        
    def add_lottery_count(self, session):
        """
        增加抽奖次数
        :param session: session
        :return: 增加抽奖次数结果
        """
        try:
            url = f"https://{self.host}/front/activity/add_lottery_count"
            response = session.get(url)
            response.raise_for_status()
            response_json = response.json()
            if response_json['code'] == 0:
                logging.info(f"[增加抽奖次数]: 成功")
                return True
            elif "达到上限" in response_json['msg']:
                logging.warning(f"[增加抽奖次数]: {response_json['msg']}")
                return False
            else:
                logging.error(f"[增加抽奖次数]发生错误: {response_json['msg']}")
                return False
        except Exception as e:
            logging.error(f"[增加抽奖次数]发生错误: {str(e)}\n{traceback.format_exc()}")
            return False
        
    def update_lottery_result(self, session):
        """
        更新抽奖结果
        :param session: session
        :return: 更新抽奖结果结果
        """
        try:
            url = f"https://{self.host}/front/activity/update_lottery_result"
            params = {
                "id": 3438615
            }
            response = session.get(url, params=params)
            response.raise_for_status()
            response_json = response.json()
            if response_json['code'] == 0:
                logging.info(f"[抽奖]: 获得{response_json['data']['goodName']}")
                return True 
            else:
                logging.warning(f"[抽奖]: {response_json['msg']}")
                return False
        except Exception as e:
            logging.error(f"[抽奖]发生错误: {str(e)}\n{traceback.format_exc()}")
            return False
    
    def get_withdrawal_trade_list(self, session):
        """
        获取提现相关数据
        :param session: session
        :return: 提现相关数据
        """
        try:
            url = f"https://{self.host}/api/h/get_withdrawal_trade_list"
            response = session.get(url)
            response.raise_for_status()
            response_json = response.json()
            if response_json['code'] == 0:
                balance = response_json['data'][0]['money']
                logging.info(f"[余额]: {balance}元")
                return balance, response_json['data']
            else:
                logging.error(f"[获取提现相关数据]发生错误: {response_json['msg']}")
                return False
        except Exception as e:
            logging.error(f"[获取提现相关数据]发生错误: {str(e)}\n{traceback.format_exc()}")
            return False
        
    def withdraw(self, session, balance, withdrawal_trade_list):
        """
        提现
        :param session: session
        :param balance: 余额
        :param withdrawal_trade_list: 提现相关数据
        :return: 提现结果
        """
        try:
            url = f"https://{self.host}/api/h/withdrawal"
            payload = {
                "totalMoney": balance,
                "type": 1,
                "withdrawalDetailPojoList": withdrawal_trade_list
            }
            response = session.post(url, json=payload)
            response.raise_for_status()
            response_json = response.json()
            if response_json['code'] == 0:
                logging.info(f"[提现]: {response_json['msg']}")
                return True
            else:
                logging.warning(f"[提现]: {response_json['msg']}")
                return False
        except Exception as e:
            logging.error(f"[提现]发生错误: {str(e)}\n{traceback.format_exc()}")
            return False
        
    def run(self):
        """
        运行任务
        """
        try:
            logging.info(f"【{self.script_name}】开始执行任务")
            
            # 检查环境变量
            for index, wx_id in enumerate(self.check_env(), 1):
                logging.info("")
                logging.info(f"------ 【账号{index}】开始执行任务 ------")

                if MULTI_ACCOUNT_PROXY:
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
                else:
                    session = requests.Session()

                session.headers["User-Agent"] = self.user_agent
                # 执行微信授权
                code = self.wechat_code_adapter.get_code(wx_id)
                if code:
                    login_result = self.wxlogin(session, code)
                    time.sleep(random.randint(1, 3))
                    if login_result:
                        # 签到
                        self.sign_in(session)
                        time.sleep(random.randint(1, 3))
                        # 抽奖
                        update_lottery_result_result = self.update_lottery_result(session)
                        while update_lottery_result_result:
                            time.sleep(random.randint(3, 5))
                            update_lottery_result_result = self.update_lottery_result(session)
                        # 增加抽奖次数
                        add_lottery_count_result = self.add_lottery_count(session)
                        while add_lottery_count_result:
                            self.update_lottery_result(session)
                            time.sleep(random.randint(3, 5))
                            add_lottery_count_result = self.add_lottery_count(session)
                        # 获取提现相关数据
                        balance, withdrawal_trade_list = self.get_withdrawal_trade_list(session)
                        if balance >= DEFAULT_WITHDRAW_BALANCE:
                            # 提现
                            self.withdraw(session, balance, withdrawal_trade_list)
                            time.sleep(random.randint(1, 3))
                        else:
                            logging.warning(f"[提现]: 余额不足{DEFAULT_WITHDRAW_BALANCE}元，不进行提现")
                            time.sleep(random.randint(1, 3))
                        
                logging.info(f"------ 【账号{index}】执行任务完成 ------")
        except Exception as e:
            logging.error(f"【{self.script_name}】执行过程中发生错误: {str(e)}\n{traceback.format_exc()}")
        finally:
            if NOTIFY:
                # 如果notify模块不存在，从远程下载至本地
                if not os.path.exists("notify.py"):
                    url = "https://raw.githubusercontent.com/whyour/qinglong/refs/heads/develop/sample/notify.py"
                    response = requests.get(url)
                    with open("notify.py", "w", encoding="utf-8") as f:
                        f.write(response.text)
                    import notify
                else:
                    import notify
                # 任务结束后推送日志
                title = f"{self.script_name} 运行日志"
                header = "作者：临渊\n\n"
                content = header + "\n" +"\n".join(self.wechat_code_adapter.log_msgs)
                notify.send(title, content)


if __name__ == "__main__":
    auto_task = AutoTask("铛铛一下")
    auto_task.run() 