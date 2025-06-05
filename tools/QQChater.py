import requests
import json
import time
import sys
from pathlib import Path

# 获取上一级目录的绝对路径
parent_dir = str(Path(__file__).resolve().parent.parent)
sys.path.append(parent_dir)
import logger

class QQChater:
    def __init__(self, base_url="http://127.0.0.1:3000"):
        """初始化QQ聊天机器人"""
        self.base_url = base_url
        
    def _send_request(self, endpoint, payload):
        """
        发送请求到OneBot API
        
        :param endpoint: API端点，如/send_group_msg
        :param payload: 请求体数据
        :return: 响应数据
        """
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"请求API失败: {e}")
            print(f"请求API失败: {e}")
            return None
            
    def send_msg_to_group(self, group_id, msg):
        """
        发送文本消息到群聊
        
        :param group_id: 群号，可以是数字或字符串
        :param msg: 要发送的文本消息
        :return: 消息ID，如果发送失败返回None
        """
        logger.info(f"发送群消息: to {group_id}: \"{msg}\"")
        endpoint = "/send_group_msg"
        payload = {
            "group_id": group_id,
            "message": [
                {
                    "type": "text",
                    "data": {
                        "text": msg
                    }
                }
            ]
        }
        
        response = self._send_request(endpoint, payload)
        if response and response.get("status") == "ok":
            return response["data"]["message_id"]
        else:
            logger.error(f"发送群消息失败: {response}")
            return None
            
    def send_at_to_group(self, group_id, user_id):
        """
        发送艾特消息到群聊
        
        :param group_id: 群号，可以是数字或字符串
        :param qq: 要艾特的QQ号，可以是数字、字符串或"all"表示全体成员
        :param name: 可选，被艾特成员的昵称
        :return: 消息ID，如果发送失败返回None
        """
        logger.info(f"发送群at: to {group_id}: \"{user_id}\"")
        endpoint = "/send_group_msg"
        at_data = {"qq": user_id}
        if name:
            at_data["name"] = name
            
        payload = {
            "group_id": group_id,
            "message": [
                {
                    "type": "at",
                    "data": at_data
                }
            ]
        }
        
        response = self._send_request(endpoint, payload)
        if response and response.get("status") == "ok":
            return response["data"]["message_id"]
        else:
            logger.error(f"发送群艾特失败: {response}")
            return None
            
    def send_at_msg_to_group(self, group_id, user_id, msg):
        """
        发送艾特+文本消息到群聊
        
        :param group_id: 群号，可以是数字或字符串
        :param qq: 要艾特的QQ号，可以是数字、字符串或"all"表示全体成员
        :param msg: 要发送的文本消息
        :param name: 可选，被艾特成员的昵称
        :return: 消息ID，如果发送失败返回None
        """
        logger.info(f"发送群消息: to {group_id}: \"{msg}\"")
        endpoint = "/send_group_msg"
        at_data = {"qq": user_id}
            
        payload = {
            "group_id": group_id,
            "message": [
                {
                    "type": "at",
                    "data": at_data
                },
                {
                    "type": "text",
                    "data": {
                        "text": msg
                    }
                }
            ]
        }
        
        response = self._send_request(endpoint, payload)
        if response and response.get("status") == "ok":
            return response["data"]["message_id"]
        else:
            logger.error(f"发送群艾特消息失败: {response}")
            return None
        
    def send_msg_to_private(self, user_id, msg):
        """
        发送文本消息到私聊
        
        :param user_id: 用户QQ号
        :param msg: 要发送的文本消息
        :return: 消息ID，如果发送失败返回None
        """
        endpoint = "/send_private_msg"
        payload = {
            "user_id": user_id,
            "message": [
                {
                    "type": "text",
                    "data": {
                        "text": msg
                    }
                }
            ]
        }
        
        response = self._send_request(endpoint, payload)
        if response and response.get("status") == "ok":
            return response["data"]["message_id"]
        else:
            logger.error(f"发送私聊消息失败: {response}")
            return None
        
    def get_group_msg_history(self, group_id, message_seq=0, count=1, reverse_order=False):
        """
        获取群历史消息
        
        :param group_id: 群号，可以是数字或字符串
        :param message_seq: 起始消息序号，0表示从最新消息开始
        :param count: 获取的消息数量，默认为20
        :param reverse_order: 是否按时间倒序排列，默认为False(时间正序)
        :return: 消息列表，如果获取失败返回None
        """
        endpoint = "/get_group_msg_history"
        payload = {
            "group_id": group_id,
            "message_seq": message_seq,
            "count": count,
            "reverseOrder": reverse_order
        }
        
        response = self._send_request(endpoint, payload)
        if response and response.get("status") == "ok":
            return response["data"]["messages"]
        else:
            logger.error(f"获取群历史消息失败: {response}")
            return None
    
    def get_friend_msg_history(self, user_id, message_seq=0, count=1, reverse_order=False):
        """
        获取好友历史消息
        
        :param user_id: 用户QQ号
        :param message_seq: 起始消息序号，0表示从最新消息开始
        :param count: 获取的消息数量，默认为20
        :param reverse_order: 是否按时间倒序排列，默认为False(时间正序)
        :return: 消息列表，如果获取失败返回None
        """
        endpoint = "/get_friend_msg_history"
        payload = {
            "user_id": user_id,
            "message_seq": message_seq,
            "count": count,
            "reverseOrder": reverse_order
        }
        
        response = self._send_request(endpoint, payload)
        if response and response.get("status") == "ok":
            return response["data"]["messages"]
        else:
            logger.error(f"获取好友历史消息失败: {response}")
            return None
    
    def get_group_member_info(self, group_id, user_id, no_cache=False):
        """
        获取群成员详细信息
        
        :param group_id: 群号，可以是数字或字符串
        :param user_id: 要查询的成员QQ号，可以是数字或字符串
        :param no_cache: 是否不使用缓存(强制从服务器获取最新数据)，默认为False
        :return: 群成员信息字典，如果获取失败返回None
        """
        endpoint = "/get_group_member_info"
        payload = {
            "group_id": group_id,
            "user_id": user_id,
            "no_cache": no_cache
        }
        
        response = self._send_request(endpoint, payload)
        if response and response.get("status") == "ok":
            return response["data"]
        else:
            self.logger.error(f"获取群成员信息失败: {response}")
            return None
            
    def get_group_member_card(self, group_id, user_id, no_cache=False):
        """
        获取群成员群名片(快捷方法)
        
        :param group_id: 群号，可以是数字或字符串
        :param user_id: 要查询的成员QQ号，可以是数字或字符串
        :param no_cache: 是否不使用缓存，默认为False
        :return: 群名片字符串，如果获取失败返回None
        """
        member_info = self.get_group_member_info(group_id, user_id, no_cache)
        return member_info.get("card") if member_info else None
    
    def transform_messages(self, group_id, message_data_list):
        result = []
    
        for message_data in message_data_list:
            # 确保输入是字典格式
            if isinstance(message_data, str):
                message_data = json.loads(message_data)
            
            # 提取所需字段
            card = message_data['sender']['card']
            if not card:
                card = message_data['sender']['nickname']
                
            timestamp = message_data['time']
            
            # 处理消息内容
            message_parts = []
            for item in message_data['message']:
                if item['type'] == 'text':
                    message_parts.append(item['data']['text'])
                elif item['type'] == 'at':
                    message_parts.append(f"[at:{self.get_group_member_card(group_id, item['data']['qq'])}]")
            
            # 合并消息部分
            full_message = ''.join(message_parts).strip()
            
            # 如果消息不为空才添加到结果
            if full_message:
                result.append({
                    "card": card,
                    "time": timestamp,
                    "message": full_message
                })

        return {"messages": result}
    
    def send_msg_package_to_group(self, group_id, message_data_list):
        """发送消息包到群聊"""
        for message_data in message_data_list:
            self.send_msg_to_group(group_id, message_data)
            sleep(0.5*len(message_data))
        
    def send_msg_package_to_private(self, user_id, message_data_list):
        """发送消息包到私聊"""
        for message_data in message_data_list:
            self.send_msg_to_private(user_id, message_data)
            sleep(0.5*len(message_data))
    
    def format_message(self, group_id, message_data):
        """格式化消息数据"""
        formated_message = []
        message_data = self.transform_messages(group_id, message_data)
        for message in message_data['messages']:
            formated_message.append(f"{message['card']}({time.strftime("%m_%d %H:%M", time.localtime(message['time']))}):{message['message']}")
        return formated_message