# AutoTaskScripts
此项目为自用自动化（本地/青龙面板）任务脚本备份，用于自动签到或是完成一些任务

如果其中的一些脚本对你有帮助可以点个star支持一下

## 通用变量

|      通用变量      |                           变量说明                           |                           备注                            |
| :----------------: | :----------------------------------------------------------: | :-------------------------------------------------------: |
|    DDDD_OCR_URL    |      用于识别验证码，示例 http://xxx.xx.xx.xx:8000/ocr/      | [项目搭建地址](https://github.com/sml2h3/ddddocr-fastapi) |
|   PROXY_API_URL    |          代理api，返回一条txt文本内容为代理ip:端口           |    [示例注册地址](https://www.ipzan.com?pid=s20qm4fr8)    |
|     LY_NOTIFY      |       是否推送通知，填True则推送，不设置该变量则不推送       |                   可选，脚本默认不推送                    |
|  soy_codeurl_data  | 微信授权协议获取code的url，示例 http://xxxx/prod-api/wechat/api/getMiniProgramCode |                      code版脚本必须                       |
| soy_codetoken_data |   上述变量对应的鉴权token或ADMIN_KEY，如协议不需要没有为空   |                      code版脚本必须                       |
|   soy_wxid_data    | 微信授权获取code的wxid，示例 wxid_xxxxxxxxx522，通过wxid取出对应的code |                      code版脚本必须                       |

### 支持协议

- 养鸡场
  
  soy_codeurl_data: http://xxxx/prod-api/wechat/api/getMiniProgramCode
  
  soy_codetoken_data: **Authorization**
  
- [NoNull佬](https://github.com/wyourname/wool/blob/master/wechat/readme.md)

  soy_codeurl_data: http://xxxx/wx/app/code

- [WeChatPadPro](https://github.com/WeChatPadPro/WeChatPadPro)
  
  soy_codeurl_data: http://xxxx/admin/GetAllDevices
  
  soy_codetoken_data: **ADMIN_KEY**
  
- [iwechat](https://github.com/iwechatcom/iwechat) 应该支持，没有测试账号
  soy_codeurl_data: http://xxxx/admin/GetAuthKey
  
  soy_codetoken_data: **key**

通过api取对应wxid的code，如图

![取code](https://raw.githubusercontent.com/LinYuanovo/pic_bed/refs/heads/main/AutoTaskScripts/code.png)

## 支持网站

|               名称               | 是否有效 |  变量   |       变量说明        |                           特殊说明                           |
| :------------------------------: | :------: | :-----: | :-------------------: | :----------------------------------------------------------: |
| [司机社](https://sijishecn.cc/)  |    ✅️     | sijishe | 邮箱&密码 或者 cookie | 自动检测，多个账号用换行分割<br />使用邮箱密码将会进行登录（必须有ocr服务地址）<br />使用cookie将会直接使用 |
| [尚香书苑](https://sxsy19.com/)  |    ✅️     |  sxsy   | 邮箱&密码 或者 cookie |                             同上                             |
| [快萌论坛](https://kmacg20.com/) |    ✅️     |  kmacg  | 邮箱&密码 或者 cookie |                             同上                             |
|  [嘤嘤怪之家](https://yyg.one/)  |    ✅️     |   yyg   |       账号&密码       |                      必须有ocr服务地址                       |

## 支持APP

|    名称    | 是否有效 |         功能         |    变量     |                       变量说明                       |                           特殊说明                           |
| :--------: | :------: | :------------------: | :---------: | :--------------------------------------------------: | :----------------------------------------------------------: |
| 次元姬小说 |    ✅️     | 签到、阅读、领取奖励 | cyj_account | api.hwnovel.com 域名下请求体的**deviceno**&**token** | 阅读需要模拟真实时间，所以脚本会运行比较长时间，预计一个小时<br />自动订阅填写bookId和从第多少章开始订阅 |

## 支持小程序

|                     名称                      | 是否有效 |                       功能                       |     变量     |                        变量说明                         |                        特殊说明                        |
| :-------------------------------------------: | :------: | :----------------------------------------------: | :----------: | :-----------------------------------------------------: | :----------------------------------------------------: |
|                    回收猿                     |    ✅️     |              签到、抽奖、满余额提现              | hsy_username |        www.52bjy.com 请求url参数中的**username**        |                                                        |
|                   银鱼质享                    |    ✅️     |                   看视频、提现                   |     yyzx     |      n05.sentezhenxuan.com域名下**authori-zation**      |                       有效期30天                       |
|       [飞蚂蚁](https://a.c1ns.cn/iJAKu)       |    ✅️     | 签到、步数兑换、奖池投注、奖池签到、获取用户豆子 |     fmy      |     openapp.fmy90.com域名下请求中**authorization**      |                       有效期15天                       |
| [康师傅畅饮社-每日C](https://s.c1ns.cn/GekGz) |    ✅️     |                签到、看视频、邀请                | ksf_unionid  | ksfdailyc-api.teown.com 域名下请求体body中的**unionid** |                                                        |
|   [一汽丰田丰享汇](https://s.c1ns.cn/IukuX)   |    ✅️     |                   签到、查积分                   |   yqftfxh    |     fxh.ftms.com.cn 域名下请求中**Authorization**值     |                                                        |
|       [牛油谷](https://s.c1ns.cn/zfe6A)       |    ✅️     |                   签到、查积分                   |  nyg_token   |      app.niuyougu.com.cn 域名下请求中的**token**值      |                                                        |
|    [社服益寿活动](https://a.c1ns.cn/m6e7K)    |    ✅️     |               签到、问答、查询信息               |  sfys_token  |     ylapi.luckystarpay.com 域名请求中**x-token**值      |                 每日秒到0.1，貌似会黑                  |
|     [老友时光汇](https://a.c1ns.cn/Kuq1I)     |    ✅️     |               签到、问答、查询信息               | lysgh_token  |      api.zijinzhaoyao.com 域名请求中**x-token**值       |                          同上                          |
|      [中免日上](https://a.c1ns.cn/qbFEB)      |    ⚠️     |            签到、查积分、金包子小游戏            |  zmrs_token  |      api.cdfsunrise.com 请求中的**Accesstoken**值       | 有效期挺长，应该是三个月<br />抽奖已失效，加了阿里滑块 |
|    [快集合](https://wxaurl.cn/UOdOAJrVwan)    |    ✅️     |              签到、看广告、查询积分              |  kjh_openid  |      app/Exp/wxappLogin2 登录请求中的**open_id**值      |                         不过期                         |

## code版小程序

优势为不需要抓包，一般只需要首次授权，之后只需要固定几个变量就能运行

|         名称         | 是否有效 |         功能         |                           特殊说明                           |
| :------------------: | :------: | :------------------: | :----------------------------------------------------------: |
|       中通快递       |    ✅️     |         签到         | 这些脚本都必须要有微信授权协议才能够运行，运行前需要先授权小程序<br />必须变量soy_codeurl_data、soy_codetoken_data、soy_wxid_data |
|       铛铛一下       |    ✅️     |      签到、抽奖、满余额提现      |                                                              |
|       捂碳星球       |    ❌     |   签到、满余额提现   | 额外变量soy_wxphone_data，与wxid一一对应的微信手机号<br />已失效，需邀请好友才可签到 |
|        厚工坊        |    ✅️     |   签到、浏览、分享   |                                                              |
| 深圳体育湾春茧未来荟 |    ✅️     |         签到         |                                                              |
|      统一梦时代      |    ✅️     | 签到、抽奖、查询积分 |                                                              |
| [康师傅畅饮社](https://s.c1ns.cn/GekGz) | ✅️ | 签到、查积分、每日C活动(签到、视频、邀请、小游戏) | |
| [一汽丰田丰享汇](https://s.c1ns.cn/IukuX) | ✅️ | 签到、查积分 | |
| [牛油谷](https://s.c1ns.cn/zfe6A) | ✅️ | 签到、查积分 | |
| [红人库](https://s.c1ns.cn/EO1Zb) | ✅️ | 签到、查积分 | |
| [社服益寿活动](https://a.c1ns.cn/m6e7K) | ✅️ | 签到、问答、查询信息 | |
| [老友时光汇](https://a.c1ns.cn/Kuq1I) | ✅️ | 签到、问答、查询信息 | |
| [飞蚂蚁](https://a.c1ns.cn/iJAKu) | ✅️ | 签到、步数兑换、奖池投注、奖池签到、获取用户豆子 | |
| [好人家美味生活馆](https://a.c1ns.cn/Pru42) | ✅️ | 签到、查询积分 | |
| [趣淘卡](https://a.c1ns.cn/dpukh) | ✅️ | 签到、查积分 | |
| [快集合](https://wxaurl.cn/UOdOAJrVwan) | ✅️ | 签到、看广告、查询积分 | |

## 目录说明

```
/AutoTaskScripts
├── miniapp
│   ├── code
│   │   └── code版本小程序
│   └── 小程序
├── utils
│   └── 工具
├── app
│   └── APP
├── web
│   └── 网站
└── README.md
```

## 谈论交流

[频道](https://t.me/LinYuanOAO)

[群组](https://t.me/LinYuanOvO)
