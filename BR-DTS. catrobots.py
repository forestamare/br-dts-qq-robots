import nonebot
from nonebot import Scheduler
from nonebot.adapters.onebot.v11 import Bot, Event
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# 创建一个调度器
scheduler = Scheduler()

# 存储游戏账号信息
game_accounts = []
auto_reply_enabled = True  # 自动回复开关
group_id = None  # 用于存储最近接收到的群 ID

# 记录每个账号的获取状态和日期
invite_code_status = {}

# 用于存储用户请求次数和时间戳
user_request_count = {}
max_requests_per_day = 2  # 每天最多请求次数
request_time_limit = timedelta(days=1)  # 24小时

class GameAccount:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.session = requests.Session()

    def login(self):
        login_url = "http://s1.dtsgame.com/index.php"  # 登录 URL
        payload = {
            "username": self.username,
            "password": self.password,
            "inv": "",
            "mode": "main"
        }
        response = self.session.post(login_url, data=payload)
        return response.ok  # 登录成功返回 True

    def get_invite_code(self):
        invite_url = "http://s1.dtsgame.com/badge.php"  # 获取邀请码的 URL
        response = self.session.get(invite_url)
        
        if response.ok:
            soup = BeautifulSoup(response.content, 'html.parser')
            invite_button = soup.find('span', class_='lime', id='getcode')
            if invite_button:
                invite_request_url = "http://s1.dtsgame.com/get_invite_code.php"  # 假设的获取邀请码的请求 URL
                invite_response = self.session.get(invite_request_url)

                if invite_response.ok:
                    invite_soup = BeautifulSoup(invite_response.content, 'html.parser')
                    invite_code = invite_soup.find('div', id='invite_code')
                    if invite_code:
                        return invite_code.text.strip()  # 返回邀请码
        return None

    def logout(self):
        logout_url = "http://s1.dtsgame.com/index.php"  # 退出 URL
        payload = {
            "quit": "账号退出"  # 发送退出请求
        }
        self.session.post(logout_url, data=payload)  # 发送 POST 请求以退出

async def send_group_message(bot: Bot, group_id: int, message: str):
    await bot.send_group_msg(group_id=group_id, message=message)

async def handle_accounts(user_id):
    global group_id
    all_invite_codes_obtained = True  # 假设所有账号都已获取邀请码
    invite_codes = []  # 存储获取到的邀请码

    for account in game_accounts:
        if account.login():
            invite_code = account.get_invite_code()
            if invite_code:
                invite_codes.append(invite_code)  # 收集获取到的邀请码
                invite_code_status[account.username] = (True, datetime.now())  # 记录已获取状态和时间
            else:
                all_invite_codes_obtained = False  # 至少有一个账号未获取邀请码
            account.logout()  # 退出账户
        else:
            all_invite_codes_obtained = False  # 至少有一个账号登录失败

    if invite_codes:
        # 如果成功获取到邀请码，发送给用户
        await send_group_message(bot, group_id, f"猫猫来了，这是你需要的邀请码：{', '.join(invite_codes)}")
    elif all_invite_codes_obtained:
        # 如果所有账号都已获取完邀请码
        await send_group_message(bot, group_id, "抱歉，所有游戏账号今日的邀请码已用完，请明天再来请求。")
    else:
        # 如果有账号获取失败
        await send_group_message(bot, group_id, "抱歉，猫猫未能成功获取邀请码，请稍后再试。")

@scheduler.scheduled_job('interval', seconds=86400)  # 每天运行一次
async def reset_invite_code_status():
    global invite_code_status
    today = datetime.now().date()
    for username in list(invite_code_status.keys()):
        _, date = invite_code_status[username]
        if date.date() < today:  # 如果记录的日期早于今天
            del invite_code_status[username]  # 删除记录

@scheduler.scheduled_job('interval', seconds=1)
async def job():
    if auto_reply_enabled and group_id:  # 检查自动回复开关和群 ID
        # 这里可以根据需要调用 handle_accounts()
        pass

@nonebot.on_message()
async def handle_group_message(bot: Bot, event: Event):
    global group_id
    if event.group_id:  # 确保是群消息
        group_id = event.group_id  # 更新群 ID
        message = event.message.strip()
        
        # 获取用户 ID
        user_id = event.user_id

        # 检查是否是机器人自己
        if user_id == bot.self_id:
            return  # 如果是机器人自己，则不处理

        # 检查用户请求记录
        if user_id not in user_request_count:
            user_request_count[user_id] = [0, datetime.now()]  # 初始化请求次数和时间戳

        request_count, first_request_time = user_request_count[user_id]

        # 检查时间是否超过24小时
        if datetime.now() - first_request_time > request_time_limit:
            # 重置请求次数和时间戳
            user_request_count[user_id] = [0, datetime.now()]
            request_count = 0

        # 检查请求次数
        if request_count < max_requests_per_day:
            if "邀请码" in message and auto_reply_enabled:  # 检查自动回复开关
                await handle_accounts(user_id)  # 处理邀请码请求
                # 更新请求次数
                user_request_count[user_id][0] += 1
        else:
            await send_group_message(bot, group_id, "您今天已经获取了两个邀请码，请明天再来请求喵~")

@nonebot.on_command("导入账号", aliases={"import_accounts"})
async def import_accounts(bot: Bot, event: Event, args: str):
    global game_accounts
    accounts = args.split(';')  # 假设账号用分号分隔
    for account in accounts:
        username, password = account.split(',')  # 假设账号格式为 username,password
        game_accounts.append(GameAccount(username.strip(), password.strip()))
    await send_group_message(bot, event.group_id, "账号导入成功！")

# 启动调度器
scheduler.start()

# 结束提示
print("猫猫已启动，正在监听消息...")
