import logging

from melobot import Bot, PluginPlanner
from melobot.protocols.onebot.v11.handle import on_at_qq
from melobot.protocols.onebot.v11 import MessageEvent, on_message, GroupMsgChecker, LevelRole, ForwardWebSocketIO, OneBotV11Protocol
from melobot import send_text
from melobot.adapter.content import TextContent
from melobot.adapter.generic import send_refer
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import settings
from core.interfaces import IMessagePusher, IUserService
from core.user_service import UserService
from core.admin import AdminService
from services.factories import PWVNRoleplayChatServiceFactory, GeneralChatServiceFactory
from services.llm_factory import initialize_global_llm
from services.news_service import NewsService
from services.scheduler_service import SchedulerService
from melobot.protocols.onebot.v11.adapter import Adapter

class OneBotV11Pusher(IMessagePusher):
    """
    IMessagePusher 接口的 OneBot V11 实现。
    使用 melobot Bot 实例来主动发送消息。
    """
    MAX_LENGTH = 3500

    def __init__(self, bot: Bot):
        self._bot = bot

    @classmethod
    def _split_message(cls, message: str) -> list[str]:
        """
        将长消息按 MAX_LENGTH 拆分，优先在换行处分割，返回各片段列表。
        """
        parts = []
        start = 0
        length = len(message)
        while start < length:
            end = min(start + cls.MAX_LENGTH, length)
            snippet = message[start:end]
            # 如果截断点不是末尾，尝试向后或向前找换行
            if end < length:
                nl = snippet.rfind("\n")
                if nl != -1:
                    end = start + nl
                    snippet = message[start:end]
            parts.append(snippet)
            start = end
        return parts

    async def send_private_message(self, user_id: int, message: str) -> None:
        parts = self._split_message(message)
        for idx, part in enumerate(parts, 1):
            try:
                await self._bot.get_adapter(Adapter).send_custom(user_id=user_id, msgs=part)
                logging.info(f"[Private] Sent part {idx}/{len(parts)} to user {user_id} (len={len(part)})")
            except Exception as e:
                logging.error(f"Failed to send private part {idx} to {user_id}: {e}", exc_info=True)

    async def send_group_message(self, group_id: int, message: str) -> None:
        parts = self._split_message(message)
        for idx, part in enumerate(parts, 1):
            try:
                await self._bot.get_adapter(Adapter).send_custom(group_id=group_id, msgs=part)
                logging.info(f"[Group] Sent part {idx}/{len(parts)} to group {group_id} (len={len(part)})")
            except Exception as e:
                logging.error(f"Failed to send group part {idx} to {group_id}: {e}", exc_info=True)


def register_message_handlers(bot: Bot, user_service: IUserService) -> PluginPlanner:
    """
    注册 OneBot V11 的消息处理器，返回一个 PluginPlanner。
    包含群 @ 匹配和私聊匹配两种场景。
    """
    @on_at_qq(qid=settings.BOT_QQ_ID, checker=GroupMsgChecker(
        role=LevelRole.NORMAL,
        white_groups=settings.ENABLED_GROUP_IDS
    ))
    async def handle_group_at(event: MessageEvent) -> None:

        user_id = event.user_id
        # 拼接文本消息
        text = "".join(m.to_dict()['data']['text'] for m in event.message if m.to_dict()['type'] == 'text').lstrip()
        reply = await user_service.handle_message(user_id, text)
        # 发送回复
        await send_refer(event, [TextContent(reply)])

    @on_message()
    async def handle_private(event: MessageEvent) -> None:
        if not event.is_private():
            return
        user_id = event.user_id
        text = "".join(m.to_dict()['data']['text'] for m in event.message if m.to_dict()['type'] == 'text').lstrip()
        reply = await user_service.handle_message(user_id, text)
        await send_text(reply)

    planner = PluginPlanner(version="1.0.0", flows=[handle_group_at, handle_private])
    return planner


def main():
    # 日志配置
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logging.getLogger('apscheduler').setLevel(logging.WARNING)

    # 初始化 LLM
    initialize_global_llm()

    # Bot 和 OneBot 协议
    bot = Bot(__name__)
    bot.add_protocol(OneBotV11Protocol(ForwardWebSocketIO(settings.ONEBOT_WS_URL)))

    scheduler = AsyncIOScheduler()
    
    @bot.on_started
    async def init():
        scheduler.start()
        logging.info("scheduler 已启动")

    @bot.on_stopped
    async def stop():
        scheduler.shutdown()
        logging.info("scheduler 已正常退出")

    # Pusher & 服务
    onebot_pusher = OneBotV11Pusher(bot)
    news_service = NewsService()
    scheduler_service = SchedulerService(news_service=news_service, scheduler=scheduler, pusher=onebot_pusher)
    admin_service = AdminService(scheduler_service=scheduler_service)

    factories = {
        'pwvn': PWVNRoleplayChatServiceFactory(settings.PWVN_ROLES_CONFIG_PATH),
        'plain': GeneralChatServiceFactory(),
    }
    user_service = UserService(
        user_data_path=settings.USER_DATA_PATH,
        factories=factories,
        admin_service=admin_service
    )

    # 注册插件
    plugin = register_message_handlers(bot, user_service)
    bot.load_plugin(plugin)

    # 启动调度器
    scheduler_service.start()
    logging.info("Scheduler service started.")

    # 启动 Bot
    logging.info("OneBot adapter started. Listening for events...")
    bot.run()


if __name__ == "__main__":
    main()
