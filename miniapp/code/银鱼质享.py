"""
 作者:  临渊
 日期:  2025/6/18
 小程序:    银鱼质享
 功能:  看视频、提现
 变量:  soy_wxid_data (微信id) 多个账号用换行分割 
        soy_codetoken_data (微信授权token)
        soy_codeurl_data (微信授权url)
        PROXY_API_URL (代理api，返回一条txt文本，内容为代理ip:端口)
 定时:  一天一次
 cron:  10 10 * * *
 更新日志：
 2025/6/18  V1.0    初始化脚本
 2025/7/19  V1.1    修改为code
 2025/7/21  V1.2    适配更多协议
 2025/7/22  V1.3    修改协议适配器导入方式
"""

import json
import random
import time
import requests
import os
import sys
import logging
import traceback
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

class AutoTask:
    def __init__(self, script_name):
        """
        初始化自动任务类
        :param script_name: 脚本名称，用于日志显示
        """
        self.script_name = script_name
        self.proxy_url = os.getenv("PROXY_API_URL") # 代理api，返回一条txt文本，内容为代理ip:端口
        self.wx_appid = "wx5b82dfe3747e533f" # 微信小程序id
        self.wechat_code_adapter = WechatCodeAdapter(self.wx_appid)
        self.host = "n05.sentezhenxuan.com"
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
            url = f"https://{self.host}/kaoshop/integral/app/integral/getUserIntegral"
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
            url = f"https://{self.host}/api/v2/routine/silenceAuth"
            params = {
                "code": code,
                "spread_spid": 0,
                "spread_code": 0,
            }
            response = session.get(url, params=params, timeout=5)
            response_json = response.json()
            if int(response_json['status']) == 200:
                self.nickname = response_json['data']['userInfo']['nickname']
                session.headers['authori-zation'] = f"Bearer {response_json['data']['token']}"
                return f"Bearer {response_json['data']['token']}"
            else:
                self.log(f"[登录] 失败，错误信息: {response_json['msg']}", level="error")
                return False
        except requests.RequestException as e:
            self.log(f"[登录] 发生网络错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        except Exception as e:
            self.log(f"[登录] 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def save_account_info(self, account_info):
        """
        保存账号信息
        :param account_info: 账号信息（新获取的列表）
        """
        file_path = "yyzx_account_info.json"
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
        if os.path.exists("yyzx_account_info.json"):
            with open("yyzx_account_info.json", "r", encoding="utf-8") as f:
                account_info = json.load(f)
            return account_info
        else:
            return []
        
    def get_user_info(self, host, session):
        """
        获取用户信息
        :param host: 域名
        :param session: session
        :return: 用户信息
        """
        try:
            url = f"https://{host}/api/user"
            response = session.get(url, timeout=5)
            response.raise_for_status()
            response_json = response.json()
            if response_json.get('status') == 200:
                self.nickname = response_json['data']['nickname']
                return True
            else:
                return False
        except Exception as e:
            self.log(f"[{self.nickname}]获取用户信息 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False

    def get_video_list(self, host, session):
        """
        获取视频列表
        :param host: 域名
        :param session: session
        :return: 视频列表
        """
        try:
            url = f"https://{host}/api/video/list?page=1&limit=10&status=1&source=0&isXn=1"
            response = session.get(url, timeout=5)
            response.raise_for_status()
            response_json = response.json()
            video_list = response_json.get('data', [])
            return video_list
        except Exception as e:
            self.log(f"[{self.nickname}]获取视频列表 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return []

    def watch_video(self, host, session, video_id, watch_time):
        """
        执行看视频
        :param host: 域名
        :param session: session
        :param video_id: 视频id
        :param watch_time: 观看时间
        """
        try:
            url = f"https://{host}/api/video/videoJob"
            
            # 获取当前时间戳（毫秒）
            current_timestamp = int(datetime.now().timestamp() * 1000)
            
            payload = {
                "vid": video_id,
                "startTime": current_timestamp,
                "endTime": current_timestamp + watch_time + 1000,
                "baseVersion": "3.3.5",
                "playMode": 0
            }
            response = session.post(url, json=payload)
            response.raise_for_status()
            
            # 处理响应
            response_json = response.json()
            if response_json.get('status') == 200:
                self.log(f"[{self.nickname}]看视频成功 视频ID: {video_id}", level="info")
                return True
            else:
                self.log(f"[{self.nickname}]看视频失败: {response_json['msg']}", level="warning")
                return False
                
        except requests.RequestException as e:
            self.log(f"[{self.nickname}]看视频发生网络错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        except Exception as e:
            self.log(f"[{self.nickname}]看视频发生未知错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def update_withdraw_info(self, host, session):
        """
        更新提现信息
        :param host: 域名
        :param session: session
        :return: 当前余额
        """
        try:
            url = f"https://{host}/api/updateTxInfo"
            response = session.get(url, timeout=5)
            response.raise_for_status()
            response_json = response.json()
            if response_json.get('status') == 200:
                self.log(f"[{self.nickname}]当前余额：{response_json['data']['now_money']}元", level="info")
                balance = float(response_json['data']['now_money'])
                return balance
            else:
                self.log(f"[{self.nickname}]更新提现信息失败: {response_json['msg']}", level="warning")
                return 0
        except Exception as e:
            self.log(f"[{self.nickname}]更新提现信息发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return 0
        
        
    def withdraw(self, host, session):
        """
        执行提现
        :param host: 域名
        :param session: session
        """
        try:
            url = f"https://{host}/api/userTx"
            response = session.get(url, timeout=5)
            response.raise_for_status()
            response_json = response.json()
            if response_json.get('status') == 200:
                self.log(f"[{self.nickname}]提现成功: {response_json['msg']}", level="info")
                return True
            else:
                self.log(f"[{self.nickname}]提现失败: {response_json['msg']}", level="warning")
                return False
        except Exception as e:
            self.log(f"[{self.nickname}]提现发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def run(self):
        """
        运行任务
        """
        try:
            self.log(f"【{self.script_name}】开始执行任务")
            account_info_list = []
            local_account_info = self.load_account_info()
            self.log(f"本地共{len(local_account_info)}个账号")
            # 检查环境变量
            for index, wx_id in enumerate(self.check_env(), 1):
                self.log("")
                self.log(f"------ 【账号{index}】开始执行任务 ------")
                session = requests.Session()
                headers = {
                    "User-Agent": self.user_agent,
                    "Content-Type": "application/json",
                    "form-type": "routine-zhixiang"
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
                token = None
                # 查找本地账号
                if local_account_info:
                    for info in local_account_info:
                        if info['wx_id'] == wx_id:
                            token = info['token']
                            break
                # 本地没有则授权获取
                if not token:
                    code = self.wechat_code_adapter.get_code(wx_id)
                    if code:
                        token = self.wxlogin(session, code)
                        if token:
                            now_account_info = {
                                "wx_id": wx_id,
                                "token": token
                            }
                            account_info_list.append(now_account_info)
                if token:
                    session.headers['authori-zation'] = token
                    # 检查ck是否过期
                    if not self.get_user_info(self.host, session):
                        self.log(f"[{self.nickname}]ck已过期，重新授权", level="warning")
                        code = self.wx_code_auth(wx_id)
                        if code:
                            token = self.wechat_code_adapter.wxlogin(session, code)
                            if token:
                                now_account_info = {
                                    "wx_id": wx_id,
                                    "token": token
                                }
                                account_info_list.append(now_account_info)
                    video_list = self.get_video_list(self.host, session)
                    if not video_list:
                        self.log(f"[{self.nickname}]获取视频列表失败，跳过当前账号看视频任务", level="warning")
                    for video in video_list:
                        video_id = video['id']
                        if video_id:
                            watch_time = video['wait_time']
                            self.watch_video(self.host, session, video_id, watch_time)
                            time.sleep(random.randint(10, 15))
                    user_balance = self.update_withdraw_info(self.host, session)
                    if user_balance >= 0.2:
                        self.withdraw(self.host, session)
                    else:
                        self.log(f"[{self.nickname}]当前余额不足0.2元，跳过提现", level="warning")

                self.log(f"------ 【账号{index}】执行任务完成 ------")
            # 保存新账号信息
            if account_info_list:
                self.save_account_info(account_info_list)
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
    auto_task = AutoTask("银鱼质享")
    auto_task.run() 