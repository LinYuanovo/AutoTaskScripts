"""
 作者:  临渊
 日期:  2025/6/27
 APP:   次元姬小说
 功能:  签到、阅读、领取奖励 （阅读需要模拟真实时间，所以脚本会运行比较长时间，预计一个小时）
 变量:  cyj_account = 'deviceno&token' （api.hwnovel.com下请求的deviceno和token，用&分割）
 定时:   一天一到两次
 cron:  10 8,15 * * *
 更新日志：
 2025/6/27 V1.0 初始化脚本
 2025/6/28 V1.1 优化阅读逻辑 增加阅读时间判断，如果已阅读时间超过50分钟，则跳过模拟阅读
 2025/6/28 V1.2 增加自动订阅 需要填写bookId和从第多少章开始订阅
"""

MULTI_ACCOUNT_SPLIT = ["\n", "@"] # 多账户分隔符列表
NOTIFY = False # 是否推送日志，默认不推送，True则推送
AUTO_ORDER_BOOK_ID = "" # 自动订阅的小说bookId，填了则自动订阅，否则不订阅，只有第一个号会进行订阅
AUTO_ORDER_BOOK_CHAPTER = 1 # 从第多少章开始自动订阅，默认使用所有代币往后进行订阅

import os
import random
import time
import json
import logging
import traceback
import requests
import base64
import hashlib
import threading
import uuid as uuidlib
from Crypto.Cipher import DES
from Crypto.Util.Padding import pad

class AutoTask:
    def __init__(self, script_name):
        self.script_name = script_name
        self.log_msgs = []
        self.local = threading.local()
        self.base_url = "https://api.hwnovel.com/api/ciyuanji/client/"
        self.setup_logging()

    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s\t- %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            handlers=[logging.StreamHandler()]
        )

    def log(self, msg, level="info", push=True):
        account_prefix = getattr(self.local, "account_prefix", "")
        msg = f"{account_prefix}{msg}"
        if level == "info":
            logging.info(msg)
        elif level == "error":
            logging.error(msg)
        elif level == "warning":
            logging.warning(msg)
        if push:
            self.log_msgs.append(msg)

    def check_env(self):
        """
        检查环境变量
        :return: 环境变量字符串
        """
        try:
            # 从环境变量获取cookie
            cyj_account = os.getenv(f"cyj_account")
            if not cyj_account:
                self.log("[检查环境变量]没有找到环境变量cyj_account，请检查环境变量", level="error")
                return None

            # 自动检测分隔符
            split_char = None
            for sep in MULTI_ACCOUNT_SPLIT:
                if sep in cyj_account:
                    split_char = sep
                    break
            if not split_char:
                # 如果都没有分隔符，默认当作单账号
                cyj_accounts = [cyj_account]
            else:
                cyj_accounts = cyj_account.split(split_char)

            for cyj_account in cyj_accounts:
                if "=" in cyj_account:
                    cyj_account = cyj_account.split("=")[1]
                    deviceno, token = cyj_account.split("&")
                    yield deviceno, token
                else:
                    deviceno, token = cyj_account.split("&")
                    yield deviceno, token
        except Exception as e:
            self.log(f"[检查环境变量]发生错误: {str(e)}\n{traceback.format_exc()}", level="error")
            raise

    def encrypt(self, data):
        key = b"ZUreQN0E"
        cipher = DES.new(key, DES.MODE_ECB)
        padded_data = pad(data.encode("utf-8"), DES.block_size)
        encrypted = cipher.encrypt(padded_data)
        return base64.b64encode(encrypted).decode("utf-8")

    def base64_encode(self, s):
        return base64.b64encode(s.encode("utf-8")).decode("utf-8")

    def digest(self, s, method="md5"):
        if method == "md5":
            return hashlib.md5(s.encode("utf-8")).hexdigest()
        raise NotImplementedError("只支持md5")

    def uuid(self):
        return str(uuidlib.uuid4())

    def request(self, method, url, headers, data=None):
        timestamp = int(time.time() * 1000)
        request_id = self.uuid()
        param = self.encrypt(json.dumps({**(data or {}), "timestamp": timestamp}))
        sign_str = f"param={param}&requestId={request_id}&timestamp={timestamp}&key=NpkTYvpvhJjEog8Y051gQDHmReY54z5t3F0zSd9QEFuxWGqfC8g8Y4GPuabq0KPdxArlji4dSnnHCARHnkqYBLu7iIw55ibTo18"
        sign = self.digest(self.base64_encode(sign_str), "md5").upper()
        try:
            if method == "GET":
                resp = requests.get(
                    self.base_url + url,
                    params={
                        "param": param,
                        "requestId": request_id,
                        "sign": sign,
                        "timestamp": timestamp
                    },
                    headers=headers,
                    timeout=10
                )
            else:
                resp = requests.post(
                    self.base_url + url,
                    json={
                        "param": param,
                        "requestId": request_id,
                        "sign": sign,
                        "timestamp": timestamp
                    },
                    headers=headers,
                    timeout=10
                )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self.log(f"请求异常: {url} {str(e)}\n{traceback.format_exc()}", level="error")
            return None

    def signin(self, headers):
        """
        每日签到
        """
        response = self.request("POST", "sign/sign", headers, {})
        if response["code"] == "200":
            self.log(f"签到: {response['msg']}")
            return response
        else:
            self.log(f"签到: {response['msg']}", level="warning")
            return False
        
    def get_task_list(self, headers):
        """
        获取任务列表
        :return: 任务列表
        """
        response = self.request("GET", "task/getTaskList", headers, {})
        if response["code"] == "200":
            task_list = response["data"]["daliyTask"]
            return task_list
        else:
            self.log(f"获取任务列表: {response['msg']}", level="warning")
            return False
    
    def read_start(self, headers):
        """
        开始阅读
        """
        data = {
            "startChapter": "3632603",
            "startChapterName": "第1章 邪恶app",
            "bookName": "人渣男主，为所欲为",
            "bookId": "14827",
            "timestamp": int(time.time() * 1000)
        }
        response = self.request("POST", "read/start", headers, data)
        if response["code"] == "200":
            readId = response["data"]["readId"]
            # self.log(f"开始阅读: readId={readId}", level="info")
            return readId
        else:
            self.log(f"开始阅读: {response['msg']}", level="error")
            return False
        
    def read_start_chapter(self, headers, readId):
        """
        阅读章节
        :param readId: 阅读ID
        """
        data = {
            "isBuy": "0",
            "isFee": "0",
            "readId": readId,
            "chapterId": "3632603",
            "chapterName": "第1章 邪恶app",
            "bookName": "人渣男主，为所欲为",
            "bookId": "14827",
            "timestamp": int(time.time() * 1000)
        }
        response = self.request("POST", "read/startChapter", headers, data)
        if response["code"] == "200":
            readChapterId = response["data"]["readChapterId"]
            # self.log(f"阅读章节: readChapterId={readChapterId}", level="info")
            return readChapterId
        else:
            self.log(f"阅读章节: {response['msg']}", level="error")
            return False
        
    def read_end(self, headers, readId):
        """
        结束阅读
        :param readId: 阅读ID
        """
        data = {
            "endChapterName": "第1章 邪恶app",
            "readId": readId,
            "chapterCount": "1",
            "endChapter": "3632603",
            "bookId": "14827",
            "timestamp": int(time.time() * 1000)
        }
        response = self.request("POST", "read/end", headers, data)
        if response["code"] == "200":
            # self.log(f"结束阅读: {response['msg']}", level="info")
            return response
        else:
            self.log(f"结束阅读: {response['msg']}", level="error")
            return False
        
    def read_end_chapter(self, headers,readChapterId):
        """
        结束阅读章节
        :param readChapterId: 阅读章节ID
        """
        data = {
            "isBuy": "0",
            "isFee": "0",
            "isUserMember": "0",
            "isBookMember": "0",
            "readChapterId": readChapterId,
            "timestamp": int(time.time() * 1000)
        }
        response = self.request("POST", "read/endChapter", headers, data)
        if response["code"] == "200":
            # self.log(f"结束阅读章节: {response['msg']}", level="info")
            return response
        else:
            self.log(f"结束阅读章节: {response['msg']}", level="error")
            return False
        
    def receive_task_reward(self, headers, task_id, reward_id):
        """
        领取任务奖励
        :param task_id: 任务ID
        :param reward_id: 奖励ID
        """
        data = {
            "taskId": task_id,
            "rewardId": reward_id
        }
        response = self.request("POST", "task/receiveTaskReward", headers, data)
        if response["code"] == "200":
            self.log(f"领取奖励: {response['msg']}", push=False)
            return response
        else:
            self.log(f"领取奖励: {response['msg']}", level="error")
            return False
        
    def get_user_info(self, headers):
        """
        获取用户信息
        """
        response = self.request("GET", "account/getAccountByUser", headers, {})
        if response["code"] == "200":
            nikeName = response["data"]["accountInfo"]["nickName"]
            # 代币
            couponBalance = float(response["data"]["accountInfo"]["couponBalance"])
            # 推荐票
            dayCount = int(response["data"]["accountInfo"]["dayCount"])
            self.log(f"{nikeName} 代币:{couponBalance} 推荐票:{dayCount}")
            return couponBalance
        else:
            self.log(f"获取用户信息: {response['msg']}", level="error")
            return False 

    def get_book_chapter_info(self, headers, bookId):
        """
        获取小说章节信息
        :param bookId: 小说ID
        :return: 小说名称, 章节列表
        """
        data = {
            "sortType": "1",
            "pageNo": "1",
            "pageSize": "9999",
            "bookId": bookId,
            "timestamp": int(time.time() * 1000)
        }
        response = self.request("GET", "chapter/getChapterListByBookId", headers, data)
        if response["code"] == "200":
            book_name = response["data"]["bookChapter"]["bookName"]
            chapter_list = response["data"]["bookChapter"]["chapterList"]
            return book_name, chapter_list
        else:
            self.log(f"获取小说章节信息: {response['msg']}", level="error")
            return False

    def order_book_chapter(self, headers, bookId, chapterId):
        """
        订阅章节
        :param bookId: 小说ID
        :param chapterId: 章节ID
        """
        data = {
            "buyCount": "1",
            "productId": chapterId,
            "viewType": "2",
            "consumeType": "1",
            "bookId": bookId,
            "timestamp": int(time.time() * 1000)
        }
        response = self.request("POST", "order/consume", headers, data)
        if response["code"] == "200":
            return True
        else:
            self.log(f"订阅章节: {response['msg']}", level="error")
            return False

    def run_for_account(self, index, token, deviceno):
        self.local.account_prefix = f"[账号{index}] "
        # 防止串号
        headers = {
            "channel": "25",
            "deviceno": deviceno,
            "platform": "1",
            "imei": "",
            "targetmodel": "M2012K11AC",
            "oaid": "",
            "version": "3.4.3",
            "token": token,
            "user-agent": "Mozilla/5.0 (Linux; Android 11; Pixel 4 XL Build/RP1A.200720.009; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/92.0.4515.115 Mobile Safari/537.36"
        }
        # 签到
        self.signin(headers)
        # 获取任务列表
        task_list = self.get_task_list(headers)
        reader_time = 0
        for task in task_list:
            if task['actionName'] == "阅读" and task['taskState'] != "0":
                reader_time = int(task['rewardList'][0]['actionRequire'])
        if reader_time >= 0:
            need_read_time = 50 - reader_time
            self.log(f"还需要阅读{need_read_time}分钟")
            if need_read_time > 0:
                # 5分钟一次，太长时间会失效
                for i in range(need_read_time // 5):
                    # 开始阅读
                    readId = self.read_start(headers)
                    time.sleep(5)
                    if readId:
                        # 阅读章节
                        readChapterId = self.read_start_chapter(headers, readId)
                        self.log(f"模拟第{i+1}次阅读中，请勿停止运行脚本", push=False)
                        time.sleep(random.randint(300, 320))
                        if readChapterId:
                            # 结束阅读章节
                            self.read_end_chapter(headers, readChapterId)
                            time.sleep(5)
                    # 结束阅读
                    self.read_end(headers, readId)
        else:
            self.log(f"已阅读{reader_time}分钟，跳过模拟阅读")
        # 获取任务列表
        task_list = self.get_task_list(headers)
        if task_list:
            # 领取奖励
            for task in task_list:
                if task["taskState"] == "1":
                    self.receive_task_reward(headers, task["taskId"], task["rewardId"])
        # 再次获取任务列表
        task_list = self.get_task_list(headers)
        if task_list:
            for task in task_list:
                taskname = task["taskName"]
                if "阅读" in taskname:
                    status = "已完成" if task["taskState"] == "2" else "未完成"
                    self.log(f"任务-{taskname}-{status}", level="info")
        # 获取用户信息
        coupon_balance = self.get_user_info(headers)
        # 自动订阅小说
        if AUTO_ORDER_BOOK_ID and index == 1:
            book_name, chapter_list = self.get_book_chapter_info(headers, AUTO_ORDER_BOOK_ID)
            if chapter_list:
                for index, chapter in enumerate(chapter_list, 1):
                    # 大于等于指定章节开始订阅
                    if index >= AUTO_ORDER_BOOK_CHAPTER and int(chapter['isFee']) == 1 and int(chapter['isBuy']) == 0:
                        if coupon_balance >= float(chapter['price']):
                            # 订阅
                            if self.order_book_chapter(headers, AUTO_ORDER_BOOK_ID, chapter["chapterId"]):
                                self.log(f"订阅 [{book_name}] - {chapter['chapterName']} 成功")
                                coupon_balance -= float(chapter['price'])
                        else:
                            break

    def run(self):
        self.log(f"【{self.script_name}】开始执行任务")

        threads = []
        for index, (deviceno, token) in enumerate(self.check_env(), 1):
            t = threading.Thread(
                target=self.run_for_account,
                args=(index, token, deviceno)
            )
            t.start()
            threads.append(t)

        for t in threads:
            t.join()
        
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
            content = header + "\n" +"\n".join(self.log_msgs)
            notify.send(title, content)

if __name__ == "__main__":
    auto_task = AutoTask("次元姬小说")
    auto_task.run()