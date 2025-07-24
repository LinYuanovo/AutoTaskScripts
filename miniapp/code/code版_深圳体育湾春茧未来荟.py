"""
 作者： 临渊
 日期： 2025/6/26
 小程序：   深圳体育湾春茧未来荟
 功能： 签到
 变量：soy_wxid_data (微信id) 多个账号用换行分割 
      soy_codetoken_data (微信授权token)
      soy_codeurl_data (微信授权url)
      PROXY_API_URL (代理api，返回一条txt文本，内容为代理ip:端口)
 定时： 一天两次
 cron： 10 8,9 * * *
 更新日志：
 2025/6/26  V1.0    初始化脚本
 2025/7/7   V1.1    适配更多协议
 2025/7/21  V1.2    适配更多协议
 2025/7/22  V1.3    修改协议适配器导入方式
"""

import random
import time
import requests
import os
import sys
import logging
import traceback
import ssl
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
    def __init__(self, site_name):
        """
        初始化自动任务类
        :param site_name: 站点名称，用于日志显示
        """
        self.site_name = site_name
        self.proxy_url = os.getenv("PROXY_API_URL") # 代理api，返回一条txt文本，内容为代理ip:端口
        self.wx_appid = "wx6b10d95e92283e1c" # 微信小程序id
        self.wechat_code_adapter = WechatCodeAdapter(self.wx_appid)
        self.host = "program.springcocoon.com"
        self.user_agent = "Mozilla/5.0 (Linux; Android 12; M2012K11AC Build/SKQ1.220303.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/134.0.6998.136 Mobile Safari/537.36 XWEB/1340129 MMWEBSDK/20240301 MMWEBID/9871 MicroMessenger/8.0.48.2580(0x28003036) WeChat/arm64 Weixin NetType/WIFI Language/zh_CN ABI/arm64 MiniProgramEnv/android"
        
    def log(self, msg, level="info"):
        self.wechat_code_adapter.log(msg, level)

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
            url = f"http://{self.host}/szbay/api/services/app/CRCWeixinEmpMerge/QueryMergeDataAsync"
            payload = 'isGetEmpMoney=true&isGetEmpPoint=true&isGetEmpGrowth=true&isGetCouponNum=false&isShowPerfectEmpInfo=false&isShowSignIn=false&isShowWeixinEmpSubscribe=false'
            response = session.post(url, data=payload, timeout=5)
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
        :return: 登录结果
        """
        try:
            url = f"https://{self.host}/szbay/Weixin/Home/MiniProgramLoginAsync"
            payload = {
                "Code": code,
                "TenancyName": "szbay",
                "AppId": self.wechat_code_adapter.wx_appid
            }
            response = session.post(url, json=payload, timeout=5)
            response_json = response.json()
            if response_json['success'] == True:
                self.log(f"[登录]: 成功")
                return True
            else:
                self.log(f"[登录]发生错误: {response_json['message']}", level="error")
                return False
        except requests.RequestException as e:
            self.log(f"[登录]发生网络错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        except Exception as e:
            self.log(f"[登录]发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def get_xsrf_token(self, session):
        """
        获取xsrf_token
        :param session: session
        :return: 
        """
        try:
            url = f"https://{self.host}/szbay/AppInteract/SignIn/Index"
            response = session.get(url, timeout=5)
            if session.cookies.get("XSRF-TOKEN"):
                xsrf_token = session.cookies.get("XSRF-TOKEN")
                session.headers["X-XSRF-TOKEN"] = xsrf_token
                return True
            else:
                self.log("[获取xsrf_token]失败", level="error")
                return False
        except Exception as e:
            self.log(f"[获取xsrf_token]发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False

    def sign_in(self, session):
        """
        签到
        :param session: session
        :return: 签到结果
        """
        try:
            url = f"https://{self.host}/szbay/api/services/app/SignInRecord/SignInAsync"
            payload = {
                "id": "6c3a00f6-b9f0-44a3-b8a0-d5d709de627d",
                "webApiUniqueID": "404e4880-25da-255b-f6e3-cded50d2cb52"
            }
            response = session.post(url, json=payload)
            response_json = response.json()
            if response_json['success']:
                self.log(f"[签到]: 成功 获得：{response_json['result']['listSignInRuleData'][0]['point']}积分")
                return True
            else:
                self.log(f"[签到]: {response_json['error']['message']}", level="warning")
                return False
        except Exception as e:
            self.log(f"[签到]发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False

    def run(self):
        """
        运行任务
        """
        try:
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
                    
                session.mount('https://', TLSAdapter())
                session.headers["User-Agent"] = self.user_agent

                # 执行微信授权
                code = self.wechat_code_adapter.get_code(wx_id)
                if code:
                    if self.wxlogin(session, code):
                        if self.get_xsrf_token(session):
                            # 签到
                            self.sign_in(session)
                            time.sleep(random.randint(1, 3))
                        
                self.log(f"------ 【账号{index}】执行任务完成 ------")
        except Exception as e:
            self.log(f"【{self.site_name}】执行过程中发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
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
                title = f"{self.site_name} 运行日志"
                header = "作者：临渊\n\n"
                content = header + "\n" +"\n".join(self.wechat_code_adapter.log_msgs)
                notify.send(title, content)


if __name__ == "__main__":
    auto_task = AutoTask("深圳体育湾春茧未来荟")
    auto_task.run() 