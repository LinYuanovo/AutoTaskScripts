"""
作者: 临渊
日期: 2025/6/8
name: 嘤嘤怪之家
入口: 网站 (https://yyg.boats/)
功能: 登录、签到、评论（每日上限30积分）
变量: yyg='账号&密码'  多个账号用换行分割
    DDDD_OCR_URL (dddd_ocr地址)
定时: 一天两次
cron: 10 9,10 * * *
------------更新日志------------
2025/6/8    V1.0    初始化，完成签到功能
2025/6/10   V1.1    添加评论功能
2025/6/11   V1.2    优化代码结构，使用session管理cookie，添加查询积分功能（不一定成功）
2025/7/23   V1.3    更新域名
2025/7/28   V1.4    修改头部注释，以便拉库
"""

import requests
import os
import re
import urllib.parse
import time
import random
import logging
import traceback
from datetime import datetime
from bs4 import BeautifulSoup

DDDD_OCR_URL = os.getenv("DDDD_OCR_URL") or "" # dddd_ocr地址

class AutoTask:
    def __init__(self, site_name):
        """
        初始化自动任务类
        :param site_name: 站点名称，用于日志显示
        """
        self.site_name = site_name
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

    def check_cookie(self):
        """
        检查cookie
        :return: 用户名和密码
        """
        try:
            # 从环境变量获取cookie
            cookie = os.getenv(f"yyg")
            if not cookie:
                logging.error(f"[检查cookie]没有找到环境变量yyg")
                return
            # 多个账号用换行分割
            cookies = cookie.split('\n')
            for cookie in cookies:
                # 解析cookie字符串，提取用户名和密码
                username, password = cookie.split('&')
                yield username, password
        except Exception as e:
            logging.error(f"[检查cookie]发生错误: {str(e)}\n{traceback.format_exc()}")
            raise

    def get_captcha_img(self, host, session, type):
        """
        获取验证码图片
        :param host: 域名
        :param session: 会话对象
        :param type: 验证码类型
        :return: 验证码base64
        """
        max_retries = 3  # 最大重试次数
        retry_count = 0

        while retry_count < max_retries:
            try:
                url = f"https://{host}/wp-content/themes/zibll/action/captcha.php?type=image&id={type}"
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36'
                }
                response = session.get(url, headers=headers).json()
                if 'img' in response:
                    return response['img']
                else:
                    retry_count += 1
                    logging.warning(f"[获取验证码]第{retry_count}次获取失败，正在重试...")
                    continue
            except Exception as e:
                retry_count += 1
                if retry_count >= max_retries:
                    logging.error(f"[获取验证码]重试次数已达上限")
                    return None
                continue

        return None

    def get_captcha_text(self, img):
        """
        获取验证码文字
        :param img: 验证码图片base64
        :return: 验证码
        """
        try:
            url = DDDD_OCR_URL
            payload = {
                'image': img
            }
            response = requests.post(url, data=payload).json()
            if response['code'] == 200:
                return response['data']
            else:
                logging.error(f"[获取验证码]发生错误: {response['message']}")
                return None
        except Exception as e:
            logging.error(f"[获取验证码]发生错误: {str(e)}\n{traceback.format_exc()}")
            return None

    def login_in(self, host, username, password, text, session):
        """
        登录
        :param host: 域名
        :param username: 用户名
        :param password: 密码
        :param text: 验证码
        :param session: 会话对象
        :return: 是否成功
        """
        max_retries = 3  # 最大重试次数
        retry_count = 0

        while retry_count < max_retries:
            try:
                url = f"https://{host}/wp-admin/admin-ajax.php"
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
                }
                payload = f"username={username}&password={password}&canvas_yz={text}&remember=forever&action=user_signin"
                response = session.post(url, headers=headers, data=payload)
                response_json = response.json()

                if response_json['error'] == 0:
                    logging.info(f"[登录]成功")
                    return True
                else:
                    logging.error(f"[登录]失败: {response_json['msg']}")
                    if "重新获取" in response_json['msg'] or "请输入图形验证码" in response_json['msg']:
                        retry_count += 1
                        if retry_count >= max_retries:
                            logging.error(f"[登录]验证码重试次数已达上限")
                            return False

                        img = self.get_captcha_img(host, session, "img_yz_signin")
                        while not img:
                            img = self.get_captcha_img(host, session, "img_yz_signin")
                        text = self.get_captcha_text(img)
                        if not text:
                            logging.error(f"[登录]获取验证码文字失败")
                            return False
                        continue
                    return False

            except requests.RequestException as e:
                logging.error(f"[登录]发生网络错误: {str(e)}\n{traceback.format_exc()}")
                return False
            except Exception as e:
                logging.error(f"[登录]发生未知错误: {str(e)}\n{traceback.format_exc()}")
                return False

        return False

    def sign_in(self, host, session):
        """
        执行签到
        :param host: 域名
        :param session: 会话对象
        :return: 是否签到成功
        """
        try:
            url = f"https://{host}/wp-admin/admin-ajax.php"
            headers = {
                'Host': host,
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36'
            }
            payload = "action=user_checkin"
            response = session.post(url, headers=headers, data=payload)
            response_json = response.json()
            # 处理响应
            logging.info(f"[签到]{response_json['msg']}")
            return response_json['msg']
        except requests.RequestException as e:
            logging.error(f"[签到]发生网络错误: {str(e)}\n{traceback.format_exc()}")
            return False
        except Exception as e:
            logging.error(f"[签到]发生未知错误: {str(e)}\n{traceback.format_exc()}")
            return False

    def get_post_id(self, host, session, retry_count=0):
        """
        获取帖子id
        :param host: 域名
        :param session: 会话对象
        :param retry_count: 重试次数
        :return: 帖子id列表
        """
        try:
            url = f"https://{host}/category/pcgame?orderby=modified" # 最新排列
            headers = {
                'Host': host,
                'Referer': f"https://{host}/category/pcgame",
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36'
            }
            response = session.get(url, headers=headers)
            soup = BeautifulSoup(response.text, 'html.parser')

            post_ids = []
            for i in range(3,7):
                # 找到所有posts元素
                links = soup.select(f'body > main > div > div > div:nth-child(2) > posts:nth-child({i}) > div.item-body.flex.xx.flex1.jsb > h2 > a')
                if links:  # 如果找到了链接
                    link = links[0]  # 获取第一个链接
                    # 提取帖子ID
                    if link.get('href'):
                        # 从URL中提取ID (例如从 https://yyg.boats/14819.html 提取 14819)
                        post_id = link['href'].split('/')[-1].replace('.html', '')
                        post_ids.append(post_id)

            # 如果没有获取到帖子ID且重试次数小于3次，则重试
            if not post_ids and retry_count < 3:
                logging.info(f"[获取帖子ID]未获取到帖子ID，第{retry_count + 1}次重试")
                time.sleep(random.randint(5, 10))
                return self.get_post_id(host, session, retry_count + 1)
            elif not post_ids and retry_count >= 3:
                post_ids = ['14818', '14817', '14816', '14815']
                logging.warning(f"[获取帖子ID]三次未获取到帖子ID，使用默认帖子ID: {post_ids}")

            logging.info(f"[获取帖子ID]成功获取到 {len(post_ids)} 个帖子ID: {post_ids}")
            return post_ids

        except requests.RequestException as e:
            logging.error(f"[获取帖子ID]发生网络错误: {str(e)}\n{traceback.format_exc()}")
            return []
        except Exception as e:
            logging.error(f"[获取帖子ID]发生未知错误: {str(e)}\n{traceback.format_exc()}")
            return []

    def submit_comment(self, host, session, captcha, post_id, retry_count=0):
        """
        提交评论
        :param host: 域名
        :param session: 会话对象
        :param captcha: 验证码
        :param post_id: 帖子ID
        :param retry_count: 重试次数
        """
        try:
            url = f"https://{host}/wp-admin/admin-ajax.php"
            headers = {
                'Host': host,
                'Referer': f"https://{host}/{post_id}.html",
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36'
            }
            payload = f"comment=%E6%84%9F%E8%B0%A2%E5%88%86%E4%BA%AB&canvas_yz={captcha}&comment_post_ID={post_id}&comment_parent=0&action=submit_comment"
            response = session.post(url, headers=headers, data=payload)
            response_json = response.json()
            logging.info(f"[评论帖子{post_id}]{response_json['msg']}")

            if "图形验证码错误" in response_json['msg']:
                if retry_count >= 3:
                    logging.warning(f"[评论{post_id}]验证码错误重试次数已达上限，跳过此评论")
                    return False

                logging.info(f"[评论帖子{post_id}]验证码错误，第{retry_count + 1}次重试")
                submit_comment_captcha = self.get_captcha_img(host, session, "submit_comment")
                while not submit_comment_captcha:
                    submit_comment_captcha = self.get_captcha_img(host, session, "submit_comment")
                submit_comment_text = self.get_captcha_text(submit_comment_captcha)
                if not submit_comment_text:
                    logging.error(f"[评论帖子{post_id}]获取验证码文字失败")
                    return False
                return self.submit_comment(host, session, submit_comment_text, post_id, retry_count + 1)

            return response_json['msg']
        except Exception as e:
            logging.error(f"[评论帖子{post_id}]发生未知错误: {str(e)}\n{traceback.format_exc()}")
            return False

    def get_user_balance(self, host, session):
        """
        获取用户积分
        :param host: 域名
        :param session: 会话对象
        :return: 用户积分
        """
        try:
            url = f"https://{host}/user/balance"
            headers = {
                'Host': host,
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36'
            }
            response = session.get(url, headers=headers)
            # 正则匹配积分记录里第一个，即 积分: xxx
            balance = re.search(r'积分: (\d+)', response.text)
            if balance:
                return balance.group(1)
            else:
                logging.error(f"[获取用户积分]未找到积分记录")
                return 0
        except Exception as e:
            logging.error(f"[获取用户积分]发生未知错误: {str(e)}\n{traceback.format_exc()}")
            return 0

    def do_task(self, host, session):
        """
        执行任务
        :param host: 域名
        :param session: 会话对象
        """
        # 执行签到
        self.sign_in(host, session)
        # 获取帖子id
        post_ids = self.get_post_id(host, session)
        # 获取评论验证码图片(四次)
        for post_id in post_ids:
            captcha = self.get_captcha_img(host, session, "submit_comment")
            while not captcha:
                captcha = self.get_captcha_img(host, session, "submit_comment")
            text = self.get_captcha_text(captcha)
            if not text:
                logging.error(f"[评论{post_id}]获取验证码文字失败")
                continue
            # 提交评论
            self.submit_comment(host, session, text, post_id)
            time.sleep(random.randint(16, 30))
        # 获取用户积分
        balance = self.get_user_balance(host, session)
        logging.info(f"[账号]当前积分: {balance}")

    def run(self):
        """
        运行任务
        """
        try:
            logging.info(f"【{self.site_name}】开始执行任务")
            host = "yyg.boats"

            for index, (username, password) in enumerate(self.check_cookie(), 1):
                logging.info("")
                logging.info(f"------【账号{index}】开始执行任务------")

                # 创建会话
                session = requests.Session()

                # 获取登录验证码图片
                login_in_img = self.get_captcha_img(host, session, "img_yz_signin")
                while not login_in_img:
                    login_in_img = self.get_captcha_img(host, session, "img_yz_signin")
                # 获取登录验证码文字
                login_in_text = self.get_captcha_text(login_in_img)
                if not login_in_text:
                    logging.error(f"[{self.site_name}]获取登录验证码文字失败")
                    continue

                # 登录
                if self.login_in(host, username, password, login_in_text, session):
                    # 执行任务
                    self.do_task(host, session)

                logging.info(f"------【账号{index}】执行任务完成------")
                logging.info("")

        except Exception as e:
            logging.error(f"【{self.site_name}】执行过程中发生错误: {str(e)}\n{traceback.format_exc()}")


if __name__ == "__main__":
    auto_task = AutoTask("嘤嘤怪之家")
    auto_task.run()
