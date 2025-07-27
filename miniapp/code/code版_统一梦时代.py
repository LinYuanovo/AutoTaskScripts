"""
作者: 临渊
日期: 2025/6/27
name: code版_统一梦时代
入口: 微信小程序
功能: 签到、抽奖、查询积分
变量: soy_wxid_data (微信id) 多个账号用换行分割 
    soy_codetoken_data (微信授权token)
    soy_codeurl_data (微信授权url)
    PROXY_API_URL (代理api，返回一条txt文本，内容为代理ip:端口)
定时: 一天两次
cron: 10 8,9 * * *
------------更新日志------------
2025/6/27  V1.0    初始化脚本
2025/7/7   V1.1    适配更多协议
2025/7/21  V1.2    适配更多协议
2025/7/22  V1.3    修改协议适配器导入方式
2025/7/28  V1.4    修改头部注释，以便拉库
"""

import json
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
    def __init__(self, script_name):
        """
        初始化自动任务类
        :param script_name: 脚本名称，用于日志显示
        """
        self.script_name = script_name
        self.proxy_url = os.getenv("PROXY_API_URL") # 代理api，返回一条txt文本，内容为代理ip:端口
        self.wx_appid = "wx532ecb3bdaaf92f9" # 微信小程序id
        self.wechat_code_adapter = WechatCodeAdapter(self.wx_appid)
        self.host = "xapi.weimob.com"
        self.user_agent = "Mozilla/5.0 (Linux; Android 12; M2012K11AC Build/SKQ1.220303.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/134.0.6998.136 Mobile Safari/537.36 XWEB/1340129 MMWEBSDK/20240301 MMWEBID/9871 MicroMessenger/8.0.48.2580(0x28003036) WeChat/arm64 Weixin NetType/WIFI Language/zh_CN ABI/arm64 MiniProgramEnv/android"
        
    def log(self, msg, level="info"):
        self.wechat_code_adapter.log(msg, level)

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
            url = f"http://{self.host}/api3/onecrm/mactivity/santa/core/showCActivityPop"
            payload = {"appid":"wx532ecb3bdaaf92f9","basicInfo":{"vid":6013753979957,"vidType":2,"bosId":4020112618957,"productId":1,"productInstanceId":3171023957,"productVersionId":"30044","merchantId":2000020692957,"tcode":"weimob","cid":176205957},"extendInfo":{"wxTemplateId":7916,"analysis":[],"bosTemplateId":1000001984,"childTemplateIds":[{"customId":90004,"version":"crm@0.1.63"},{"customId":90002,"version":"ec@68.1"},{"customId":90006,"version":"hudong@0.0.229"},{"customId":90008,"version":"cms@0.0.504"}],"quickdeliver":{"enable":"false"},"youshu":{"enable":"false"},"source":1,"channelsource":5,"refer":"cms-index","mpScene":1145},"queryParameter":"null","i18n":{"language":"zh","timezone":"8"},"pid":"4020112618957","storeId":"0","targetBasicInfo":{"productInstanceId":3168798957}}
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
            url = f"https://{self.host}/fe/mapi/user/loginX"
            payload = {"appid":self.wechat_code_adapter.wx_appid,"basicInfo":{"bosId":"4020112618957","cid":"176205957","tcode":"weimob","vid":"6013753979957"},"env":"production","extendInfo":{"source":1},"is_pre_fetch_open":"true","parentVid":0,"pid":"4020112618957","storeId":"0","code":code,"queryAuthConfig":"true"}
            response = session.post(url, json=payload, timeout=5)
            response_json = response.json()
            if int(response_json['errcode']) == 0:
                self.log(f"[登录] 成功")
                token = response_json['data']['token']
                session.headers["x-wx-token"] = token
                return True
            else:
                self.log(f"[登录] 发生错误: {response_json['message']}", level="error")
                return False
        except requests.RequestException as e:
            self.log(f"[登录] 发生网络错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        except Exception as e:
            self.log(f"[登录] 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def get_sign_info(self, session):
        """
        获取签到信息
        :param session: session
        :return: 签到信息
        """
        try:
            url = f"https://{self.host}/api3/onecrm/mactivity/sign/misc/sign/activity/c/signMainInfo"
            payload = {"appid":"wx532ecb3bdaaf92f9","basicInfo":{"vid":6013753979957,"vidType":2,"bosId":4020112618957,"productId":146,"productInstanceId":3168798957,"productVersionId":"12017","merchantId":2000020692957,"tcode":"weimob","cid":176205957},"extendInfo":{"wxTemplateId":7916,"analysis":[],"bosTemplateId":1000001984,"childTemplateIds":[{"customId":90004,"version":"crm@0.1.63"},{"customId":90002,"version":"ec@68.1"},{"customId":90006,"version":"hudong@0.0.229"},{"customId":90008,"version":"cms@0.0.504"}],"quickdeliver":{"enable":"false"},"youshu":{"enable":"false"},"source":1,"channelsource":5,"refer":"onecrm-signgift","mpScene":1145},"queryParameter":"null","i18n":{"language":"zh","timezone":"8"},"pid":"4020112618957","storeId":"0","customInfo":{"source":0,"wid":3118552467}}
            response = session.post(url, json=payload)
            response_json = response.json()
            if int(response_json['errcode']) == 0:
                return response_json['data']['hasSign']
            else:
                self.log(f"[获取签到信息] 发生错误: {response_json['errmsg']}", level="error")
                return False
        except Exception as e:
            self.log(f"[获取签到信息] 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False

    def sign_in(self, session):
        """
        签到
        :param session: session
        :return: 签到结果
        """
        try:
            url = f"https://{self.host}/api3/onecrm/mactivity/sign/misc/sign/activity/core/c/sign"
            payload = {"appid":"wx532ecb3bdaaf92f9","basicInfo":{"vid":6013753979957,"vidType":2,"bosId":4020112618957,"productId":146,"productInstanceId":3168798957,"productVersionId":"12017","merchantId":2000020692957,"tcode":"weimob","cid":176205957},"extendInfo":{"wxTemplateId":7916,"analysis":[],"bosTemplateId":1000001984,"childTemplateIds":[{"customId":90004,"version":"crm@0.1.63"},{"customId":90002,"version":"ec@68.1"},{"customId":90006,"version":"hudong@0.0.229"},{"customId":90008,"version":"cms@0.0.504"}],"quickdeliver":{"enable":"false"},"youshu":{"enable":"false"},"source":1,"channelsource":5,"refer":"onecrm-signgift","mpScene":1106},"queryParameter":"null","i18n":{"language":"zh","timezone":"8"},"pid":"4020112618957","storeId":"0","customInfo":{"source":0,"wid":3140960455}}
            response = session.post(url, json=payload)
            response_json = response.json()
            if int(response_json['errcode']) == 0:
                self.log(f"[签到] {response_json['errmsg']} 获得: {response_json['data']['fixedReward']['points']}积分 额外获得:{response_json['data']['extraReward']['points']}积分")
                return True
            else:
                self.log(f"[签到] {response_json['errmsg']}", level="warning")
                return False
        except Exception as e:
            self.log(f"[签到] 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def get_activity_info(self, session, pageId="13906063"):
        """
        获取活动信息
        :param session: session
        :param pageId: 页面id
        :return: 活动信息
        """
        try:
            url = f"https://{self.host}/api3/mp-decoration/web/page/queryPageInfo"
            paylaod = {"appid":"wx532ecb3bdaaf92f9","basicInfo":{"vid":6013753979957,"vidType":2,"bosId":4020112618957,"productId":1,"productInstanceId":3171023957,"productVersionId":"30044","merchantId":2000020692957,"tcode":"weimob","cid":176205957},"extendInfo":{"wxTemplateId":7916,"analysis":[],"bosTemplateId":1000001984,"childTemplateIds":[{"customId":90004,"version":"crm@0.1.63"},{"customId":90002,"version":"ec@68.1"},{"customId":90006,"version":"hudong@0.0.229"},{"customId":90008,"version":"cms@0.0.504"}],"quickdeliver":{"enable":"false"},"youshu":{"enable":"false"},"source":1,"channelsource":5,"refer":"cms-design","mpScene":1145},"queryParameter":"null","i18n":{"language":"zh","timezone":"8"},"pid":"4020112618957","storeId":"0","bosId":4020112618957,"requestType":1,"pageSize":10,"pageNum":1,"exParams":{"pageId":pageId},"jsonSwitch":"true","pageId":pageId,"$level":1}
            response = session.post(url, json=paylaod)
            response_json = response.json()
            if int(response_json['errcode']) == 0:
                return response_json['data']["pageModuleInfoList"]
            else:
                self.log(f"[获取活动信息] 发生错误: {response_json['errmsg']}", level="error")
                return False
        except Exception as e:
            self.log(f"[获取活动信息] 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def get_miniurl(self, activity_info):
        for tmp_activity in activity_info:
            module_json = tmp_activity.get("moduleJSON", {})
            content = module_json.get("content", {})
            items = content.get("items", [])
            for item in items:
                hot_zone_list = item.get("hotZoneList", [])
                for hot_zone in hot_zone_list:
                    link = hot_zone.get("link", {})
                    mini_url = link.get("miniUrl", "")
                    if "tmpKey" in mini_url:
                        return mini_url
        return False
    
    def check_activity(self, activity_info):
        """
        检查活动
        :param activity_info: 活动信息
        :return: 活动信息
        """
        activity_params = []
        for tmp_activity in activity_info:
            module_json = tmp_activity.get("moduleJSON", {})
            content = module_json.get("content", {})
            items = content.get("items", [])
            for item in items:
                # 统一处理 item 和 hotZone
                for link_obj in [item.get("link", {})] + [hz.get("link", {}) for hz in item.get("hotZoneList", [])]:
                    mini_url = link_obj.get("miniUrl", "")
                    if mini_url and "?" in mini_url:
                        url = mini_url.split('?', 1)[1]
                        params = url.split("&")
                        activity_param = {}
                        for param in params:
                            if "=" in param:
                                key, value = param.split("=", 1)
                                activity_param[key] = value
                        # activity_name 兼容 item 和 hotZone
                        activity_param['activity_name'] = link_obj.get('linkName', '')
                        activity_params.append(activity_param)
        # 去重
        seen_actid = set()
        result = []
        for param in activity_params:
            actid = param.get("actId")
            if actid:
                if actid in seen_actid:
                    continue
                seen_actid.add(actid)
            result.append(param)
        return result
        
        
    def get_lottery_num(self, session, productInstanceId, actId):
        """
        查询抽奖次数
        :param session: session
        :param productInstanceId: 实例id
        :param actId: 活动id
        :return: 抽奖次数
        """
        try:
            url = f"https://{self.host}/api3/orchestration/mobile/prize/getRemainingAssets"
            payload = {"appid":"wx532ecb3bdaaf92f9","basicInfo":{"vid":6013753979957,"vidType":2,"bosId":4020112618957,"productId":226,"productInstanceId":productInstanceId,"productVersionId":"12008","merchantId":2000020692957,"tcode":"weimob","cid":176205957},"extendInfo":{"wxTemplateId":7526,"childTemplateIds":[{"customId":90004,"version":"crm@0.1.11"},{"customId":90002,"version":"ec@42.3"},{"customId":90006,"version":"hudong@0.0.201"},{"customId":90008,"version":"cms@0.0.419"}],"analysis":[],"quickdeliver":{"enable":"false"},"bosTemplateId":1000001420,"youshu":{"enable":"false"},"source":1,"channelsource":5,"refer":"hd-lego-index","mpScene":1089},"queryParameter":{"tracePromotionId":"100039234","tracepromotionid":"100039234"},"i18n":{"language":"zh","timezone":"8"},"pid":"4020112618957","storeId":"0","_transformBasicInfo":"true","_requrl":"/orchestration/mobile/prize/getRemainingAssets","templateId":748,"templateKey":"twistEgg","activityId":actId,"bussinessType":1,"channel":1,"channelType":1,"source":1,"_version":"2.5.4","activityIdentity":"20","assetTypes":["chance"],"openId":"oBk224m4im1J9PnLUe8AMagujqgM","wid":11068728376,"appId":"wx532ecb3bdaaf92f9","playSourceCode":"lcode","tracePromotionId":"100039234","tracepromotionid":"100039234","vid":6013753979957,"vidType":2,"bosId":4020112618957,"productId":226,"productInstanceId":productInstanceId,"productVersionId":"12008","merchantId":2000020692957,"tcode":"weimob","cid":176205957,"vidTypes":[2],"openid":"oBk224m4im1J9PnLUe8AMagujqgM"}
            response = session.post(url, json=payload)
            response_json = response.json()
            if int(response_json['errcode']) == 0:
                return response_json['data']['assets']['chance']['assetNum']
            else:
                self.log(f"[查询抽奖次数] {response_json['errmsg']}", level="warning")
                return False
        except Exception as e:
            self.log(f"[查询抽奖次数] 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def lottery(self, session, productInstanceId, actId):
        """
        抽奖
        :param session: session
        :param productInstanceId: 实例id
        :param actId: 活动id
        :return: 抽奖结果
        """
        try:
            url = f"https://{self.host}/api3/orchestration/mobile/activity/draw/play"
            payload = {"appid":"wx532ecb3bdaaf92f9","basicInfo":{"vid":6013753979957,"vidType":2,"bosId":4020112618957,"productId":226,"productInstanceId":productInstanceId,"productVersionId":"12008","merchantId":2000020692957,"tcode":"weimob","cid":176205957},"extendInfo":{"wxTemplateId":7526,"childTemplateIds":[{"customId":90004,"version":"crm@0.1.11"},{"customId":90002,"version":"ec@42.3"},{"customId":90006,"version":"hudong@0.0.201"},{"customId":90008,"version":"cms@0.0.419"}],"analysis":[],"quickdeliver":{"enable":"false"},"bosTemplateId":1000001420,"youshu":{"enable":"false"},"source":1,"channelsource":5,"refer":"hd-lego-index","mpScene":1089},"queryParameter":{"tracePromotionId":"100039234","tracepromotionid":"100039234"},"i18n":{"language":"zh","timezone":"8"},"pid":"4020112618957","storeId":"0","_transformBasicInfo":"true","_requrl":"/orchestration/mobile/prize/getRemainingAssets","templateId":748,"templateKey":"twistEgg","activityId":actId,"bussinessType":1,"channel":1,"channelType":1,"source":1,"_version":"2.5.4","activityIdentity":"20","assetTypes":["chance"],"openId":"oBk224m4im1J9PnLUe8AMagujqgM","wid":11068728376,"appId":"wx532ecb3bdaaf92f9","playSourceCode":"lcode","tracePromotionId":"100039234","tracepromotionid":"100039234","vid":6013753979957,"vidType":2,"bosId":4020112618957,"productId":226,"productInstanceId":productInstanceId,"productVersionId":"12008","merchantId":2000020692957,"tcode":"weimob","cid":176205957,"vidTypes":[2],"openid":"oBk224m4im1J9PnLUe8AMagujqgM"}
            response = session.post(url, json=payload)
            response_json = response.json()
            if int(response_json['errcode']) == 0:
                prize_name = response_json['data']['prizes'][0]['name']
                if prize_name:
                    self.log(f"[抽奖] 获得:{prize_name}")
                else:
                    self.log(f"[抽奖] 未中奖")
                return True
            elif int(response_json['errcode']) == 101100003:
                return False
            else:
                self.log(f"[抽奖] {response_json['errmsg']}", level="warning")
                return False
        except Exception as e:
            self.log(f"[抽奖] 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False
        
    def get_points(self, session):
        """
        查询积分
        :param session: session
        :return: 积分
        """
        try:
            url = f"https://{self.host}/api3/onecrm/point/myPoint/getSimpleAccountInfo"
            payload = {"appid":"wx532ecb3bdaaf92f9","basicInfo":{"vid":6013753979957,"vidType":2,"bosId":4020112618957,"productId":1,"productInstanceId":3171023957,"productVersionId":"30044","merchantId":2000020692957,"tcode":"weimob","cid":176205957},"extendInfo":{"wxTemplateId":7916,"analysis":[],"bosTemplateId":1000001984,"childTemplateIds":[{"customId":90004,"version":"crm@0.1.63"},{"customId":90002,"version":"ec@68.1"},{"customId":90006,"version":"hudong@0.0.229"},{"customId":90008,"version":"cms@0.0.504"}],"quickdeliver":{"enable":"false"},"youshu":{"enable":"false"},"source":1,"channelsource":5,"refer":"cms-usercenter","mpScene":1145},"queryParameter":"null","i18n":{"language":"zh","timezone":"8"},"pid":"4020112618957","storeId":"0","targetBasicInfo":{"productInstanceId":3168798957},"request":{}}
            response = session.post(url, json=payload)
            response_json = response.json()
            if int(response_json['errcode']) == 0:
                self.log(f"[积分] {response_json['data']['availablePoint']}")
                return response_json['data']['availablePoint']
            else:
                self.log(f"[积分] {response_json['errmsg']}", level="warning")
                return False
        except Exception as e:
            self.log(f"[积分] 发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            return False

    def run(self):
        """
        运行任务
        """
        try:
            self.log(f"【{self.script_name}】开始执行任务")
            
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
                    
                session.headers["User-Agent"] = self.user_agent

                # 执行微信授权
                code = self.wechat_code_adapter.get_code(wx_id)
                if code:
                    if self.wxlogin(session, code):
                        if not self.get_sign_info(session):
                            # 签到
                            self.sign_in(session)
                            time.sleep(random.randint(1, 3))
                        else:
                            self.log(f"[签到] 今日已签到", level="warning")
                        # 抽奖活动
                        activity_info = self.get_activity_info(session)
                        activity_params = self.check_activity(activity_info)
                        for activity_param in activity_params:
                            if "tmpKey" in activity_param:
                                self.log(f"[活动] {activity_param['activity_name']}")
                                lottery_num = self.get_lottery_num(session, activity_param['productInstanceId'], activity_param['actId'])
                                for i in range(lottery_num):
                                    time.sleep(random.randint(3, 5))
                                    self.lottery(session, activity_param['productInstanceId'], activity_param['actId'])
                            elif "pageid" in activity_param:
                                # 二次查询，防止页面内有抽奖活动
                                activity_info = self.get_activity_info(session, activity_param['pageid'])
                                activity_params = self.check_activity(activity_info)
                                for activity_param in activity_params:
                                    if "tmpKey" in activity_param:
                                        lottery_num = self.get_lottery_num(session, activity_param['productInstanceId'], activity_param['actId'])
                                        for i in range(lottery_num):
                                            if not self.lottery(session, activity_param['productInstanceId'], activity_param['actId']):
                                                break
                        # 查询积分
                        self.get_points(session)
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
                header = "作者：临渊\n\n"
                content = header + "\n" +"\n".join(self.wechat_code_adapter.log_msgs)
                notify.send(title, content)


if __name__ == "__main__":
    auto_task = AutoTask("统一梦时代")
    auto_task.run() 