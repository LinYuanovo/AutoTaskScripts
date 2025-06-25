"""
 作者： 临渊
 日期： 2025/6/18
 小程序：   银鱼质享
 功能： 看视频、提现
 变量： yyzx='authori-zation' （n05.sentezhenxuan.com域名下authori-zation） 多个账号用换行分割 
 定时： 一天一次
 cron： 10 10 * * *
 更新日志：
 2025/6/18：    初始化脚本
"""

import random
import requests
import os
import logging
import traceback
from datetime import datetime
import time

class AutoTask:
    def __init__(self, site_name):
        """
        初始化自动任务类
        :param site_name: 站点名称，用于日志显示
        """
        self.site_name = site_name
        self.host = "n05.sentezhenxuan.com"
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a13) XWEB/8555"
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
            cookie = os.getenv(f"yyzx")
            if not cookie:
                logging.warning(f"[检查环境变量]没有找到环境变量yyzx，退出")
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

    def get_video_list(self, host, cookie):
        """
        获取视频列表
        :param host: 域名
        :param cookie: cookie
        :return: 视频列表
        """
        try:
            url = f"https://{host}/api/video/list?page=1&limit=10&status=1&source=0&isXn=1"
            headers = {
                'authori-zation': cookie,
                'User-Agent': self.user_agent
            }
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            response_json = response.json()
            video_list = response_json['data']
            return video_list
        except Exception as e:
            logging.error(f"[获取视频列表]发生错误: {str(e)}\n{traceback.format_exc()}")
            return []
    

    def watch_video(self, host, cookie, video_id, watch_time):
        """
        执行看视频
        :param host: 域名
        :param cookie: cookie
        :param video_id: 视频id
        :param watch_time: 观看时间
        """
        try:
            url = f"https://{host}/api/video/videoJob"
            headers = {
                'authori-zation': cookie,
                'User-Agent': self.user_agent
            }
            
            # 获取当前时间戳（毫秒）
            current_timestamp = int(datetime.now().timestamp() * 1000)
            
            payload = {
                "vid": video_id,
                "startTime": current_timestamp,
                "endTime": current_timestamp + watch_time + 1000,
                "baseVersion": "3.3.5",
                "playMode": 0
            }
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            # 处理响应
            response_json = response.json()
            if response_json.get('status') == 200:
                logging.info(f"[看视频]成功，视频ID: {video_id}")
                return True
            else:
                logging.warning(f"[看视频]失败: {response_json['msg']}")
                return False
                
        except requests.RequestException as e:
            logging.error(f"[看视频]发生网络错误: {str(e)}\n{traceback.format_exc()}")
            return False
        except Exception as e:
            logging.error(f"[看视频]发生未知错误: {str(e)}\n{traceback.format_exc()}")
            return False
        
    def update_withdraw_info(self, host, cookie):
        """
        更新提现信息
        :param host: 域名
        :param cookie: cookie
        :return: 当前余额
        """
        try:
            url = f"https://{host}/api/updateTxInfo"
            headers = {
                'authori-zation': cookie,
                'User-Agent': self.user_agent,
                'content-type': 'application/json'
            }
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            response_json = response.json()
            if response_json.get('status') == 200:
                logging.info(f"[更新提现信息]当前余额：{response_json['data']['now_money']}元")
                balance = float(response_json['data']['now_money'])
                return balance
            else:
                logging.warning(f"[更新提现信息]失败: {response_json['msg']}")
                return 0
        except Exception as e:
            logging.error(f"[更新提现信息]发生错误: {str(e)}\n{traceback.format_exc()}")
            return 0
        
        
    def withdraw(self, host, cookie):
        """
        执行提现
        :param host: 域名
        :param cookie: cookie
        """
        try:
            url = f"https://{host}/api/userTx"
            headers = {
                'Host': host,
                'Connection': 'keep-alive',
                'charset': 'utf-8',
                'form-type': 'routine-zhixiang',
                'referer': 'https://servicewechat.com/wx5b82dfe3747e533f/5/page-frame.html',
                'authori-zation': cookie,
                'User-Agent': self.user_agent,
                'content-type': 'application/json'
            }
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            response_json = response.json()
            if response_json.get('status') == 200:
                logging.info(f"[提现]{response_json['msg']}")
                return True
            else:
                logging.warning(f"[提现]失败: {response_json['msg']}")
                return False
        except Exception as e:
            logging.error(f"[提现]发生错误: {str(e)}\n{traceback.format_exc()}")
            return False

    def run(self):
        """
        运行任务
        """
        try:
            logging.info(f"【{self.site_name}】开始执行任务")
            
            # 1. 检查cookie
            for index, cookie in enumerate(self.check_env(), 1):
                logging.info("")
                logging.info(f"------ 【账号{index}】开始执行任务 ------")
                
                # 2. 获取视频列表
                video_list = self.get_video_list(self.host, cookie)
                if not video_list:
                    logging.warning(f"[获取视频列表]失败，跳过当前账号看视频任务")
                
                # 3. 执行看视频任务
                for video in video_list:
                    video_id = video['id']
                    if video_id:
                        watch_time = video['wait_time']
                        self.watch_video(self.host, cookie, video_id, watch_time)
                        time.sleep(random.randint(10, 15))
                # 4. 提现
                user_balance = self.update_withdraw_info(self.host, cookie)
                if user_balance >= 0.2:
                    self.withdraw(self.host, cookie)
                else:
                    logging.warning(f"[提现]当前余额不足0.2元，跳过提现")

                logging.info(f"------ 【账号{index}】执行任务完成 ------")
        except Exception as e:
            logging.error(f"【{self.site_name}】执行过程中发生错误: {str(e)}\n{traceback.format_exc()}")


if __name__ == "__main__":
    auto_task = AutoTask("银鱼质享")
    auto_task.run() 