#!/usr/bin/env python
# coding: utf-8
#####插件说明#####
#炸群监控插件！！通过匹配消息中的敏感词数量来自动踢出某些群内的捣乱分子
import json
import web
import re
import os
import Lib.alimama
import requests
import time
import random

def run(WXBOT,msg,plugin_name):
	try:
		WXBOT.bot_conf[plugin_name]
	except:
		WXBOT.bot_conf[plugin_name] ={
		    'switch':True,
		    'alimama_siteid':'15574862',
		    'alimama_adzoneid':'59576937',
		    'alimama_sign_account':'ca387a0f250083076b1b2168c824881f',
		    'message_send_with_coupons':u'发现优惠券啦！复制这条信息%s，打开【手机淘宝】可领取本群专属手机优惠劵【%s元】在下单购买！如果无法领取说明代金券已经领取完！',
		    'message_send_with_fanli':u'复制本内容%s,打开【手机淘宝】下单并确认收货后将订单号私聊我，可以领取商家红包【%s元】！有问题可以私聊咨询我！',
		    'message_search_fail':u'没有相关优惠，换个试试吧～'
		}
		
	if  WXBOT.bot_conf[plugin_name]['switch'] == True and ((msg['msg_type_id'] == 3  or msg['msg_type_id'] == 4 ) and msg['content']['type'] == 0 ):		   
		A_MAMA = Lib.alimama.alimama(WXBOT.bot_conf[plugin_name]['alimama_siteid'],WXBOT.bot_conf[plugin_name]['alimama_adzoneid'],WXBOT.bot_conf[plugin_name]['alimama_sign_account'],'remote')
		print '[INFO] Start anaysis Message!' 
		#匹配查询命令，并找到对应关键词商品回复
		search_pattern	 =  re.compile(u"^(买|找|帮我找|有没有|我要买)\s?(.*?)$")
		Command_result   = search_pattern.findall(msg['content']['data'])
		if len(Command_result)==1:
			skey = Command_result[0][1]
			print u'[INFO] TBK命中查询命令，关键词-->%s'%(skey)
			result,data = A_MAMA.search_item_info_by_key_use_queqiao(skey)
			send_search_result_to_uid(WXBOT,A_MAMA,data,msg,skey,'',plugin_name)

		#模糊匹配url提取商品id
		search_url_pattern =  re.compile(u"[a-zA-z]+://[^\s]*")
		Command_result = search_url_pattern.findall(msg['content']['data'])
		if len(Command_result) > 0:
			iid = search_iid_from_url(Command_result[0])
			#print u'[INFO] LOG-->Command_result:%s'%(str(Command_result))
			if iid != '':
				print u'[INFO] TBK发现商品ID-->%s'%(iid)
				result,data = A_MAMA.search_item_info_by_iid(iid)
				send_search_result_to_uid(WXBOT,A_MAMA,data,msg,'',iid,plugin_name)

def send_search_result_to_uid(WXBOT,A_MAMA,data,msg,skey=None,iid=None,plugin_name=None):
	#模糊匹配中，如果匹配到查询命令会调用此函数
	if data['data']['pageList'] != None:
		item_info = data['data']['pageList'][random.randint(0,len(data['data']['pageList'])-1)]
		item_info['title'] = re.sub(u'<(.*?)>','',item_info['title'])
		result,sclick_data = A_MAMA.create_auction_code_with_tkl(item_info['auctionId'],WXBOT.bot_conf[plugin_name]['alimama_siteid'],WXBOT.bot_conf[plugin_name]['alimama_adzoneid'],item_info)
		send_item_pic_to_uid(WXBOT,item_info,msg)
		time.sleep(0.5)
		try:
		    #尝试获取2合1的淘口令,整合代金券
			sclick_data['data']['couponLinkTaoToken']
			WXBOT.send_msg_by_uid(WXBOT.bot_conf[plugin_name]['message_send_with_coupons']%(sclick_data['data']['couponLinkTaoToken'],item_info['couponAmount']),msg['user']['id'])
		except:
			time.sleep(0.5)
			#没找到代金券，开启返利模式
			fanli_fee = int(int(item_info['tkCommFee'])*0.4)
			fanli_fee = (str(fanli_fee) if fanli_fee > 0 else str(item_info['tkCommFee']))
			WXBOT.send_msg_by_uid(WXBOT.bot_conf[plugin_name]['message_send_with_fanli']%(sclick_data['data']['taoToken'],fanli_fee), msg['user']['id'])
	else:
		WXBOT.send_msg_by_uid(WXBOT.bot_conf[plugin_name]['message_search_fail'], msg['user']['id'])

def search_iid_from_url(x):
	#从消息中提取的url来进行iid的提取，这个函数代扩容！！
	search_iid_pattern =  re.compile(u"(http|https)://(item\.taobao\.com|detail\.tmall\.com)/(.*?)id=(\d*)")
	search_iid_pattern_2 = re.compile(u'(http|https)://(a\.m\.taobao\.com)/i(\d*)\.htm')
	r = requests.get(x,headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.63 Safari/537.36'})
	iid = ''
	temp = search_iid_pattern.findall(r.url)
	if len(temp)==0:
		try:
			iid = search_iid_pattern.findall(r.content)[0][3]
		except:
			try:
				iid = search_iid_pattern_2.findall(r.content)[0][2]
			except:
				pass
	else:
		iid = temp[0][3]
	return iid

def send_item_pic_to_uid(WXBOT,item_info,msg):
	pic_path = os.path.join(os.getcwd(),'temp',"item_"+str(item_info['auctionId'])+".jpg")
	file_object = open(pic_path, 'wb')
	file_object.write(requests.get(item_info['pictUrl']).content)
	file_object.close()
	WXBOT.send_img_msg_by_uid(pic_path,msg['user']['id'])