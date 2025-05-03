from time import sleep


class aihandler:
    def __init__(self):
        pass
    def set_max_context(self, max_context):
        pass
    def get_max_context(self):
        return 10
    def set_temperature(self, temperature):
        pass
    def get_temperature(self):
        return 0.5
    def auto_message(self):
        return [{"zh":"你好啊，你发送了一条自动消息。","ja":"こんにちは、自動メッセージを送信しました。"}]
    def user_message(self, message):
        sleep(5)
        return [{"zh":"你好啊，你发送了一条用户消息。","ja":"こんにちは、ユーザーからのメッセージを受け取りました。"}]