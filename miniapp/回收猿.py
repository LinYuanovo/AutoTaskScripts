"""
 作者： 临渊
 日期： 2025/6/24
 小程序：   回收猿
 功能： 签到、抽奖、满余额提现
 变量： hsy_username （www.52bjy.com请求url参数中的username） 多个账号用换行分割 
 定时： 一天一次
 cron： 10 8 * * *
 更新日志：
 2025/6/24  初始化脚本
 2025/6/26  修复重复提现
"""

DEFAULT_WITHDRAW_BALANCE = 1 # 默认超过该金额进行提现，需大于等于1

import hashlib
import random
import time
import requests
import os
import logging
import traceback
from datetime import datetime

class AutoTask:
    def __init__(self, site_name):
        """
        初始化自动任务类
        :param site_name: 站点名称，用于日志显示
        """
        self.site_name = site_name
        # self.wx_code_url = os.getenv("soy_codeurl_data")
        # self.wx_code_token = os.getenv("soy_codetoken_data")
        self.host = "www.52bjy.com"
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090b13) XWEB/9129"
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

    def check_env(self):
        """
        检查环境变量
        :return: 环境变量字符串
        """
        try:
            # 从环境变量获取cookie
            username = os.getenv(f"hsy_username")
            if not username:
                logging.error(f"[检查环境变量]没有找到环境变量hsy_username，请检查环境变量")
                return None
            # 多个账号用换行分割
            usernames = username.split('\n')
            for username in usernames:
                if "=" in username:
                    username = username.split("=")[1]
                    yield username
                else:
                    yield username
        except Exception as e:
            logging.error(f"[检查环境变量]发生错误: {str(e)}\n{traceback.format_exc()}")
            raise

    def wx_code_auth(self, session, wx_id):
        """
        执行微信授权
        :param session: session
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
                "appid": "wxadd84841bd31a665"
            }
            response = session.post(url, headers=headers, json=payload)
            response.raise_for_status()
            response_json = response.json()
            if response_json['code'] == 200:
                code = response_json['data']['code']
                return code
            else:
                logging.error(f"[微信授权]{response_json['msg']}")
                return False
        except requests.RequestException as e:
            logging.error(f"[微信授权]发生网络错误: {str(e)}\n{traceback.format_exc()}")
            return False
        except Exception as e:
            logging.error(f"[微信授权]发生未知错误: {str(e)}\n{traceback.format_exc()}")
            return False

    def get_sign(self, params):
        """
        获取签名
        :param params: 参数
        :return: 签名
        """
        params_str = "&".join([f"{k}={v}" for k, v in params.items()]) + "UppwYkfBlk"
        encrypted_str = hashlib.md5(params_str.encode()).hexdigest()
        return encrypted_str
        
    def login(self, session, code):
        """
        登录
        :param session: session
        :param code: 微信code
        :return: 登录结果
        """
        try:
            url = f"https://{self.host}/api/app/hsy.php"
            params = {
                "action": "auth",
                "appkey": "1079fb245839e765",
                "code": code,
                "inviter": "",
                "iv": "c+AcluyHusGM9EmVkh2axA==",
                "merchant_id": "2",
                "method": "weixin_bind",
                "version": "2"
            }
            params["sign"] = self.get_sign(params)
            payload = f"encryptedData=M/Lv191+L7VI5ye0p/EFKzZuP4Wy02eMQwxhHmooRivjYsf6h+XjgGmAI8JXnTpTMCD+6o7+0k6HfEzs8Ww5nCM6M7HrHXtLWvaXkVbT2cF+ufak87NNT+5Txt2CGRfFCdAGSHmB1lFuxfbmQR8SFSZGdh7tn20Ehd3mKe6HHUI+ZxoG/L6OOUDX1yTQQ3nsxQyuWbLOldgQ7VfKfA/9WmIS6lt3j8sIOn83CiiiiJNPc1spMEfWZX3vD839FiuKwgh+a5/JTeBgfEhcchV7y0YQXQlxD2BLQ7whF/A/KrKB9bsIrdefmqynicZuRKa6WTNnQlikoT9oq0cYzF+w4lyesPK4ig/uKuSxf4P8SRpZ1U3cdKuwTs1eufsIm2nuUAUgYj0SfbM02QD65ESZWGLI6zHiVXadGhFF2KDPeehwnSaK6h2++6WhyI8Hj1+E"
            session.headers["Content-Type"] = "application/x-www-form-urlencoded"
            response = session.post(url, params=params, data=payload)
            response.raise_for_status()
            response_json = response.json()
            logging.info(f"[登录]: {response_json}")
        except requests.RequestException as e:
            logging.error(f"[登录]发生网络错误: {str(e)}\n{traceback.format_exc()}")
            return False
        except Exception as e:
            logging.error(f"[登录]发生错误: {str(e)}\n{traceback.format_exc()}")
            return False
        

    def sign_in(self, session, username):
        """
        签到
        :param session: session
        :return: 签到结果
        """
        try:
            url = f"https://{self.host}/api/app/hsy.php"
            params = {
                "action": "user",
                "app": "hsywx",
                "appkey": "1079fb245839e765",
                "merchant_id": "2",
                "method": "qiandao",
                "username": username,
                "version": "4"
            }
            params["sign"] = self.get_sign(params)
            response = session.get(url, params=params)
            response.raise_for_status()
            response_json = response.json()
            logging.info(f"[签到]: {response_json['message']}")
        except Exception as e:
            logging.error(f"[签到]发生错误: {str(e)}\n{traceback.format_exc()}")
            return False
        
    def prize_draw(self, session, username):
        """
        抽奖
        :param session: session
        :param username: 用户名
        :return: 抽奖结果
        """
        try:
            url = f"https://{self.host}/api/app/promotionjgg.php"
            params = {
                "action": "prize_draw",
                "app": "hsywx",
                "appkey": "1079fb245839e765",
                "merchant_id": "2",
                "username": username,
                "version": "4"
            }
            params["sign"] = self.get_sign(params)
            response = session.get(url, params=params)
            response.raise_for_status()
            response_json = response.json()
            if response_json['code'] == 200:
                # 奖励金
                introduce = response_json['data']['introduce']
                title = response_json['data']['title']
                logging.info(f"[抽奖]: {introduce} {title}")
            else:
                logging.warning(f"[抽奖]: {response_json['message']}")
        except Exception as e:
            logging.error(f"[抽奖]发生错误: {str(e)}\n{traceback.format_exc()}")
            return False
        
    def get_user_balance(self, session, username):
        """
        获取用户余额
        :param session: session
        :param username: 用户名
        :return: 用户余额
        """
        try:
            url = f"https://{self.host}/api/app/hsy.php"
            params = {
                "action": "user",
                "appkey": "1079fb245839e765",
                "merchant_id": "2",
                "method": "center",
                "username": username,
                "version": "2"
            }
            params["sign"] = self.get_sign(params)
            response = session.get(url, params=params)
            response.raise_for_status()
            response_json = response.json()
            if response_json['code'] == 200:
                balance = response_json['data']['award_balance']
                logging.info(f"[余额]: {balance}元")
                return balance
            else:
                logging.warning(f"[获取用户余额]: {response_json['message']}")
                return 0
        except Exception as e:
            logging.error(f"[获取用户余额]发生错误: {str(e)}\n{traceback.format_exc()}")
            return 0
        
    def withdraw(self, session, username, balance):
        """
        提现
        :param session: session
        :param username: 用户名
        :param balance: 余额
        :return: 提现结果
        """
        try:
            url = f"https://{self.host}/api/app/envcash.php"
            params = {
                "action": "add",
                "amount": balance,
                "app": "wx",
                "appkey": "1079fb245839e765",
                "merchant_id": "2",
                "type": "award",
                "username": username,
                "version": "2"
            }
            params["sign"] = self.get_sign(params)
            response = session.get(url, params=params)
            response.raise_for_status()
            response_json = response.json()
            logging.info(f"[提现]: {response_json['message']}")
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
            for index, username in enumerate(self.check_env(), 1):
                logging.info("")
                logging.info(f"------ 【账号{index}】开始执行任务 ------")
                
                session = requests.Session()

                # # 执行微信授权
                # code = self.wx_code_auth(session, wx_id)
                # if code:
                #     self.login(session, code)
                
                # 签到
                self.sign_in(session, username)
                time.sleep(random.randint(3, 5))
                # 抽奖
                self.prize_draw(session, username)
                time.sleep(random.randint(3, 5))
                # 获取用户余额
                balance = float(self.get_user_balance(session, username))
                time.sleep(random.randint(3, 5))
                # 提现
                if balance >= DEFAULT_WITHDRAW_BALANCE:
                    logging.info(f"[提现]: 余额大于{DEFAULT_WITHDRAW_BALANCE}，开始尝试提现")
                    self.withdraw(session, username, balance)
                    time.sleep(random.randint(3, 5))
                logging.info(f"------ 【账号{index}】执行任务完成 ------")
        except Exception as e:
            logging.error(f"【{self.site_name}】执行过程中发生错误: {str(e)}\n{traceback.format_exc()}")


if __name__ == "__main__":
    auto_task = AutoTask("回收猿")
    auto_task.run() 