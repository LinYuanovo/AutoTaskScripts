"""
 作者:  临渊
 日期:  2025/7/8
 小程序:  万家乐会员俱乐部 (https://a.c1ns.cn/fI33X)
 功能:  签到、抽奖、助力、查询积分
 变量:  soy_wxid_data (微信id) 多个账号用换行分割 
        soy_codetoken_data (微信授权token)
        soy_codeurl_data (微信授权url)
        PROXY_API_URL (代理api，返回一条txt文本，内容为代理ip:端口)
 定时:  一天三次
 cron:  10 12-14 * * *
 更新日志：
 2025/7/8   V1.0    初始化脚本
 2025/7/8   V1.1    更改助力方式，确保每个号都被助力满
 2025/7/23  V1.2    导入微信协议适配器
"""

import random
import time
import requests
import os
import logging
import traceback
import ssl
import sys
from datetime import datetime

MULTI_ACCOUNT_SPLIT = ["\n", "@"] # 分隔符列表
MULTI_ACCOUNT_PROXY = False # 是否使用多账号代理，默认不使用，True则使用多账号代理
NOTIFY = os.getenv("LY_NOTIFY") or False # 是否推送日志，默认不推送，True则推送

# 导入微信协议适配器
if "miniapp" not in os.path.abspath(__file__): # 单独脚本，非拉库
    wechat_adapter_path = ("wechatCodeAdapter.py")
else:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../utils')))
    wechat_adapter_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../utils/wechatCodeAdapter.py'))
if not os.path.exists(wechat_adapter_path):
    try:
        url = "https://raw.githubusercontent.com/LinYuanovo/AutoTaskScripts/refs/heads/main/utils/wechatCodeAdapter.py"
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        with open(wechat_adapter_path, "w", encoding="utf-8") as f:
            f.write(response.text)
    except requests.RequestException as e:
        print(f"下载微信协议适配器文件失败（网络问题），自行复制一份")
        exit(1)
    except Exception as e:
        print(f"下载微信协议适配器文件失败（其他错误）：{e}")
        exit(1)
from wechatCodeAdapter import WechatCodeAdapter # type: ignore

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
        self.proxy_url = os.getenv("PROXY_API_URL") # 代理api，返回一条txt文本，内容为代理ip:端口
        self.wx_appid = "wx07b7a339bb2cf065" # 微信小程序id
        self.wechat_code_adapter = WechatCodeAdapter(self.wx_appid)
        self.host = "wakecloud.chinamacro.com"
        self.activity_no = "2025070400000001"
        self.nickname = ""
        self.user_id = ""
        self.credits = 0
        self.user_agent = "Mozilla/5.0 (Linux; Android 12; M2012K11AC Build/SKQ1.220303.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/134.0.6998.136 Mobile Safari/537.36 XWEB/1340129 MMWEBSDK/20240301 MMWEBID/9871 MicroMessenger/8.0.48.2580(0x28003036) WeChat/arm64 Weixin NetType/WIFI Language/zh_CN ABI/arm64 MiniProgramEnv/android"
        
    def log(self, msg, level="info"):
        self.wechat_code_adapter.log(msg, level)

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
        
    def hide_phone(self, phone):
        """
        隐藏手机号中间4位
        """
        return phone[:3] + "****" + phone[-4:]

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
            url = f"https://{self.host}/mtool/app/luckywheel/detail"
            payload = {
                "activityNo": self.activity_no
            }
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
        :return: 登录结果
        """
        try:
            url = f"https://{self.host}/wd-member/member/login"
            payload = {
                "code": code,
                "tenantId": 473,
                "appBuId": 2065,
                "wxAppId": self.wx_appid,
                "loginType": 0
            }
            response = session.post(url, json=payload, timeout=5)
            response_json = response.json()
            if int(response_json['code']) == 100:
                self.nickname = self.hide_phone(response_json['data']['memberInfo']['phone'])
                self.user_id = response_json['data']['memberInfo']['uniqueAccountId']
                session.headers['cookie'] = f"sessionId={response_json['data']['loginInfo']['sessionId']}"
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

    def sign_in(self, session):
        """
        签到
        :param session: session
        :return: 签到结果
        """
        try:
            url = f"https://{self.host}/wd-member/app/member/sign"
            response = session.get(url, timeout=5)
            response_json = response.json()
            if int(response_json['code']) == 100:
                if response_json.get('data', ''):
                    self.log(f"[{self.nickname}] 签到: 成功 获得: {response_json['data']}积分")
                    return True
                else:
                    self.log(f"[{self.nickname}] 签到: 今日已签到")
                    return False
            else:
                self.log(f"[{self.nickname}] 签到: {response_json['msg']}")
                return False
        except Exception as e:
            self.log(f"[{self.nickname}] 签到: 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def share_lottery(self, session):
        """
        助力抽奖
        :param session: session
        :return: 助力抽奖结果
        """
        try:
            url = f"https://{self.host}/mtool/app/luckywheel/add_draw_by_share"
            payload = {
                "activityNo": self.activity_no,
                "memberId": self.user_id
            }
            response = session.post(url, json=payload, timeout=5)
            response_json = response.json()
            if int(response_json['code']) == 100:
                self.log(f"[{self.nickname}] 助力抽奖: 成功")
                return True
            else:
                self.log(f"[{self.nickname}] 助力抽奖: {response_json['msg']}", level="warning")
                return False
        except Exception as e:
            self.log(f"[{self.nickname}] 助力抽奖: 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False

    def query_lottery(self, session):
        """
        查询抽奖
        :param session: session
        :return: 抽奖
        """
        try:
            url = f"https://{self.host}/mtool/app/luckywheel/joinmember"
            paylaod = {
                "activityNo": self.activity_no
            }
            response = session.post(url, json=paylaod, timeout=5)
            response_json = response.json()
            if int(response_json['code']) == 100:
                lottery_num = response_json['data']['surplusDrawCount']
                self.log(f"[{self.nickname}] 剩余抽奖次数: {lottery_num}")
                return lottery_num
            else:
                self.log(f"[{self.nickname}] 查询抽奖: 发生错误: {response_json['msg']}", level="error")
                return False
        except Exception as e:
            self.log(f"[{self.nickname}] 获取任务列表: 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def do_lottery(self, session):
        """
        抽奖
        :param session: session
        :return: 抽奖结果
        """
        try:
            url = f"https://{self.host}/mtool/app/luckywheel/draw"
            paylaod = {
                "activityNo": self.activity_no
            }
            response = session.post(url, json=paylaod, timeout=5)
            response_json = response.json()
            if int(response_json['code']) == 100:
                self.log(f"[{self.nickname}] 抽奖: 成功 获得: {response_json['data']['giftName']}")
                return True
            else:
                self.log(f"[{self.nickname}] 抽奖: 发生错误: {response_json['msg']}", level="error")
                return False
        except Exception as e:
            self.log(f"[{self.nickname}] 抽奖: 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
                
    def get_user_credits(self, session):
        """
        获取用户积分
        :param session: session
        :return: 用户积分
        """
        try:
            url = f"https://{self.host}/wd-member/app/member/score/statistic/{self.user_id}"
            response = session.get(url, timeout=5)
            response_json = response.json()
            if int(response_json['code']) == 100:
                self.credits = response_json['data']['usableScore']
                self.log(f"[{self.nickname}] 积分: {self.credits}")
                return True
            else:
                self.log(f"[{self.nickname}] 获取用户积分: 发生错误: {response_json['msg']}", level="error")
                return False
        except Exception as e:
            self.log(f"[{self.nickname}] 获取用户积分: 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def run(self):
        """
        运行任务
        """
        try:
            self.log(f"【{self.script_name}】开始执行任务")
            user_id_list = []
            wxid_list = list(self.check_env())
            session_list = []
            nickname_list = []

            # 先登录所有账号，收集user_id
            for index, wx_id in enumerate(wxid_list, 1):
                self.log("")
                self.log(f"------ 【账号{index}】开始登录 ------")
                session = requests.Session()
                headers = {
                    "User-Agent": self.user_agent,
                    "Cookie": "",
                    "Content-Type": "application/json"
                }
                session.headers.update(headers)

                if MULTI_ACCOUNT_PROXY:
                    proxy = self.get_proxy()
                    if proxy:
                        session.proxies.update({"http": f"http://{proxy}", "https": f"http://{proxy}"})
                        # 检查代理，不可用重新获取
                        while not self.check_proxy(proxy, session):
                            proxy = self.get_proxy()
                            session.proxies.update({"http": f"http://{proxy}", "https": f"http://{proxy}"})

                # 执行微信授权
                code = self.wechat_code_adapter.get_code(wx_id)
                if code:
                    if self.wxlogin(session, code):
                        user_id_list.append(self.user_id)
                        session_list.append(session)
                        nickname_list.append(self.nickname)
                    else:
                        session_list.append(None)
                        nickname_list.append("")
                self.log(f"------ 【账号{index}】登录完成 ------")

            for i, (session, user_id, nickname) in enumerate(zip(session_list, user_id_list, nickname_list)):
                if not session:
                    continue
                self.nickname = nickname
                self.user_id = user_id
                self.log("")
                self.log(f"------ 【账号{i+1}】开始做任务 ------")
                # 签到
                self.sign_in(session)
                time.sleep(random.randint(3, 5))
                # 查询抽奖
                lottery_num = self.query_lottery(session)
                time.sleep(random.randint(3, 5))
                # 抽奖
                for _ in range(lottery_num):
                    self.do_lottery(session)
                    time.sleep(random.randint(3, 5))
                # 获取用户积分
                self.get_user_credits(session)

                # 环形助力
                n = len(user_id_list)
                max_help = min(2, n-1)
                if max_help > 0:
                    help_indices = [(i + j + 1) % n for j in range(max_help)]
                    for idx in help_indices:
                        help_id = user_id_list[idx]
                        self.user_id = help_id
                        self.share_lottery(session)
                        time.sleep(random.randint(3, 5))
                self.user_id = user_id  # 恢复自己
                self.log(f"------ 【账号{i+1}】任务完成 ------")

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
                content = header + "\n" +"\n".join(self.wechat_code_adapter.log_msgs)
                notify.send(title, content)


if __name__ == "__main__":
    auto_task = AutoTask("万家乐会员俱乐部")
    auto_task.run() 