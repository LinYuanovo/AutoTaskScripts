import requests
import os
import logging
import traceback
from datetime import datetime

class WechatCodeAdapter:
    def __init__(self, wx_appid):
        """
        初始化微信授权适配器
        """
        self.wx_code_url = os.getenv("soy_codeurl_data")
        self.wx_code_token = os.getenv("soy_codetoken_data")
        self.wx_appid = wx_appid # 微信小程序id
        self.wx_protocol_type = 0 # 微信协议类型
        self.wx_accounts_list = [] # 微信账号列表
        self.log_msgs = []  # 日志收集
        self._init_protocol_type()
        self._init_all_accounts()
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
        if self.wx_code_url:
            end_url = self.wx_code_url.split("/")[-1]
        else:
            end_url = ""
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

    def _init_protocol_type(self):
        """
        初始化微信协议类型
        """
        self.wx_protocol_type = self.get_protocol_type()
        
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

    def _init_all_accounts(self):
        """
        初始化微信账号列表
        """
        if self.wx_protocol_type == 3:
            self.wx_accounts_list = self.get_all_devices()
        elif self.wx_protocol_type == 4:
            self.wx_accounts_list = self.get_auth_keys()
        
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
            response = requests.get(url, params=params, timeout=15)
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
            all_devices = self.wx_accounts_list
            if not all_devices:
                self.log(f"[获取code] 账号列表为空，未能获取到", level="error")
                return False
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
        
    def get_auth_keys(self):
        """
        iwechat 获取账号授权码列表
        :return: 账号授权码列表
        """
        try:
            url = self.wx_code_url
            params = {
                "key": self.wx_code_token
            }
            response = requests.get(url, params=params, timeout=15)
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
            auth_keys = self.wx_accounts_list
            if not auth_keys:
                self.log(f"[获取code] 账号列表为空，未能获取到", level="error")
                return False
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