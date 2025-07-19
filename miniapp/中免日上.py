"""
 作者:  临渊
 日期:  2025/7/2
 小程序:  中免日上 (https://a.c1ns.cn/qbFEB)
 功能:  签到、查积分、小游戏
 变量:  zmrs_token = 'Accesstoken' (https://api.cdfsunrise.com/restfulapi/Account/getAccountInfo 请求中的Accesstoken)
 定时:  一天两次
 cron:  10 8,9 * * *
 更新日志：
 2025/7/2   V1.0    初始化脚本
 2025/7/3   V1.1    增加小游戏签到、浏览、抽奖、做包子
 2025/7/7   V1.2    通知可以设置环境变量LY_NOTIFY
 2025/7/8   V1.3    尝试修复火爆问题
 2025/7/19  V1.4    去除抽奖、增加一个浏览
"""

import json
import random
import re
import time
import requests
import os
import string
import logging
import traceback
import ssl
from datetime import datetime

MULTI_ACCOUNT_SPLIT = ["\n", "@"] # 分隔符列表
MULTI_ACCOUNT_PROXY = True # 是否使用多账号代理，默认不使用，True则使用多账号代理
NOTIFY = os.getenv("LY_NOTIFY") or False # 是否推送日志，默认不推送，True则推送
# 504 来财包 505 福禄包 506 转运包 507 美力包 508 普通包 509 锦鲤包
BAOZI_INFO = {
    "509": ["xl_jlh", "xl_fhy", "xl_hongyunjiang"],
    "504": ["xl_yzm", "xl_xhj", "xl_huayunjiao"],
    "505": ["xl_fqr", "xl_rfy", "xl_wfx"],
    "506": ["xl_bhd", "xl_xyt", "xl_byj"],
    "507": ["xl_jyg", "xl_ltx", "xl_zlc"]
}

class TLSAdapter(requests.adapters.HTTPAdapter):
    """
    自定义TLS
    解决unsafe legacy renegotiation disabled
    貌似python太高版本依然会报错
    """
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        ctx.options |= 0x4   # <-- the key part here, OP_LEGACY_SERVER_CONNECT
        kwargs["ssl_context"] = ctx
        return super(TLSAdapter, self).init_poolmanager(*args, **kwargs)

class AutoTask:
    def __init__(self, script_name):
        """
        初始化自动任务类
        :param script_name: 脚本名称，用于日志显示
        """
        self.script_name = script_name
        self.log_msgs = []  # 日志收集
        self.proxy_url = os.getenv("PROXY_API_URL") # 代理api，返回一条txt文本，内容为代理ip:端口
        self.wx_appid = "wx82028cdb701506f3" # 微信小程序id
        # self.wx_code_url = os.getenv("soy_codeurl_data")
        # self.wx_code_token = os.getenv("soy_codetoken_data")
        self.host = "api.cdfsunrise.com"
        self.nickname = ""
        self.token = ""
        self.user_id = ""
        self.mobile = ""
        self.device_id = self.get_random_device_id()
        self.lottery_count = 0
        self.activity_key = ""
        self.activity_type = ""
        self.game_user_fragment_count = 0
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
    
    def get_random_device_id(self):
        """
        获取随机设备id
        :return: 设备id
        """
        base_id = "BOfYnPsxs/of426K5rN9PfcWW4XoIzJvrguoNGX3viThgcV/6MXraPhzImAwmpH2J5pidmvpqiJNVqdY+OL1Q8w=="
        # 只替换字母和数字，保留其它符号
        chars = string.ascii_letters + string.digits
        new_id = ""
        for c in base_id:
            if c.isalnum():
                new_id += random.choice(chars)
            else:
                new_id += c
        return new_id

    def get_proxy(self):
        """
        获取代理
        :return: 代理
        """
        if not self.proxy_url:
            self.log("[获取代理] 没有找到环境变量PROXY_API_URL，不使用代理", level="warning")
            return None
        url = self.proxy_url
        response = requests.get(url)
        proxy = response.text
        self.log(f"[获取代理] {proxy}")
        return proxy
    
    def check_proxy(self, proxy, session):
        """
        检查代理
        :param proxy: 代理
        :param session: session
        :return: 是否可用
        """
        try:
            url = f"https://{self.host}/restapi/market/banner"
            payload = {"pageName":"mine","pageMineAB":"C"}
            response = session.post(url, json=payload, timeout=5)
            if response.status_code == 200:
                self.log(f"[检查代理] {proxy} 应该可用")
                return True
            else:
                self.log(f"[检查代理] {response.text}")
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
            zmrs_token = os.getenv(f"zmrs_token")
            if not zmrs_token:
                self.log("[检查环境变量] 没有找到环境变量zmrs_token，请检查环境变量", level="error")
                return None

            # 自动检测分隔符
            split_char = None
            for sep in MULTI_ACCOUNT_SPLIT:
                if sep in zmrs_token:
                    split_char = sep
                    break
            if not split_char:
                # 如果都没有分隔符，默认当作单账号
                zmrs_tokens = [zmrs_token]
            else:
                zmrs_tokens = zmrs_token.split(split_char)

            for zmrs_token in zmrs_tokens:
                yield zmrs_token
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
        
    def device_login(self, session):
        """
        设备登录
        :param session: session
        :return: 登录结果
        """
        try:
            url = f"https://{self.host}/restapi/user/deviceLogin"
            payload = {
                "sign": "md5sign",
                "timeStamp": "1751439544177",
                "userAgent": {
                    "sign": "badfd729098449d8fa9ce8b0e0202186",
                    "serialNo": "o_e3j4oIH7UGySia9B_yxAHnAXfs",
                    "system": "Windows 11 x64",
                    "appName": "lefox-official-miniprogram",
                    "version": "1.61.0",
                    "type": "taro_weapp",
                    "model": "microsoftmicrosoft",
                    "serverId": "DCB544E2087CEE28-A0B923820DCC509A-479375484",
                    "data": {
                        "newBind": "true"
                    },
                    "thirdPartyAppID": "wx82028cdb701506f3"
                },
                "jsCode": "0f1XAY1w3bqRb53qm31w3tSn3E3XAY18"
            }
            response = session.post(url, json=payload, timeout=5)
            response_json = response.json()
            token = response_json.get('data', {}).get('accessToken', '')
            if token:
                session.headers['Accesstoken'] = token
                return True
            else:
                self.log(f"[设备登录] 失败，错误信息: {response_json['message']}", level="error")
                return False
        except Exception as e:
            self.log(f"[设备登录] 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def wxlogin(self, session, code):
        """
        登录
        :param session: session
        :param code: 微信code
        :return: 登录结果
        """
        try:
            url = f"https://{self.host}/restapi/user/wxMiniLogin"
            payload = {
                "userAgent": {
                    "sign": "badfd729098449d8fa9ce8b0e0202186",
                    "serialNo": "o_e3j4oIH7UGySia9B_yxAHnAXfs",
                    "system": "Windows 11 x64",
                    "appName": "lefox-official-miniprogram",
                    "version": "1.61.0",
                    "type": "taro_weapp",
                    "model": "microsoftmicrosoft",
                    "serverId": "DCB544E2087CEE28-A0B923820DCC509A-479375484",
                    "data": {
                        "newBind": "true"
                    },
                    "thirdPartyAppID": "wx82028cdb701506f3"
                },
                "encrypted": "",
                "iv": "",
                "jsCode": code,
                "deviceId": self.device_id,
                "rid": "",
                "quickLoginOptionToken": "3784e624846b04e5e2f0344251180ea7:f9b1dc74-6fbb-4599-b1e8-614d503db61b"
            }
            self.log(f"[登录] {session.headers}")
            response = session.post(url, data=payload, timeout=5)
            response_json = response.json()
            self.log(f"[登录] {response_json}")
            if response_json['success']:
                self.token = response_json['data']['tokenInfo']['accessToken']
                session.headers['accesstoken'] = self.token
                return True
            else:
                self.log(f"[登录] 失败，错误信息: {response_json['msg']}", level="error")
                return False
        except requests.RequestException as e:
            self.log(f"[登录] 发生网络错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        except Exception as e:
            self.log(f"[登录] 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False

    def get_user_info(self, session):
        """
        获取用户信息
        :param session: session
        :return: 用户信息
        """
        try:
            url = f"https://{self.host}/restfulapi/Account/getAccountInfo"
            payload = {
                "beautyMember": "false"
            }
            response = session.post(url, json=payload, timeout=5)
            try:
                response_json = response.json()
            except json.JSONDecodeError:
                # 不是json，判断为token失效
                self.log(f"[获取用户信息] {response.text}", level="error")
                return False
            if response_json['success']:
                self.user_id = response_json['data']['userId']
                self.nickname = response_json['data']['userName']
                self.mobile = response_json['data']['mobile']
                session.headers['mobile'] = self.mobile
                # 如果昵称为手机号，隐藏中间四位
                if re.match(r"^1[3-9]\d{9}$", self.nickname):
                    self.nickname = self.nickname[:3] + "****" + self.nickname[-4:]
                self.log(f"[{self.nickname}] 获取用户信息成功")
                return True
            else:
                self.log(f"[获取用户信息] {response_json['message']}", level="warning")
                return False
        except Exception as e:
            self.log(f"[获取用户信息] 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def signin(self, session):
        """
        签到
        :param session: session
        :return: 签到结果
        """
        try:
            url = f"https://{self.host}/restapi/activity/activityAction"
            payload = {
                "activityKey": "2025fivechoujiangchild",
                "eventType": "registration",
                "deviceId": self.device_id
            }
            response = session.post(url, json=payload, timeout=5)
            response_json = response.json()
            response_message = response_json.get('message', '')
            if response_message:
                self.log(f"[{self.nickname}] 签到: {response_message}")
                return True
            else:
                self.log(f"[{self.nickname}] 签到失败，错误信息: {response_json['msg']}", level="error")
                return False
        except Exception as e:
            self.log(f"[签到] 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def mini_game_signin(self, session):
        """
        小游戏签到
        :param session: session
        :return: 签到结果
        """
        try:
            url = f"https://{self.host}/restapi/activity/upload"
            payload = {
                "activityKey": "20f8bab0d4000",
                "eventType": "cycle_sign_in",
                "eventData": "{,\"sign\":\"7f6cca6e4c0a48ec9a043f01cfa23d4f\"}",
                "sourceId": "",
                "userId": self.user_id,
                "deviceId": self.device_id,
                "rid": ""
            }
            response = session.post(url, json=payload, timeout=5)
            response_json = response.json()
            if response_json['success']:
                self.log(f"[{self.nickname}] 小游戏签到: {response_json['msg']}")
            else:
                if "系统繁忙" in response_json['msg']:
                    self.log(f"[{self.nickname}] 小游戏签到: 今日已签到")
                    return True
                else:
                    self.log(f"[{self.nickname}] 小游戏签到失败，错误信息: {response_json['msg']}", level="error")
                    return False
        except Exception as e:
            self.log(f"[小游戏签到] 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False

        
    def mini_game_brose(self, session, activity_key):
        """
        小游戏浏览
        :param session: session
        :param activity_key: 活动key 115c73bf71000 1153198a86000 20ad059a31000
        :return: 浏览结果
        """
        try:
            url = f"https://{self.host}/restapi/activity/activityAction"
            payload = {
                "activityKey": activity_key,
                "eventType": "page_browsing",
                "deviceId": self.device_id
            }
            response = session.post(url, json=payload, timeout=5)
            response_json = response.json()
            response_message = response_json.get('message', '')
            if response_message:
                self.log(f"[{self.nickname}] 小游戏浏览: {response_message}")
                return True
            else:
                self.log(f"[{self.nickname}] 小游戏浏览失败，错误信息: {response_json['msg']}", level="error")
                return False
        except Exception as e:
            self.log(f"[小游戏浏览] 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
    
    def get_mini_game_lottery_info(self, session):
        """
        获取小游戏抽奖信息
        :param session: session
        :return: 抽奖信息
        """
        try:
            url = f"https://{self.host}/restapi/activity/userInfo"
            payload = {
                "activityKey": "f791d7686000",
                "dateTime": datetime.now().strftime("%Y-%m-%d"),
                "activityType": 48,
                "deviceId": self.device_id,
                "rid": ""
            }
            session.headers['UserSystem'] = "h5platform"
            response = session.post(url, json=payload, timeout=5)
            response_json = response.json()
            if response_json['success']:
                self.log(f"[{self.nickname}] 小游戏抽奖次数: {response_json['data']['bzInfo']['tags']['fragment']}")
                return int(response_json['data']['bzInfo']['tags']['fragment'])
            else:
                self.log(f"[{self.nickname}] 小游戏抽奖信息失败，错误信息: {response_json['msg']}", level="error")
                return 0
        except Exception as e:
            self.log(f"[获取小游戏抽奖信息] 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return 0
        
    def get_mini_game_profit_list(self, session):
        """
        获取小游戏材料
        :param session: session
        :return: 
        """
        try:
            url = f"https://{self.host}/restapi/activity/profit/list"
            payload = {
                "activityKey": "f791d7686000",
                "profitTypes": [
                    "xl_fhy",
                    "xl_rfy",
                    "xl_xyt",
                    "xl_ltx",
                    "xl_xhj",
                    "xl_jlh",
                    "xl_yzm",
                    "xl_fqr",
                    "xl_bhd",
                    "xl_jyg",
                    "xl_hongyunjiang",
                    "xl_huayunjiao",
                    "xl_wfx",
                    "xl_byj",
                    "xl_zlc"
                ]
            }
            response = session.post(url, json=payload, timeout=5)
            response_json = response.json()
            if response_json['success']:
                profit_list = response_json['data']['list']
                return profit_list
            else:
                self.log(f"[{self.nickname}] 小游戏材料失败，错误信息: {response_json['msg']}", level="error")
                return False
        except Exception as e:
            self.log(f"[获取小游戏材料] 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def do_mini_game_baozi(self, session, activity_key, extension):
        """
        小游戏做包子
        :param session: session
        :param activity_key: 活动key
        :param extension: 扩展参数
        :return: 操作结果
        """
        try:
            url = f"https://{self.host}/restapi/activity/bottle/action"
            payload = {
                "activityKey": activity_key,
                "eventType": "benefit_exchange_bz",
                "sourceId": "",
                "deviceId": self.device_id,
                "rid": "",
                "extension": extension
            }
            response = session.post(url, json=payload, timeout=5)
            response_json = response.json()
            if response_json['success']:
                return True
            else:
                self.log(f"[{self.nickname}] 做包子失败，错误信息: {response_json['msg']}", level="error")
                return False
        except Exception as e:
            self.log(f"[小游戏操作] 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def get_mini_game_baozi_count(self, session):
        """
        获取小游戏包子数
        :param session: session
        :return: 包子数
        """
        try:
            url = f"https://{self.host}/restapi/activity/profit/info"
            payload = {
                "activityKey": "c4979573d000",
                "profitType": "SmallBun"
            }
            response = session.post(url, json=payload, timeout=5)
            response_json = response.json()
            if response_json['success']:
                self.log(f"[{self.nickname}] 小游戏包子数: {response_json['data']['profitNum']}")
                return response_json['data']['profitNum']
            else:
                self.log(f"[{self.nickname}] 获取小游戏包子数失败，错误信息: {response_json['msg']}", level="warning")
                return 0
        except Exception as e:
            self.log(f"[获取小游戏包子数] 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return 0
        
    def get_lottery_info(self, session, id):
        """
        :param session: session
        :param id: 抽奖id
        463 每日签到抽奖
        411 包子皮数量 gameUserFragmentCount
        510 小游戏转盘
        504 来财包
        505 福禄包
        506 转运包
        507 美力包
        508 普通包
        509 锦鲤包
        :return: 抽奖信息
        """
        try:
            url = f"https://{self.host}/restapi/activity/lottery/v2"
            payload = {
                "id": id
            }
            response = session.post(url, json=payload, timeout=5)
            response_json = response.json()
            response_result = response_json.get('responseHead', {}).get('isSuccess', '')
            if response_result:
                self.lottery_count = response_json['data']['userFragmentCount']
                self.game_user_fragment_count = response_json['data']['gameUserFragmentCount']
                self.activity_key = response_json['data']['activityKey']
                self.activity_type = response_json['data']['activityType']
                return True
            else:
                self.log(f"[{self.nickname}] 抽奖失败，错误信息: {response_json['msg']}", level="error")
                return False
        except Exception as e:
            self.log(f"[获取抽奖信息] 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def lottery(self, session, activity_key, activity_type):
        """
        抽奖
        :param session: session
        :param activity_key: 活动key
        :param activity_type: 活动类型
        :return: 抽奖结果
        """
        try:
            url = f"https://{self.host}/restapi/activity/pickLuckyDraw"
            payload = {
                "activityKey": activity_key,
                "activityType": activity_type,
                "deviceId": self.device_id,
                "userId": self.user_id,
                "memberCode": ""
            }
            response = session.post(url, json=payload, timeout=5)
            response_json = response.json()
            if response_json['success']:
                if response_json['data']['prizeList']:
                    prizes = ""
                    for prize in response_json['data']['prizeList']:
                        prizes += f"{prize['prizeDesc']} "
                    self.log(f"[{self.nickname}] 抽奖获得: {prizes}")
                else:
                    self.log(f"[{self.nickname}] 抽奖获得: {response_json['data']['prizeValue']} {response_json['data']['prizeName']}")
                return True
            else:
                self.log(f"[{self.nickname}] 抽奖失败，错误信息: {response_json['msg']}", level="error")
                return False
        except Exception as e:
            self.log(f"[抽奖] 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def get_user_welfare(self, session):
        """
        获取用户福利点
        :param session: session
        :return: 福利信息
        """
        try:
            url = f"https://{self.host}/restapi/card/getUserWelfare"
            payload = {}
            response = session.post(url, json=payload, timeout=5)
            response_json = response.json()
            response_result = response_json.get('responseHead', {}).get('isSuccess', '')
            if response_result:
                self.log(f"[{self.nickname}] 福利金: {response_json['welfareList'][0]['totalAvailable']} 福利点: {response_json['welfareList'][1]['totalAvailable']}")
                return True
            else:
                self.log(f"[获取用户福利点] {response_json['responseHead']['resultMessage']}", level="warning")
                return False
        except Exception as e:
            self.log(f"[获取用户福利点] 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def run(self):
        """
        运行任务
        """
        try:
            self.log(f"【{self.script_name}】开始执行任务")
            # 检查环境变量
            for index, token in enumerate(self.check_env(), 1):
                self.log("")
                self.log(f"------ 【账号{index}】开始执行任务 ------")
                
                session = requests.Session()
                headers = {
                    "UserSystem": "H5",
                    "User-Agent": self.user_agent,
                    "accesstoken": token,
                    "Content-Type": "application/json;charset=UTF-8"
                }
                session.headers.update(headers)

                if MULTI_ACCOUNT_PROXY and self.proxy_url != "":
                    proxy = self.get_proxy()
                    if proxy:
                        session.proxies.update({"http": f"http://{proxy}", "https": f"http://{proxy}"})
                        # 检查代理，不可用重新获取
                        while not self.check_proxy(proxy, session):
                            proxy = self.get_proxy()
                            session.proxies.update({"http": f"http://{proxy}", "https": f"http://{proxy}"})

                # # 执行微信授权
                # code = self.wx_code_auth(wx_id)
                # if code:
                #     if self.device_login(session):
                #         if self.wxlogin(session, code):
                #             self.get_user_info(session)

                # 获取用户信息
                if self.get_user_info(session):
                    # 签到
                    self.signin(session)
                    time.sleep(random.randint(3, 6))
                    # 获取抽奖信息
                    if self.get_lottery_info(session, "463"):
                        time.sleep(random.randint(3, 6))
                        # # 抽奖
                        # for i in range(self.lottery_count):
                        #     self.lottery(session, self.activity_key, self.activity_type)
                        #     time.sleep(random.randint(3, 6))
                    # 获取用户福利点
                    self.get_user_welfare(session)
                    time.sleep(random.randint(3, 6))
                    # 小游戏
                    self.log(f"========== 小游戏 ==========")
                    # 小游戏签到
                    self.mini_game_signin(session)
                    time.sleep(random.randint(3, 6))
                    # 小游戏浏览
                    self.mini_game_brose(session, "115c73bf71000")
                    time.sleep(random.randint(3, 6))
                    self.mini_game_brose(session, "1153198a86000")
                    time.sleep(random.randint(3, 6))
                    self.mini_game_brose(session, "20ad059a31000")
                    time.sleep(random.randint(3, 6))
                    # 获取小游戏飞行棋信息
                    if self.get_lottery_info(session, "510"):
                        time.sleep(random.randint(3, 6))
                        # 小游戏飞行棋抽奖
                        # for i in range(self.get_mini_game_lottery_info(session)):
                        #     self.lottery(session, self.activity_key, self.activity_type)
                        #     time.sleep(random.randint(3, 6))
                    # 获取小游戏包子皮数量
                    if self.get_lottery_info(session, "411"):
                        time.sleep(random.randint(3, 6))
                        if self.game_user_fragment_count > 0:
                            profit_list = self.get_mini_game_profit_list(session)
                            # 检测材料是否能做任意一种包子
                            material_count = {profit['rightsType']: profit['rightsNum'] for profit in profit_list}
                            for baozi_id, need_materials in BAOZI_INFO.items():
                                if all(material_count.get(mat, 0) > 0 for mat in need_materials):
                                    extension = {
                                        mat: "1" for mat in need_materials
                                    }
                                    if self.do_mini_game_baozi(session, "f791d7686000", extension): 
                                        time.sleep(random.randint(3, 6))
                                        # 查询该包子的信息
                                        if self.get_lottery_info(session, baozi_id):
                                            time.sleep(random.randint(3, 6))
                                            # # 抽奖
                                            # for i in range(self.game_user_fragment_count):
                                            #     self.lottery(session, self.activity_key, self.activity_type)
                                            #     time.sleep(random.randint(3, 6))
                        else:
                            self.log(f"[{self.nickname}] 小游戏包子皮数量不足，不检测是否能做任意包子")
                    # 查询小游戏包子数
                    self.get_mini_game_baozi_count(session)
                    self.log(f"========== 小游戏 ==========")
                self.log(f"------ 【账号{index}】执行任务完成 ------")
        except Exception as e:
            self.log(f"【{self.script_name}】执行过程中发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
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
                content = header + "\n" +"\n".join(self.log_msgs)
                notify.send(title, content)


if __name__ == "__main__":
    auto_task = AutoTask("中免日上")
    auto_task.run() 