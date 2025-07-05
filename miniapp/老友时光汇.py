"""
 作者:  临渊
 日期:  2025/7/5
 小程序:  老友时光汇 (https://a.c1ns.cn/Kuq1I) (首次进入点参与答题授权头像昵称)
 功能:  签到、问答、查询信息
 变量:  lysgh_token = 'x-token' (api.zijinzhaoyao.com域名请求中x-token值)
 定时:  一天两次
 cron:  10 11,12 * * *
 更新日志：
 2025/7/5 V1.0 初始化脚本
"""

MULTI_ACCOUNT_SPLIT = ["\n", "@"] # 分隔符列表
MULTI_ACCOUNT_PROXY = False # 是否使用多账号代理，默认不使用，True则使用多账号代理
NOTIFY = False # 是否推送日志，默认不推送，True则推送

import json
import random
import time
import requests
import os
import logging
import traceback
import ssl
from datetime import datetime

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
        self.wx_appid = "wxa973bdd2c6278631" # 微信小程序id
        # self.wx_code_url = os.getenv("soy_codeurl_data")
        # self.wx_code_token = os.getenv("soy_codetoken_data")
        self.host = "api.zijinzhaoyao.com"
        self.nickname = ""
        self.credits = 0
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
            url = f"https://{self.host}/api/user/sign"
            response = session.post(url, timeout=5)
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
            lysgh_token = os.getenv(f"lysgh_token")
            if not lysgh_token:
                self.log("[检查环境变量] 没有找到环境变量lysgh_token，请检查环境变量", level="error")
                return None

            # 自动检测分隔符
            split_char = None
            for sep in MULTI_ACCOUNT_SPLIT:
                if sep in lysgh_token:
                    split_char = sep
                    break
            if not split_char:
                # 如果都没有分隔符，默认当作单账号
                lysgh_tokens = [lysgh_token]
            else:
                lysgh_tokens = lysgh_token.split(split_char)

            for lysgh_token in lysgh_tokens:
                if "=" in lysgh_token:
                    lysgh_token = lysgh_token.split("=")[1]
                    yield lysgh_token
                else:
                    yield lysgh_token
        except Exception as e:
            self.log(f"[检查环境变量] 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            raise

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
            response_json = response.json()
            if response_json['code'] == 200:
                code = response_json['data']['code']
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
        
    def wxlogin(self, session, code):
        """
        登录
        :param session: session
        :param code: 微信code
        :return: 登录结果
        """
        try:
            url = f"https://{self.host}/api/silenceLogin"
            payload = {
                "code": code
            }
            response = session.post(url, json=payload, timeout=5)
            response_json = response.json()
            if int(response_json['code']) == 0:
                session.headers['x-token'] = response_json['data']['token']
                return True
            else:
                self.log(f"[登录] 失败，错误信息: {response_json['message']}", level="error")
                return False
        except requests.RequestException as e:
            self.log(f"[登录] 发生网络错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        except Exception as e:
            self.log(f"[登录] 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False

    def sign_in(self, session):
        """
        签到
        :param session: session
        :return: 签到结果
        """
        try:
            url = f"https://{self.host}/api/userSign"
            response = session.post(url, timeout=5)
            response_json = response.json()
            if int(response_json['code']) == 0:
                self.log(f"[{self.nickname}] 签到: 成功")
                return True
            else:
                self.log(f"[{self.nickname}] 签到: {response_json['message']}")
                return False
        except Exception as e:
            self.log(f"[{self.nickname}] 签到: 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def get_exam_list(self, session):
        """
        获取问答列表
        :param session: session
        :return: 问答列表
        """
        try:
            url = f"https://{self.host}/api/v3/activity-list/columns"
            paylaod = {
                "column": 1
            }
            response = session.post(url, json=paylaod, timeout=5)
            response_json = response.json()
            if int(response_json['code']) == 0:
                exam_list = response_json['data']
                return exam_list
            else:
                return False
        except Exception as e:
            self.log(f"[{self.nickname}] 获取问答列表: 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False

    def start_exam(self, session, exam_activity_id):
        """
        开始问答
        :param session: session
        :param exam_activity_id: 问答活动id
        :return: 开始问答结果
        """
        try:
            url = f"https://{self.host}/api/v2/startAnswer"
            payload = {
                "id": exam_activity_id
            }
            response = session.post(url, json=payload, timeout=5)
            response_json = response.json()
            if int(response_json['code']) == 0:
                exam_id = response_json['data']['examId']
                exam_answer = response_json['data']['question']['answer']
                # self.log(f"[{self.nickname}] 开始问答: 成功 id: {exam_id} 答案: {exam_answer}")
                return exam_id, exam_answer
            else:
                self.log(f"[{self.nickname}] 开始问答: {response_json['message']}", level="warning")
                return False
        except Exception as e:
            self.log(f"[{self.nickname}] 开始问答: 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def submit_answer(self, session, exam_id, exam_activity_id, exam_answer):
        """
        提交答案
        :param session: session
        :param exam_id: 问答id
        :param exam_activity_id: 问答活动id
        :param exam_answer: 问答答案
        """
        try:
            url = f"https://{self.host}/api/submitAnswer"
            payload = {
                "examId": exam_id,
                "id": exam_activity_id,
                "answer": exam_answer,
                "number": 1
            }
            response = session.post(url, json=payload, timeout=5)
            response_json = response.json()
            if int(response_json['code']) == 0 and response_json['data']['isCorrect']:
                # self.log(f"[{self.nickname}] 提交答案: 成功")
                return True
            else:
                self.log(f"[{self.nickname}] 提交答案: {response_json['message']}", level="warning")
                return False
        except Exception as e:
            self.log(f"[{self.nickname}] 提交答案: 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def submit_exam(self, session, exam_id, exam_activity_id):
        """
        提交问答
        :param session: session
        :param exam_id: 问答id
        :param exam_activity_id: 问答活动id
        :return: 提交问答结果
        """
        try:
            url = f"https://{self.host}/api/v2/submitExam"
            payload = {
                "id": exam_activity_id,
                "examId": exam_id
            }
            response = session.post(url, json=payload, timeout=5)
            response_json = response.json()
            if int(response_json['code']) == 0:
                self.log(f"[{self.nickname}] 提交问答: 成功 获得: {response_json['data']['credits']}学分 现金: {response_json['data']['money']}元")
                return True
            else:
                self.log(f"[{self.nickname}] 提交问答: {response_json['message']}", level="warning")
                return False
        except Exception as e:
            self.log(f"[{self.nickname}] 提交问答: 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def get_user_info(self, session, log=False):
        """
        获取用户信息
        :param session: session
        :return: 用户信息
        """
        try:
            url = f"https://{self.host}/api/getUserInfo"
            response = session.get(url, timeout=5)
            response_json = response.json()
            if int(response_json['code']) == 0:
                self.credits = response_json['data']['userInfo']['credits']
                self.nickname = response_json['data']['userInfo']['nickname']
                if log:
                    self.log(f"[{self.nickname}] 总学分: {self.credits} 现金收益: {response_json['data']['userInfo']['totalMoney']}元")
                return True
            else:
                self.log(f"[查询用户信息] 发生错误: {response_json['message']}", level="error")
                return False
        except Exception as e:
            self.log(f"[查询用户信息] 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def exchange(self, session, credits):
        """
        学分兑换现金
        :param session: session
        :param credits: 学分
        """
        try:
            url = f"https://{self.host}/api/v3/credits-exchange"
            payload = {
                "amount": credits
            }
            response = session.post(url, json=payload, timeout=5)
            response_json = response.json()
            if int(response_json['code']) == 0:
                self.log(f"[{self.nickname}] 兑换成功 获得: {response_json['data']}")
                return True
            else:
                self.log(f"[{self.nickname}] 兑换: {response_json['message']}", level="warning")
                return False
        except Exception as e:
            self.log(f"[{self.nickname}] 兑换失败 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
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
                    
                headers = {
                    "User-Agent": self.user_agent,
                    "Project-Name": "yl",
                    "Content-Type": "application/json;charset=UTF-8",
                    "x-token": token
                }
                session.headers.update(headers)

                # # 执行微信授权
                # code = self.wx_code_auth(wx_id)
                # if code:
                #     if self.wxlogin(session, code):
                # 查询用户信息
                if self.get_user_info(session):
                    # 签到
                    self.sign_in(session)
                    time.sleep(random.randint(3, 5))
                    # 获取问答列表
                    exam_list = self.get_exam_list(session)
                    if exam_list:
                        for exam in exam_list:
                            left_count = int(exam['times']) - int(exam['count'])
                            for _ in range(left_count):
                                # 开始问答
                                exam_id, exam_answer = self.start_exam(session, exam['id'])
                                time.sleep(random.randint(3, 5))
                                # 提交答案
                                self.submit_answer(session, exam_id, exam['id'], exam_answer)
                                time.sleep(random.randint(30, 40))
                                # 提交问答
                                self.submit_exam(session, exam_id, exam['id'])
                                time.sleep(random.randint(3, 5))
                    # 查询用户信息
                    self.get_user_info(session, log=True)
                    if self.credits >= 50:
                        self.exchange(session, self.credits)

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
    auto_task = AutoTask("老友时光汇")
    auto_task.run() 