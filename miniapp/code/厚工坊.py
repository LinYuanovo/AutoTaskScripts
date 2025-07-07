"""
 作者： 临渊
 日期： 2025/6/25
 小程序：   厚工坊
 功能： 签到、浏览、分享
 变量：soy_wxid_data (微信id) 多个账号用换行分割 
      soy_codetoken_data (微信授权token)
      soy_codeurl_data (微信授权url)
      PROXY_API_URL (代理api，返回一条txt文本，内容为代理ip:端口)
 定时： 一天两次
 cron： 10 8,9 * * *
 更新日志：
 2025/6/25 V1.0 初始化脚本
 2025/7/7  V1.1 适配更多协议
"""

MULTI_ACCOUNT_SPLIT = ["\n", "@"] # 分隔符列表
MULTI_ACCOUNT_PROXY = False # 是否使用多账号代理，默认不使用，True则使用多账号代理
NOTIFY = False # 是否推送日志，默认不推送，True则推送

import random
import time
import requests
import os
import logging
import traceback
from datetime import datetime
import json

class AutoTask:
    def __init__(self, site_name):
        """
        初始化自动任务类
        :param site_name: 站点名称，用于日志显示
        """
        self.site_name = site_name
        self.log_msgs = []  # 日志收集
        self.proxy_url = os.getenv("PROXY_API_URL") # 代理api，返回一条txt文本，内容为代理ip:端口
        self.wx_appid = "wx5dd1e38d5312e70b" # 微信小程序id
        self.wx_code_url = os.getenv("soy_codeurl_data")
        self.wx_code_token = os.getenv("soy_codetoken_data")
        self.host = "api.hgf1862.com"
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
            self.log("[获取代理]没有找到环境变量PROXY_API_URL，不使用代理", level="warning")
            return None
        url = self.proxy_url
        response = requests.get(url)
        proxy = response.text
        self.log(f"[获取代理]: {proxy}")
        return proxy
    
    def check_proxy(self, proxy, session):
        """
        检查代理
        :param proxy: 代理
        :param session: session
        :return: 是否可用
        """
        try:
            url = f"http://{self.host}/"
            response = session.get(url, timeout=5)
            if response.status_code == 200:
                self.log(f"[检查代理]: {proxy} 应该可用")
                return True
            else:
                self.log(f"[检查代理]: {response.text}")
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
                self.log("[检查环境变量]没有找到环境变量soy_wxid_data，请检查环境变量", level="error")
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
            self.log(f"[检查环境变量]发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
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
        
    def wxlogin(self, session, code):
        """
        登录
        :param session: session
        :param code: 微信code
        :return: token
        """
        try:
            url = f"https://{self.host}/YUN/api/onLogin.aspx?opt=onLogin&code={code}"
            headers = {
                "User-Agent": self.user_agent,
                "Content-Type": "application/json",
                "Referer": f"https://servicewechat.com/{self.wx_appid}/286/page-frame.html"
            }
            session.headers.update(headers)
            response = session.get(url)
            response.raise_for_status()
            response_json = response.json()
            if response_json['status'] == 1:
                self.log(f"[登录]: {response_json['msg']}")
                session_id = response_json['SessionID']
                session.headers["sessionid"] = session_id
                session.cookies.set("user=SessionID=", session_id)
                return session_id
            else:
                self.log(f"[登录]发生错误: {response_json['msg']}", level="error")
                return False
        except requests.RequestException as e:
            self.log(f"[登录]发生网络错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        except Exception as e:
            self.log(f"[登录]发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        

    def sign_in(self, session):
        """
        签到
        :param session: session
        :return: 签到结果
        """
        try:
            url = f"https://{self.host}/YUN/Game/2021/QianDao/QianDaoAjax_By28.aspx?op=now&vers={datetime.now().strftime('%Y%m%d')}"
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": f"https://{self.host}/YUN/Game/2021/QianDao/Default_By28.aspx"
            }
            session.headers.update(headers)
            response = session.post(url)
            response.raise_for_status()
            response_json = response.json()
            if response_json['status'] == 1:
                self.log(f"[签到]: {response_json['msg']}")
                return True
            else:
                self.log(f"[签到]: {response_json['msg']}", level="warning")
                return False
        except Exception as e:
            self.log(f"[签到]发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def get_task_list(self, session):
        """
        获取任务列表
        :param session: session
        :return: 任务列表
        """
        try:
            url = f"https://{self.host}/YUN/Game/2024/RenWuJB/AjaxGet.aspx"
            params = {
                "cid": 11,
                "op": "getdata",
                "pid": 8001
            }
            response = session.post(url, params=params)
            response.raise_for_status()
            response_json = response.json()
            if response_json['status'] == 1:
                task_list = response_json['list']
                # 过滤掉下单任务
                task_list = [task for task in task_list if "单" not in task['name']]
                for task in task_list:
                    self.log(f"[任务]: {task['name']} {task['complete_num']}/{task['renwu_num']}")
                return task_list
            else:
                self.log(f"[获取任务列表]发生错误: {response_json['msg']}", level="error")
                return False
        except Exception as e:
            self.log(f"[获取任务列表]发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
    
    def do_task(self, session, task_id, task_name):
        """
        执行任务
        :param session: session
        :param task_id: 任务id
        :param task_name: 任务名称
        :return: 任务url
        """
        try:
            url = f"https://{self.host}/YUN/Game/2024/RenWuJB/AjaxGo.aspx"
            params = {
                "cid": task_id
            }
            response = session.post(url, params=params)
            response.raise_for_status()
            response_json = response.json()
            if response_json['status'] == 1:
                url = response_json['goUrlPath'].split("=")[1]
                self.log(f"[执行任务]: {task_name} 成功")
                return url
            else:
                self.log(f"[执行任务]: {task_name} 发生错误，{response_json['msg']}", level="error")
                return False
        except Exception as e:
            self.log(f"[执行任务]: {task_name} 发生错误，{str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def share_task(self, session, share_url):
        """
        分享任务
        :param session: session
        :param share_url: 分享url
        :return: 分享结果
        """
        try:
            url = f"https://{self.host}/YUN/api/GlobalRecord.aspx"
            params = {
                "opt": "shareData"
            }
            # 注：requests会字典转换为 key=value&key=value
            # 但是嵌套的不行，所以要用json.dumps
            flat_payload = {
                "SessionID": session.headers["sessionid"],
                "datas": json.dumps({
                    "currentPage": "web/web",
                    "prevPage": "web/web",
                    "onload_options": {"url": share_url},
                    "xcx_version": "1.0.287",
                    "options": {"url": share_url}
                }),
                "shareDatas": json.dumps({"title":"","desc":"","imageUrl":"","path":""}),
                "webViewUrl": f"https://{self.host}/YUN/shops/Union_FuLiBuy/ProductFuLi.aspx?Product_ID=8294&Aid=0"
            }
            session.headers["Content-Type"] = "application/x-www-form-urlencoded"
            response = session.post(url, params=params, data=flat_payload)
            response.raise_for_status()
            response_json = response.json()
            if response_json['status'] == 1:
                return True
            else:
                self.log(f"[分享任务]发生错误: {response_json['msg']}", level="error")
                return False
        except Exception as e:
            self.log(f"[分享任务]发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def run(self):
        """
        运行任务
        """
        try:
            # 如果notify模块不存在，从远程下载至本地
            if not os.path.exists("notify.py"):
                url = "https://raw.githubusercontent.com/whyour/qinglong/refs/heads/develop/sample/notify.py"
                response = requests.get(url)
                with open("notify.py", "w", encoding="utf-8") as f:
                    f.write(response.text)
                import notify
            else:
                import notify

            self.log(f"【{self.site_name}】开始执行任务")
            
            # 检查环境变量
            for index, wx_id in enumerate(self.check_env(), 1):
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

                # 执行微信授权
                code = self.wx_code_auth(wx_id)
                if code:
                    login_result = self.wxlogin(session, code)
                    time.sleep(random.randint(3, 5))
                    if login_result:
                        # 签到
                        self.sign_in(session)
                        time.sleep(random.randint(3, 5))
                        # 获取任务列表
                        task_list = self.get_task_list(session)
                        time.sleep(random.randint(3, 5))
                        # 执行任务
                        for task in task_list:
                            if task['complete_status'] == 0:
                                if "分享" in task['name']:
                                    complete_num = task['complete_num']
                                    total_num = task['renwu_num']
                                    for _ in range(complete_num, total_num):
                                        share_url = self.do_task(session, task['cid'], task['name'])
                                        if share_url:
                                            self.share_task(session, share_url)
                                        time.sleep(random.randint(3, 5))
                                else:
                                    self.do_task(session, task['cid'], task['name'])
                                time.sleep(random.randint(3, 5))
                self.log(f"------ 【账号{index}】执行任务完成 ------")
        except Exception as e:
            self.log(f"【{self.site_name}】执行过程中发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
        finally:
            # 任务结束后推送日志
            if NOTIFY:
                title = f"{self.site_name} 运行日志"
                header = "作者：临渊\n"
                content = header + "\n" +"\n".join(self.log_msgs)
                notify.send(title, content)


if __name__ == "__main__":
    auto_task = AutoTask("厚工坊")
    auto_task.run() 