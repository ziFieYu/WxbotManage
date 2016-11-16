#!/usr/bin/env python
# coding: utf-8
import Lib.wxbot
import pyqrcode
import os
import thread
import time
import json
import requests
import threading
from traceback import format_exc

def run(web_input,action,bot_list):
    #action ---> http://127.0.0.1/api/*****/  其中×××对应的就是action,通过action字段来实现自定义的操作在下面主程序编写业务逻辑
    #返回格式如下，code目前为200和500，200为正常，500为异常
    #{'code':200,'error_info':'','data':''}

    #登陆微信账号
    if action == 'wx_login':
        try:
            bot_conf = json.loads(web_input['bot_conf'])
        except Exception,e:
            print '[INFO] Web WeChat load_emtry_conf -->',e
            bot_conf = {}
        try:
            #启动机器人
            temp = weixin_bot()
            temp.start()
            bot_list.append(temp)
            time.sleep(5)
            temp.bot.bot_conf = bot_conf
            temp.bot_start_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            data = {
                'bot_id':temp.bot_id,
                'login_qr':'/static/temp/'+str(temp.bot_id)+'.png',
                'bot_start_time':temp.bot_start_time 
            }
            return {'code':200,'error_info':'','data':data}
        except Exception,e:
            return {'code':500,'error_info':str(e),'data':''}

class weixin_bot(threading.Thread):
    # 重写父类run()方法
    def run(self):
        self.bot = ReWxbot()
        self.bot.DEBUG = True
        bot_run_thread = thread.start_new_thread(self.bot.run,())
        time.sleep(3)
        self.bot_id = self.bot.uuid
        self.login_qr = '/static/temp/'+str(self.bot.uuid)+'.png'
        #bot_run_thread.join()
            
class ReWxbot(Lib.wxbot.WXBot):
    status = 'wait4login'    #表示机器人状态，供WEBAPI读取
    bot_conf = {} #机器人配置，在webapi初始化的时候传入，后续也可修改
    def handle_msg_all(self, msg):
        #载入插件系统，插件支持动态修改！修改后实时生效，无需重启程序！
        for filename in os.listdir("plugin"):
            try:
                if not filename.endswith(".py") or filename.startswith("_"):
                    continue
                pluginName=os.path.splitext(filename)[0]
                plugin=__import__("plugin."+pluginName, fromlist=[pluginName])
                reload(plugin)
                plugin.run(self,msg,pluginName)
            except Exception,e:
                print u'[ERRO] 插件%s运行错误--->%s'%(filename,e)

    def schedule(self):
        pass

    #在未传入bot_conf的情况下尝试载入本地配置文件
    def load_conf(self,bot_conf):
        try:
            if bot_conf == {}:
                with open(os.path.join(self.temp_pwd,'bot_conf.json')) as f:
                    self.bot_conf= json.loads(f.read())
        except:
            self.bot_conf = {}

    #保存配置文件
    def save_conf(self):
        with open(os.path.join(self.temp_pwd,'bot_conf.json'), 'w') as f:
            f.write(json.dumps(self.bot_conf))
            
    #动态更新通讯录信息信息
    def batch_get_contact(self,memberlist):
        """动态更新通讯录信息信息"""
        url = self.base_uri + '/webwxbatchgetcontact?type=ex&r=%s&pass_ticket=%s' % (int(time.time()), self.pass_ticket)
        params = {
            'BaseRequest': self.base_request,
            "Count": len(self.group_list),
            "List": [{"UserName": group['UserName'], "EncryChatRoomId": ""} for group in memberlist]
        }
        r = self.session.post(url, data=json.dumps(params))
        r.encoding = 'utf-8'
        dic = json.loads(r.text)
        for temp in dic['ContactList']:
            if temp['VerifyFlag'] & 8 != 0:  # 公众号
                #更新公众号列表,先判断公众号列表中有没有他，有就更新、没就新增
                i = 0
                Is_in = False
                for x in self.public_list:
                    if x['UserName'] == temp['UserName']:
                        Is_in = True
                        break
                    i = i + 1
                if Is_in:
                    self.public_list[i] = x  #更新
                else:
                    self.public_list.append(x) #新增
                self.account_info['normal_member'][temp['UserName']] = {'type': 'public', 'info': temp}
            elif temp['UserName'].find('@@') == 0:#群聊,并更新
                gid = temp['UserName']
                #更新群列表,先判断群列表中有没有他，有就更新、没就新增
                i = 0
                Is_in = False
                for x in self.group_list:
                    if x['UserName'] == temp['UserName']:
                        Is_in = True
                        break
                    i = i + 1
                self.group_members[gid] = temp['MemberList'] #更新群联系人列表
                temp['MemberList'] = [] #去除下群聊用户列表，防止字典太大
                if Is_in:
                    self.group_list[i] = temp  #更新
                else:
                    self.group_list.append(temp) #新增
                self.encry_chat_room_id_list[gid] = temp['EncryChatRoomId']  #更新群加密ID
                #添加到account_info中,以便在内部处理消息的时候能够正确获取到消息的群名
                self.account_info['normal_member'][temp['UserName']] = {'type': 'group', 'info': temp}
            elif temp['UserName'][1] != '@' and temp['UserName'][0] == '@':
                #更新联系人列表,先判断联系人列表中有没有他，有就更新、没就新增
                i = 0
                Is_in = False
                for x in self.contact_list:
                    if x['UserName'] == temp['UserName']:
                        Is_in = True
                        break
                    i = i + 1
                if Is_in:
                    self.contact_list[i] = x  #更新
                else:
                    self.contact_list.append(x) #新增
                self.account_info['normal_member'][temp['UserName']] = {'type': 'contact', 'info': temp}
            else:
                #可能是特殊帐号、本人号的信息更新
                pass
                
    def gen_qr_code(self):
        string = 'https://login.weixin.qq.com/l/' + self.uuid
        qr = pyqrcode.create(string)
        qr.png(os.path.join(os.getcwd(),'static','temp',str(self.uuid)+'.png'), scale=8)

    def run(self):
        try:
            self.get_uuid()
            self.gen_qr_code()
            print '[INFO] Please use WeChat to scan the QR code .'

            result = self.wait4login()
            if result != '200':
                print '[ERROR] Web WeChat login failed. failed code=%s' % (result,)
                self.status = 'loginout'
                return

            if self.login():
                print '[INFO] Web WeChat login succeed .'
            else:
                print '[ERROR] Web WeChat login failed .'
                self.status = 'loginout'
                return

            if self.init():
                print '[INFO] Web WeChat init succeed .'
            else:
                print '[INFO] Web WeChat init failed'
                self.status = 'loginout'
                return
            self.status_notify()
            try:
                self.get_contact()
            except:
                print '[WARN] Web WeChat Get_contact failed .'
            self.temp_pwd  =  os.path.join(os.getcwd(),'static',str(self.my_account['Uin']))
            if os.path.exists(self.temp_pwd) == False:
                os.makedirs(self.temp_pwd)
            print '[INFO] Get %d contacts' % len(self.contact_list)
            print '[INFO] Start to process messages .'
            self.save_conf()
            self.proc_msg()
            self.status = 'loginout'
        except Exception,e:
            print '[ERROR] Web WeChat run failed --> %s'%(e)
            self.status = 'loginout'
    
    def proc_msg(self):
        self.test_sync_check()
        self.status = 'loginsuccess'
        while True:
            if self.status == 'wait4loginout':
                return
            check_time = time.time()
            try:
                [retcode, selector] = self.sync_check()
                # print '[DEBUG] sync_check:', retcode, selector
                if retcode == '1100':  # 从微信客户端上登出
                    break
                elif retcode == '1101':  # 从其它设备上登了网页微信
                    break
                elif retcode == '0':
                    if selector == '2':  # 有新消息
                        r = self.sync()
                        if r is not None:
                            self.handle_msg(r)
                    elif selector == '3':  # 未知
                        r = self.sync()
                        if r is not None:
                            self.handle_msg(r)
                    elif selector == '4':  # 通讯录更新
                        r = self.sync()
                        if r is not None:
                            #self.get_contact()
                            pass
                    elif selector == '6':  # 可能是红包
                        r = self.sync()
                        if r is not None:
                            self.handle_msg(r)
                    elif selector == '7':  # 在手机上操作了微信
                        r = self.sync()
                        if r is not None:
                            self.handle_msg(r)
                    elif selector == '0':  # 无事件
                        pass
                    else:
                        print '[DEBUG] sync_check:', retcode, selector
                        r = self.sync()
                        if r is not None:
                            self.handle_msg(r)
                    try:
                        if r['ModContactList'] != []: #动态处理联系人、群更新消息
                            self.batch_get_contact(r['ModContactList'])
                            print '[DEBUG] batch %d contacts!'%(len(r['ModContactList']))
                    except:
                        pass
                else:
                    print '[DEBUG] sync_check:', retcode, selector
                self.schedule()
            except:
                print '[ERROR] Except in proc_msg'
                print format_exc()
            check_time = time.time() - check_time
            if check_time < 0.8:
                time.sleep(1 - check_time)