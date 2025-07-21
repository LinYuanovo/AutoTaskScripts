"""
 作者:  临渊
 日期:  2025/6/22
 小程序:  飞蚂蚁 (https://a.c1ns.cn/iJAKu)
 功能:  签到、步数兑换、奖池投注、获取用户豆子
 变量:  soy_wxid_data (微信id) 多个账号用换行分割 
        soy_codetoken_data (微信授权token)
        soy_codeurl_data (微信授权url)
 定时:  一天三次
 cron:  10 6-8 * * *
 更新日志：
 2025/7/7   V1.0    初始化code版
 2025/7/21  V1.1    适配更多协议
"""

import random
import time
import requests
import os
import logging
import traceback
from datetime import datetime

MULTI_ACCOUNT_SPLIT = ["\n", "@"] # 分隔符列表
NOTIFY = os.getenv("LY_NOTIFY") or False # 是否推送日志，默认不推送，True则推送

class WechatCodeAdapter:
    def __init__(self):
        """
        初始化微信授权适配器
        """
        self.wx_code_url = os.getenv("soy_codeurl_data")
        self.wx_code_token = os.getenv("soy_codetoken_data")
        self.wx_appid = "wx501990400906c9ff" # 微信小程序id
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

class AutoTask:
    def __init__(self, script_name):
        """
        初始化自动任务类
        :param script_name: 站点名称，用于日志显示
        """
        self.script_name = script_name
        self.wechat_code_adapter = WechatCodeAdapter()
        self.host = "openapp.fmy90.com"
        self.userPhone = ""
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090b13) XWEB/9129"

    def log(self, msg, level="info"):
        self.wechat_code_adapter.log(msg, level)

    def check_env(self):
        """
        检查环境变量
        :return: 环境变量字符串
        """
        try:
            # 从环境变量获取cookie
            soy_wxid_data = os.getenv(f"soy_wxid_data")
            if not soy_wxid_data:
                self.log("[检查环境变量] 没有找到环境变量soy_wxid_data，请检查环境变量", level="error")
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
            self.log(f"[检查环境变量] 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
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
            code_value = response_json.get('data', {}).get('code')
            if code_value:
                code = code_value
                return code
            else:
                self.log(f"[微信授权]{response_json['msg']}", level="error")
                return False
        except requests.RequestException as e:
            self.log(f"[微信授权]发生网络错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        except Exception as e:
            self.log(f"[微信授权]发生未知错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def code_login(self, session, code):
        """
        微信授权登录
        :param session: session
        :param code: 微信code
        """
        try:
            url = f"https://{self.host}/auth/wx/login"
            payload = {
                "code": code,
                "platformKey": "F2EE24892FBF66F0AFF8C0EB532A9394",
                "version": "V2.00.01",
                "vital": "",
                "partner_platform_key": ""
            }
            response = session.post(url, data=payload)
            response.raise_for_status()
            response_json = response.json()
            token = response_json.get('data', {}).get('token', '')
            if token:
                session.headers['authorization'] = f"bearer {token}"
                return True
            else:
                self.log(f"[登录]发生错误: {response_json['message']}", level="error")
                return False
        except requests.RequestException as e:
            self.log(f"[登录]发生网络错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def sign_in(self, session):
        """
        执行签到
        :param session: session
        """
        try:
            url = f"https://{self.host}/sign/new/do"
            payload = {
                "version": "V2.00.01",
                "platformKey": "F2EE24892FBF66F0AFF8C0EB532A9394",
                "mini_scene": 1008,
                "partner_ext_infos": ""
            }
            response = session.post(url, data=payload)
            response.raise_for_status()
            response_json = response.json()
            self.log(f"[签到]: {response_json['message']}")
            if "过期" in response_json['message']:
                return False
            else:
                return True
        except requests.RequestException as e:
            logging.error(f"[签到]发生网络错误: {str(e)}\n{traceback.format_exc()}")
            return False
        except Exception as e:
            logging.error(f"[签到]发生未知错误: {str(e)}\n{traceback.format_exc()}")
            return False

    def step_exchange(self, session):
        """
        执行步数兑换
        :param session: session
        """
        try:
            url = f"https://{self.host}/step/exchange"
            payload = {
                "steps": 10000,
                "version": "V2.00.01",
                "platformKey": "F2EE24892FBF66F0AFF8C0EB532A9394",
                "mini_scene": 1008,
                "partner_ext_infos": ""
            }
            response = session.post(url, data=payload)
            response.raise_for_status()
            response_json = response.json()
            self.log(f"[步数兑换]: {response_json['message']}")
            if "每天最多兑换" in response_json['message']:
                return False
            else:
                return True
        except requests.RequestException as e:
            logging.error(f"[步数兑换]发生网络错误: {str(e)}\n{traceback.format_exc()}")
            return False
        except Exception as e:
            logging.error(f"[步数兑换]发生未知错误: {str(e)}\n{traceback.format_exc()}")
            return False
        
    def pool_bet(self, session):
        """
        执行奖池投注
        :param session: session
        """
        try:
            url = f"https://{self.host}/active/pool/bet"
            payload = {
                "version": "V2.00.01",
                "platformKey": "F2EE24892FBF66F0AFF8C0EB532A9394",
                "mini_scene": 1008,
                "partner_ext_infos": ""
            }
            response = session.post(url, data=payload)
            response.raise_for_status()
            response_json = response.json()
            self.log(f"[奖池投注]: {response_json['message']}")
            return True
        except requests.RequestException as e:
            logging.error(f"[奖池投注]发生网络错误: {str(e)}\n{traceback.format_exc()}")
            return False
        except Exception as e:
            logging.error(f"[奖池投注]发生未知错误: {str(e)}\n{traceback.format_exc()}")
            return False


    def pool_sign(self, session):
        """
        执行奖池签到
        :param session: session
        """
        try:
            url = f"https://{self.host}/active/pool/sign"
            payload = {
                "version": "V2.00.01",
                "platformKey": "F2EE24892FBF66F0AFF8C0EB532A9394",
                "mini_scene": 1008,
                "partner_ext_infos": ""
            }
            response = session.post(url, data=payload)
            response.raise_for_status()
            response_json = response.json()
            self.log(f"[奖池签到]: {response_json['message']}")
            return True
        except requests.RequestException as e:
            logging.error(f"[奖池签到]发生网络错误: {str(e)}\n{traceback.format_exc()}")
            return False
        except Exception as e:
            logging.error(f"[奖池签到]发生未知错误: {str(e)}\n{traceback.format_exc()}")
            return False

    def get_user_beans(self, session):
        """
        获取用户豆子
        :param session: session
        """
        try:
            url = f"https://{self.host}/user/new/beans/info"
            param = {
                "type": 1,
                "version": "V2.00.01",
                "platformKey": "F2EE24892FBF66F0AFF8C0EB532A9394",
                "mini_scene": 1008,
                "partner_ext_infos": ""
            }
            # 已获取豆子
            total_get_response = session.get(url, params=param)
            total_get_response_json = total_get_response.json()
            total_get_beans = total_get_response_json['data']['totalCount']
            param['type'] = 2
            # 已使用豆子
            total_use_response = session.get(url, params=param) 
            total_use_response_json = total_use_response.json()
            total_use_beans = total_use_response_json['data']['totalCount']
            # 豆子余额
            total_beans = total_get_beans - total_use_beans
            self.log(f"[豆子余额]: {total_beans}")
            return total_beans
        except requests.RequestException as e:
            logging.error(f"[获取豆子余额]发生网络错误: {str(e)}\n{traceback.format_exc()}")
            return 0
        except Exception as e:
            logging.error(f"[获取豆子余额]发生未知错误: {str(e)}\n{traceback.format_exc()}")
            return 0
        
    def run(self):
        """
        运行任务
        """
        try:
            self.log(f"【{self.script_name}】开始执行任务")
            
            for index, wxid in enumerate(self.check_env(), 1):
                self.log("")
                self.log(f"------ 【账号{index}】开始执行任务 ------")
                
                session = requests.Session()
                session.headers['User-Agent'] = self.user_agent
                
                code = self.wechat_code_adapter.get_code(wxid)
                if code:
                    if self.code_login(session, code):
                        # 2. 执行签到
                        if self.sign_in(session):
                            time.sleep(random.randint(3, 5))
                            # 3. 执行步数兑换（直到提示每天最多兑换xxx）
                            while self.step_exchange(session):
                                time.sleep(random.randint(3, 5))
                            # 4. 执行奖池投注
                            self.pool_bet(session)
                            time.sleep(random.randint(3, 5))
                            # 5. 执行奖池签到
                            self.pool_sign(session)
                            time.sleep(random.randint(3, 5))
                            # 6. 获取用户豆子
                            self.get_user_beans(session)
                            time.sleep(random.randint(5, 10))
                self.log(f"------ 【账号{index}】执行任务完成 ------")
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
                header = "作者：临渊\n"
                content = header + "\n" +"\n".join(self.wechat_code_adapter.log_msgs)
                notify.send(title, content)

if __name__ == "__main__":
    auto_task = AutoTask("飞蚂蚁")
    auto_task.run() 