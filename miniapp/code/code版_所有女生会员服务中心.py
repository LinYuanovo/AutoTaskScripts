"""
作者: 临渊
日期: 2025/7/27
name: code版_所有女生会员服务中心
入口: 微信小程序 (https://a.c1ns.cn/2cVCq)
功能: 签到、浏览、预约、查询积分
变量: soy_wxid_data (微信id) 多个账号用换行分割 
        soy_codetoken_data (微信授权token)
        soy_codeurl_data (微信授权url)
        PROXY_API_URL (代理api，返回一条txt文本，内容为代理ip:端口)
定时: 一天两次
cron: 10 11,12 * * *
------------更新日志------------
2025/7/27   V1.0    初始化脚本
2025/7/28   V1.1    修改头部注释，以便拉库
"""

import json
import random
import time
import requests
import os
import base64
import hashlib
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
        self.wx_appid = "wx7d1403fe84339669" # 微信小程序id
        self.wechat_code_adapter = WechatCodeAdapter(self.wx_appid)
        self.host = "7.wawo.cc"
        self.activity_code = "D2L0T1T4"
        self.nickname = ""
        self.token = ""
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
        
    def save_account_info(self, account_info):
        """
        保存账号信息
        :param account_info: 账号信息（新获取的列表）
        """
        file_path = "synshyfwzx_account_info.json"
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

    def remove_account_info(self, wx_id):
        """
        删除账号信息
        :param wx_id: 微信id
        """
        file_path = "synshyfwzx_account_info.json"
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                old_list = json.load(f)
            old_list = [item for item in old_list if item['wx_id'] != wx_id]
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(old_list, f, ensure_ascii=False, indent=2)
            self.log(f"删除账号信息: 成功")

    def load_account_info(self):
        """
        加载账号信息
        :return: 账号信息
        """
        if os.path.exists("synshyfwzx_account_info.json"):
            with open("synshyfwzx_account_info.json", "r", encoding="utf-8") as f:
                account_info = json.load(f)
            return account_info
        else:
            return []
    
    def wxlogin(self, session, code):
        """
        登录
        :param session: session
        :param code: code
        :return: 登录结果
        """
        try:
            url = f"https://{self.host}/api/auth/common/login"
            payload = {
                "code": code,
                "platform": "wx_app",
                "businessLine": 1
            }
            response = session.post(url, json=payload, timeout=15)
            response_json = response.json()
            if response_json['code'] == "000":
                self.nickname = response_json['data']['nickName']
                self.token = response_json['data']['accessToken']
                session.headers['AccessToken'] = self.token
                return self.token
            else:
                self.log(f"[登录] 失败，错误信息: {response_json.get('message', '未知错误')}", level="error")
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
            url = f"https://{self.host}/api/account/wx/member/base"
            response = session.get(url, timeout=15)
            response_json = response.json()
            if response_json['code'] == "000":
                self.nickname = response_json['data']['nickName']
                return True
            else:
                self.log(f"[获取用户信息] 失败，错误信息: {response_json.get('message', '未知错误')}", level="error")
                return False
        except Exception as e:
            self.log(f"[获取用户信息] 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def sign_in(self, session):
        """
        签到
        :param session: session
        """
        try:
            url = f"https://{self.host}/api/activity/wx/task/sign/signIn"
            response = session.post(url, timeout=15)
            response_json = response.json()
            if response_json['code'] == "000":
                self.log(f"[{self.nickname}] 签到成功")
                return True
            else:
                self.log(f"[{self.nickname}] 签到: {response_json.get('message', '未知错误')}", level="warning")
                return False
        except Exception as e:
            self.log(f"[{self.nickname}] 签到 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def get_task_list(self, session):
        """
        获取任务列表
        :param session: session
        :return: 任务列表
        """
        try:
            url = f"https://{self.host}/api/task/wx/un/ver2/task/list"
            params = {
                "activityCode": self.activity_code,
                "type": 1
            }
            response = session.get(url, params=params, timeout=15)
            response_json = response.json()
            if response_json['code'] == "000":
                return response_json['data']
            else:
                return []
        except Exception as e:
            self.log(f"[{self.nickname}] 获取任务列表 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return []
        
    def finish_browse_task(self, session, task_url):
        """
        完成浏览任务
        :param session: session
        :param task_url: 任务url
        """
        try:
            url = f"https://{self.host}/api/task/wx/ver2/task/done"
            headers = {
                "User-Agent": self.user_agent,
                "AccessToken": self.token,
                "activityCode": self.activity_code
            }
            payload = {
                "path": task_url
            }
            response = session.post(url, json=payload, headers=headers, timeout=15)
            response_json = response.json()
            if response_json['code'] == "000":
                if response_json['data']:
                    self.log(f"[{self.nickname}] 浏览成功")
                    return True
                else:
                    self.log(f"[{self.nickname}] 浏览任务已完成", level="warning")
                    return True
            else:
                self.log(f"[{self.nickname}] 浏览任务失败: {response_json.get('message', '未知错误')}", level="error")
                return False
        except Exception as e:
            self.log(f"[{self.nickname}] 浏览任务失败: 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def get_activities(self, session):
        """
        获取活动列表
        :param session: session
        :return: 活动列表
        """
        try:
            url = f"https://{self.host}/api/live/wx/strategy/activities"
            response = session.get(url, timeout=15)
            response_json = response.json()
            if response_json['code'] == "000":
                return response_json['data']
            else:
                return []
        except Exception as e:
            self.log(f"[{self.nickname}] 获取活动列表: 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return []
        
    def get_goods_id(self, session, activity_id):
        """
        获取商品id
        :param session: session
        :param activity_id: 活动id
        :return: 商品id
        """
        try:
            url = f"https://{self.host}/api/live/wx/strategy/un/top/daily"
            params = {
                "activityId": activity_id,
                "searchAll": "true"
            }
            response = session.get(url, params=params, timeout=15)
            response_json = response.json()
            if response_json['code'] == "000":
                return response_json['data']
            else:
                return []
        except Exception as e:
            self.log(f"[{self.nickname}] 获取商品id: 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return []
    
    def finish_appointment(self, session, activity_id, goods_id):
        """
        完成预约
        :param session: session
        :param activity_id: 活动id
        :param goods_id: 商品id
        """
        try:
            url = f"https://{self.host}/api/live/wx/strategy/appointment"
            payload = {
                "activityId": activity_id,
                "goodsId": goods_id,
                "type": 1
            }
            response = session.post(url, json=payload, timeout=15)
            response_json = response.json()
            if response_json['code'] == "000":
                self.log(f"[{self.nickname}] 预约: {response_json['message']}")
                return True
            else:
                self.log(f"[{self.nickname}] 预约: {response_json.get('message', '未知错误')}", level="error")
                return False
        except Exception as e:
            self.log(f"[{self.nickname}] 预约: 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def get_user_points(self, session):
        """
        获取用户积分
        :param session: session
        :return: 用户积分
        """
        try:
            url = f"https://{self.host}/api/score/wx/score/queryAmount"
            response = session.get(url, timeout=15)
            response_json = response.json()
            if response_json['code'] == "000":
                self.log(f"[{self.nickname}] 积分: {response_json['data']}")
                return response_json['data']
            else:
                self.log(f"[{self.nickname}] 获取用户积分: {response_json.get('message', '未知错误')}", level="error")
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
            account_info_list = []
            local_account_info = self.load_account_info()
            self.log(f"本地共{len(local_account_info)}个账号")
            for index, wx_id in enumerate(self.check_env(), 1):
                # 清理账号信息
                self.nickname = ""
                self.token = ""
                self.log("")
                self.log(f"------ 【账号{index}】开始执行任务 ------")
                session = requests.Session()
                headers = {
                    "User-Agent": self.user_agent,
                    "authority": self.host
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

                token = None
                # 查找本地账号
                if local_account_info:
                    for info in local_account_info:
                        if info['wx_id'] == wx_id:
                            token = info['token']
                            # self.log(f"[登录] 找到本地token: {token}")
                            break
                # 本地没有则授权获取
                if not token:
                    code = self.wechat_code_adapter.get_code(wx_id)
                    if code:
                        token = self.wxlogin(session, code)
                        now_account_info = {
                            "wx_id": wx_id,
                            "token": token
                        }
                        account_info_list.append(now_account_info)
                else:
                    self.token = token
                    session.headers['AccessToken'] = token
                # 获取用户信息
                if not self.get_user_info(session):
                    self.remove_account_info(wx_id)
                    code = self.wechat_code_adapter.get_code(wx_id)
                    if code:
                        token = self.wxlogin(session, code)
                        now_account_info = {
                            "wx_id": wx_id,
                            "token": token
                        }
                        account_info_list.append(now_account_info)
                    else:
                        self.log(f"[{self.nickname}] 授权失败，跳过该账号", level="error")
                        continue
                # 签到
                self.sign_in(session)
                time.sleep(random.randint(3, 5))
                # 获取任务列表
                task_list = self.get_task_list(session)
                time.sleep(random.randint(3, 5))
                for task in task_list:
                    if "浏览" in task['name'] and not task['finishStatus']:
                        self.finish_browse_task(session, task['taskBtCss']['url'])
                        time.sleep(random.randint(3, 5))
                    elif "预约" in task['name'] and not task['finishStatus']:
                        # 获取活动列表
                        activities = self.get_activities(session)
                        time.sleep(random.randint(3, 5))
                        now_time_string = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        # 获取商品id
                        for activity in activities:
                            if now_time_string > activity['startLiveTimeString'] and now_time_string < activity['endLiveTimeString']:
                                activity_id = activity['id']
                                goods_id_list = self.get_goods_id(session, activity_id)
                                time.sleep(random.randint(3, 5))
                                goods_id = goods_id_list[random.randint(0, len(goods_id_list) - 1)]
                                if self.finish_appointment(session, activity_id, goods_id):
                                    break
                # 获取用户积分
                self.get_user_points(session)
                time.sleep(random.randint(3, 5))
                self.log(f"------ 【账号{index}】执行任务完成 ------")
                # 清理session
                session.close()
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
    auto_task = AutoTask("所有女生会员服务中心")
    auto_task.run() 