"""
 作者:  临渊
 日期:  2025/6/22
 小程序:  飞蚂蚁 (https://a.c1ns.cn/iJAKu)
 功能:  签到、步数兑换、奖池投注、获取用户豆子
 变量:  fmy='authorization' （openapp.fmy90.com域名下请求中authorization） 多个账号用换行分割 
 定时:  一天三次
 cron:  10 6-8 * * *
 更新日志：
 2025/6/22  V1.0 初始化脚本
 2025/7/8   V1.1 token过期退出执行 增加变量推送日志
"""

import random
import time
import requests
import os
import logging
import traceback
from datetime import datetime

NOTIFY = os.getenv("LY_NOTIFY") or False # 是否推送日志，默认不推送，True则推送

class AutoTask:
    def __init__(self, script_name):
        """
        初始化自动任务类
        :param script_name: 站点名称，用于日志显示
        """
        self.script_name = script_name
        self.log_msgs = []  # 日志收集
        self.host = "openapp.fmy90.com"
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

    def check_env(self):
        """
        检查环境变量
        :return: 环境变量字符串
        """
        try:
            # 从环境变量获取cookie
            cookie = os.getenv(f"fmy")
            if not cookie:
                logging.error(f"[检查环境变量]没有找到环境变量fmy，请检查环境变量")
                return None
            # 多个账号用换行分割
            cookies = cookie.split('\n')
            for cookie in cookies:
                if "=" in cookie:
                    cookie = cookie.split("=")[1]
                    yield cookie
                else:
                    yield cookie
        except Exception as e:
            logging.error(f"[检查环境变量]发生错误: {str(e)}\n{traceback.format_exc()}")
            raise

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
        执行池子投注
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
            self.log(f"[池子投注]: {response_json['message']}")
            return True
        except requests.RequestException as e:
            logging.error(f"[池子投注]发生网络错误: {str(e)}\n{traceback.format_exc()}")
            return False
        except Exception as e:
            logging.error(f"[池子投注]发生未知错误: {str(e)}\n{traceback.format_exc()}")
            return False


    def pool_sign(self, session):
        """
        执行池子签到
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
            self.log(f"[池子签到]: {response_json['message']}")
            return True
        except requests.RequestException as e:
            logging.error(f"[池子签到]发生网络错误: {str(e)}\n{traceback.format_exc()}")
            return False
        except Exception as e:
            logging.error(f"[池子签到]发生未知错误: {str(e)}\n{traceback.format_exc()}")
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
            
            # 1. 检查cookie
            for index, cookie in enumerate(self.check_env(), 1):
                self.log("")
                self.log(f"------ 【账号{index}】开始执行任务 ------")
                
                session = requests.Session()
                session.headers['authorization'] = cookie
                session.headers['User-Agent'] = self.user_agent

                # 2. 执行签到
                if self.sign_in(session):
                    time.sleep(random.randint(3, 5))
                    # 3. 执行步数兑换（直到提示每天最多兑换xxx）
                    while self.step_exchange(session):
                        time.sleep(random.randint(3, 5))
                    # 4. 执行池子投注
                    self.pool_bet(session)
                    time.sleep(random.randint(3, 5))
                    # 5. 执行池子签到
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
                content = header + "\n" +"\n".join(self.log_msgs)
                notify.send(title, content)

if __name__ == "__main__":
    auto_task = AutoTask("飞蚂蚁")
    auto_task.run() 