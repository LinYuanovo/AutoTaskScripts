"""
 作者:  临渊
 日期:  2025/7/22
 APP:   宠胖胖 (https://ch.mewpet.cn/2vPn)
 功能:  签到、做部分任务、领取在线和任务奖励、查询积分
 变量:  cpp_token = 'Authorization' (chongpangpang.com请求下的Authorization或token值)
 定时:  一天四次
 cron:  10 8,12,16,20 * * *
 更新日志：
 2025/7/22  V1.0    初始化脚本
"""

import json
import random
import time
import requests
import os
import logging
import traceback
import ssl
from datetime import datetime
import sys

MULTI_ACCOUNT_SPLIT = ["\n", "@"] # 分隔符列表
MULTI_ACCOUNT_PROXY = False # 是否使用多账号代理，默认不使用，True则使用多账号代理
NOTIFY = os.getenv("LY_NOTIFY") or False # 是否推送日志，默认不推送，True则推送

# 导入微信协议适配器
if "app" not in os.path.abspath(__file__): # 单独脚本，非拉库
    wechat_adapter_path = ("wechatCodeAdapter.py")
else:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../utils')))
    wechat_adapter_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../utils/wechatCodeAdapter.py'))
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
        self.wx_appid = "wx49133dd26d6fc20b" # 微信小程序id
        self.wechat_code_adapter = WechatCodeAdapter(self.wx_appid)
        self.host = "shareactivity.chongpangpang.com"
        self.user_id = ""
        self.nickname = ""
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
            url = f"https://{self.host}/"
            response = session.get(url, timeout=5)
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
            cpp_token = os.getenv(f"cpp_token")
            if not cpp_token:
                self.log("[检查环境变量] 没有找到环境变量cpp_token，请检查环境变量", level="error")
                return None

            # 自动检测分隔符
            split_char = None
            for sep in MULTI_ACCOUNT_SPLIT:
                if sep in cpp_token:
                    split_char = sep
                    break
            if not split_char:
                # 如果都没有分隔符，默认当作单账号
                cpp_tokens = [cpp_token]
            else:
                cpp_tokens = cpp_token.split(split_char)

            for cpp_token in cpp_tokens:
                if "=" in cpp_token:
                    cpp_token = cpp_token.split("=")[1]
                    if "Bearer" not in cpp_token:
                        cpp_token = "Bearer " + cpp_token
                    yield cpp_token
                else:
                    if "Bearer" not in cpp_token:
                        cpp_token = "Bearer " + cpp_token
                    yield cpp_token
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
        
    def get_openid(self, session, code):
        """
        获取openid
        :param session: session
        :param code: 微信code
        :return: session_key, openid
        """
        try:
            url = f"https://{self.host}/api/Login/getOpenpid"
            payload = {
                "code": code
            }
            response = session.post(url, json=payload, timeout=5)
            response_json = response.json()
            if int(response_json['code']) == 1:
                session_key = response_json['data']['session_key']
                openid = response_json['data']['openid']
                return session_key, openid
            else:
                self.log(f"[获取openid] 失败，错误信息: {response_json['msg']}", level="error")
                return False
        except Exception as e:
            self.log(f"[获取openid] 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def save_account_info(self, account_info):
        """
        保存账号信息
        :param account_info: 账号信息（新获取的列表）
        """
        file_path = "xsq_account_info.json"
        # 读取旧数据
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                old_list = json.load(f)
        else:
            old_list = []
        # 构建 wx_id 到账号的映射，方便查找和更新
        old_dict = {item['wx_id']: item for item in old_list}
        # self.log(f"旧数据: {old_dict}")
        for new_item in account_info:
            old_dict[new_item['wx_id']] = new_item  # 有则更新，无则新增
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(list(old_dict.values()), f, ensure_ascii=False, indent=2)
            self.log(f"保存新数据: 成功")

    def load_account_info(self):
        """
        加载账号信息
        :return: 账号信息
        """
        if os.path.exists("xsq_account_info.json"):
            with open("xsq_account_info.json", "r", encoding="utf-8") as f:
                account_info = json.load(f)
            return account_info
        else:
            return []
    
    def wxlogin(self, session, session_key, openid):
        """
        登录
        :param session: session
        :param session_key: session_key
        :param openid: openid
        :return: 登录结果
        """
        try:
            url = f"https://{self.host}/api/user/login"
            payload = {
                "session_key": session_key,
                "openid": openid,
                "invitation_code": "",
                "js_code": ""
            }
            response = session.post(url, json=payload, timeout=5)
            response_json = response.json()
            if int(response_json['code']) == 1:
                self.nickname = self.hide_phone(response_json['data']['mobile'])
                session.headers['token'] = response_json['data']['token']
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
            url = f"https://cn-prod01-gw.chongpangpang.com/cpp-user-management/v3/users/detail"
            response = session.post(url, timeout=10)
            response_json = response.json()
            user_id = response_json.get('userId', '')
            if user_id:
                self.user_id = user_id
                session.headers['X-User-Id'] = self.user_id
                self.nickname = response_json.get('nickName', '')
                return True
            else:
                self.log(f"[{self.nickname}] 获取用户信息: 失败，错误信息: {response_json['message']}", level="error")
                return False
        except Exception as e:
            self.log(f"[{self.nickname}] 获取用户信息: 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False

    def sign_in(self, session):
        """
        签到
        :param session: session
        :return: 签到结果
        """
        try:
            url = f"https://{self.host}/api-cpp-gw/cpp-user-score-management/v1/user-score/checkin"
            response = session.post(url, timeout=10)
            response_json = response.json()
            score = response_json.get('scores', '')
            if score:
                self.log(f"[{self.nickname}] 签到: 成功 获得{score}积分")
                return True
            else:
                self.log(f"[{self.nickname}] 签到: {response_json['message']}")
                return False
        except Exception as e:
            self.log(f"[{self.nickname}] 签到: 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def get_task_list(self, session):
        """
        获取任务列表
        :param session: session
        :return: 任务列表
        """
        try:
            url = f"https://{self.host}/api-cpp-gw/cpp-user-score-management/v2/user-score/action-score-tasks"
            response = session.get(url, timeout=10)
            response_json = response.json()
            task_list = response_json.get('taskInfoList', [])
            if task_list:
                return response_json
            else:
                self.log(f"[{self.nickname}] 获取任务列表: 失败，错误信息: {response_json['message']}", level="error")
                return None
        except Exception as e:
            self.log(f"[{self.nickname}] 获取任务列表: 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return None
        
    def do_task(self, session, task_code):
        """
        执行任务
        :param session: session
        :param task_code: 任务code
        """
        try:
            url = f"https://{self.host}/api-cpp/cpp-user-score-management/v1/user-score/clock-in/{task_code}"
            response = session.post(url, timeout=10)
            if response.status_code == 200:
                self.log(f"[{self.nickname}] 执行任务: 成功")
                return True
            else:
                self.log(f"[{self.nickname}] 执行任务: 失败，错误信息: {response.text}", level="error")
                return False
        except Exception as e:
            self.log(f"[{self.nickname}] 执行任务: 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def get_unreceived_reward(self, session):
        """
        获取未领取的奖励列表
        :param session: session
        :return: 未领取的奖励
        """
        try:
            url = f"https://{self.host}/api-cpp-gw/cpp-user-score-management/v2/user-score/index"
            response = session.get(url, timeout=10)
            response_json = response.json()
            onlineInfo = response_json.get('onlineInfo', {})
            if onlineInfo:
                return response_json
        except Exception as e:
            self.log(f"[{self.nickname}] 获取未领取的奖励列表: 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return None
        
    def get_online_reward(self, session, stage):
        """
        获取在线奖励
        :param session: session
        :param stage: 阶段
        """
        try:
            url = f"https://{self.host}/api-cpp-gw/cpp-user-score-management/v1/user-score/online/reward/draw/{stage}"
            response = session.post(url, timeout=10)
            response_json = response.json()
            message = response_json.get('message', '')
            if not message:
                self.log(f"[{self.nickname}] 领取在线奖励: 成功")
                return True
            else:
                self.log(f"[{self.nickname}] 领取在线奖励: 失败，错误信息: {response_json['message']}", level="error")
                return False
        except Exception as e:
            self.log(f"[{self.nickname}] 领取在线奖励: 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def get_reward(self, session, reward_id, reward_title, reward_score):
        """
        领取任务奖励
        :param session: session
        :param reward_id: 奖励id
        :param reward_title: 奖励标题
        :param reward_score: 奖励积分
        """
        try:
            url = f"https://{self.host}/api-cpp/cpp-user-score-management/v1/user-score/draw-score"
            payload = f"{reward_id}"
            response = session.post(url, data=payload, timeout=10)
            response_json = response.json()
            result = response_json.get('totalScores', '')
            if result:
                self.log(f"[{self.nickname}] 领取 |{reward_title} {reward_score}积分| 成功")
                return True
            else:
                self.log(f"[{self.nickname}] 领取 |{reward_title} {reward_score}积分| 失败，错误信息: {response_json['message']}", level="error")
                return False
        except Exception as e:
            self.log(f"[{self.nickname}] 领取 |{reward_title} {reward_score}积分| 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def get_task_reward_ladder(self, session, ladder_index):
        """
        获取任务阶梯奖励
        :param session: session
        :param ladder_index: 任务阶段
        :return: 领取返回
        """
        try:
            url = f"https://{self.host}/api-cpp/cpp-user-score-management/v1/user-score/task-ladder/draw"
            payload = {
                "ladderIndex": ladder_index
            }
            response = session.post(url, json=payload, timeout=10)
            if response.text == "true":
                self.log(f"[{self.nickname}] 领取任务{ladder_index}阶梯奖励: 成功")
                return True
            else:
                self.log(f"[{self.nickname}] 领取任务{ladder_index}阶梯奖励: {response.json()['message']}", level="warning")
                return False
        except Exception as e:
            self.log(f"[{self.nickname}] 领取任务{ladder_index}阶梯奖励: 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def run(self):
        """
        运行任务
        """
        try:
            self.log(f"【{self.script_name}】开始执行任务")
            # account_info_list = []
            # local_account_info = self.load_account_info()
            # self.log(f"本地共{len(local_account_info)}个账号")
            for index, token in enumerate(self.check_env(), 1):
                self.log("")
                self.log(f"------ 【账号{index}】开始执行任务 ------")
                session = requests.Session()
                headers = {
                    "User-Agent": self.user_agent,
                    "Content-Type": "application/json;charset=UTF-8",
                    "Authorization": token
                }
                session.headers.update(headers)

                if MULTI_ACCOUNT_PROXY:
                    proxy = self.get_proxy()
                    if proxy:
                        session.proxies.update({"http": f"http://{proxy}", "https": f"http://{proxy}"})
                        # # 检查代理，不可用重新获取
                        # while not self.check_proxy(proxy, session):
                        #     proxy = self.get_proxy()
                        #     session.proxies.update({"http": f"http://{proxy}", "https": f"http://{proxy}"})

                # 获取用户信息
                if not self.get_user_info(session):
                    self.nickname = f"账号{index}"
                # 签到
                self.sign_in(session)
                time.sleep(random.randint(3, 5))
                # 获取任务列表
                task_response = self.get_task_list(session)
                task_list = task_response.get('taskInfoList', [])
                time.sleep(random.randint(3, 5))
                for task in task_list:
                    if "档案" in task['taskTitle'] or "评论" in task['taskTitle']:
                        pass
                    else:
                        need_num = task['receiveLimit'] - task['receiveCount']
                        for _ in range(need_num):
                            task_code = task['taskCode']
                            self.do_task(session, task_code)
                            time.sleep(random.randint(3, 5))
                # 获取未领取的奖励列表
                unreceived_reward_response = self.get_unreceived_reward(session)
                if unreceived_reward_response:
                    online_info = unreceived_reward_response.get('onlineInfo', '')
                    # 领取在线奖励
                    if online_info:
                        if online_info['remainder'] == 0:
                            stage = online_info['stage']
                            self.get_online_reward(session, stage)
                            time.sleep(random.randint(3, 5))
                    # 领取任务奖励
                    unreceived_reward_list = unreceived_reward_response.get('unclaimedScores', [])
                    for reward in unreceived_reward_list:
                        self.get_reward(session, reward['recordId'], reward['title'], reward['score'])
                        time.sleep(random.randint(3, 5))
                # 重新获取一次任务列表
                task_response = self.get_task_list(session)
                task_reward_ladder = task_response.get('taskRewardLadder', '')
                task_complete_count = task_reward_ladder.get('taskCompleteCount', '')
                reward_ladder = task_reward_ladder.get('rewardLadder', [])
                for ladder_index, ladder in enumerate(reward_ladder, 1):
                    if task_complete_count >= ladder['taskNum']:
                        self.get_task_reward_ladder(session, ladder_index)
                        time.sleep(random.randint(3, 5))
                # 重新获取一次未领取的奖励列表
                unreceived_reward_response = self.get_unreceived_reward(session)
                if unreceived_reward_response:
                    score = unreceived_reward_response.get('totalScores', '')
                    if score:
                        self.log(f"[{self.nickname}] 当前积分余额: {score}积分")
                    
                self.log(f"------ 【账号{index}】执行任务完成 ------")
            # # 保存新账号信息
            # if account_info_list:
            #     self.save_account_info(account_info_list)
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
    auto_task = AutoTask("宠胖胖")
    auto_task.run() 