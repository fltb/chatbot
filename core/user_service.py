import os
import json
import uuid
import logging
import threading
import functools
from typing import Dict, Optional, Any

from llama_index.core import Settings

from config import settings
from core.interfaces import IUserService, IChatService
from core.models import UserProfile, SessionInfo
from core.admin import NotAdminError, AdminService
from services.llm_factory import get_llm_by_name # LLM 加载功能移至 llm_factory

# 为 RoleValidationError 定义一个本地异常，或从公共异常模块导入
class RoleValidationError(Exception):
    pass

class UserService(IUserService):
    def __init__(self, user_data_path: str, factories: Dict[str, Any], admin_service: AdminService):
        self._user_data_path = user_data_path
        self._factories = factories
        self.admin_service = admin_service
        
        self._users: Dict[int, UserProfile] = {}
        self._active_chats: Dict[str, IChatService] = {}
        self._lock = threading.Lock() # 保护对 _users 和 _active_chats 的写入
        
        self._load_roles_config()
        self._load_all_users()
        self._register_commands()

    # --- 初始化与数据加载 ---

    def _load_roles_config(self):
        """加载角色配置用于验证"""
        try:
            with open(settings.PWVN_ROLES_CONFIG_PATH, 'r', encoding='utf-8') as f:
                self._roles_config = json.load(f)
            self.AVAILABLE_ROLES = self._roles_config.keys()
        except FileNotFoundError:
            self._roles_config = {}
            self.AVAILABLE_ROLES = []
            logging.warning(f"Roles config file not found at {settings.PWVN_ROLES_CONFIG_PATH}")

    def _load_all_users(self):
        os.makedirs(os.path.dirname(self._user_data_path), exist_ok=True)
        try:
            with open(self._user_data_path, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
                for user_id_str, data in raw_data.items():
                    user_id = int(user_id_str)
                    sessions = {
                        session_id: SessionInfo(
                            session_id=session_id,
                            session_mode=session_data.get('session_mode', 'pwvn'),
                            user_role=session_data.get('user_role'),
                            bot_role=session_data.get('bot_role')
                        )
                        for session_id, session_data in data.get('sessions', {}).items()
                    }
                    self._users[user_id] = UserProfile(
                        user_id=user_id,
                        active_session_id=data.get('active_session_id'),
                        sessions=sessions
                    )
        except (FileNotFoundError, json.JSONDecodeError):
            self._users = {}
        logging.info(f"Loaded {len(self._users)} users.")

    def _save_user_profile(self, user_id: int):
        with self._lock:
            with open(self._user_data_path, 'w', encoding='utf-8') as f:
                serializable_users = {
                    uid: {
                        'user_id': profile.user_id,
                        'active_session_id': profile.active_session_id,
                        'sessions': {
                            sid: s.__dict__ 
                            for sid, s in profile.sessions.items()
                        }
                    } for uid, profile in self._users.items()
                }
                json.dump(serializable_users, f, indent=4)

    def _get_or_create_user(self, user_id: int) -> UserProfile:
        if user_id not in self._users:
            self._users[user_id] = UserProfile(user_id=user_id)
        return self._users[user_id]

    # --- 命令路由 ---

    def _register_commands(self):
        """将命令映射到处理函数"""
        self._commands = {
            'new': {'handler': self._handle_new_session, 'help': '/new <mode> [args...] - 创建新会话, 可用模式: pwvn, plain'},
            'ls': {'handler': self._handle_list_sessions, 'help': '/ls - 列出所有会话'},
            'ss': {'handler': self._handle_switch_session, 'help': '/ss <session_id> - 切换会话'},
            'dels': {'handler': self._handle_delete_session, 'help': '/dels <session_id> - 删除会话'},
            'sbr': {'handler': self._handle_modify_role, 'help': '/sbr <role> - 切换当前机器人角色'},
            'sur': {'handler': self._handle_modify_role, 'help': '/sur <role> - 切换当前用户角色'},
            'sl': {'handler': self._handle_switch_llm, 'help': '/sl <model> - 切换当前会话的LLM'},
            'help': {'handler': self._handle_help, 'help': '/help - 显示此帮助信息'},
        }
    
    async def handle_message(self, user_id: int, message: str) -> str:
        message = message.strip()
        if not message:
            message = ""

        if message.startswith('/admin'):
            try:
                return await self.admin_service.handle_command(user_id, message)
            except NotAdminError as e:
                return str(e)
            except Exception as e:
                logging.error(f"Admin command failed: {e}", exc_info=True)
                return f"Admin command failed: {e}"
        
        if message.startswith('/'):
            return await self._handle_user_command(user_id, message)

        chat = self._get_active_chat(user_id)
        if not chat:
            # Return the message directly if it's a string response
            if isinstance(chat, str):
                return chat
            
            # Otherwise return the formatted message
            msg_lines = [
                "当前无活动会话,你可以使用以下命令开启新会话：",
                "",
                "1. 普通对话：",
                "   /new plain",
                "   适合日常提问、闲聊。",
                "",
                "2. 角色扮演 (Password VN)：",
                "   /new pwvn <你的角色> <Bot角色>",
                f"   例如：/new pwvn Dave Dean",
                f"   Bot 角色可选：{', '.join(self.AVAILABLE_ROLES) if hasattr(self, 'AVAILABLE_ROLES') and self.AVAILABLE_ROLES else '（请先配置角色）'}",
                "",
                "输入 /ls 可查看你所有的会话。",
                "输入 /help 查看全部指令。"
            ]
            return "\n".join(msg_lines)

        # Only call get_response if chat is actually a chat service
        return chat.get_response(message)

    async def _handle_user_command(self, user_id: int, message: str) -> str:
        parts = message[1:].split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ''

        cmd_info = self._commands.get(command)
        if not cmd_info:
            # Check aliases
            for key, info in self._commands.items():
                if command in info.get('aliases', []):
                    cmd_info = info
                    break
        
        if cmd_info:
            handler = cmd_info['handler']
            # Pass the original command for context if needed (e.g., for _handle_modify_role)
            return await handler(user_id, args, command=command)
        
        return f"未知指令 '{command}'。输入 /help 查看可用指令。"
        
    # --- 命令处理实现 ---

    async def _handle_help(self, user_id: int, args: str, **kwargs) -> str:
        help_lines = [meta['help'] for meta in self._commands.values()]
        return "[可用指令]\n" + "\n".join(help_lines)

    async def _handle_new_session(self, user_id: int, args: str, **kwargs) -> str:
        parts = args.split()
        if not parts or (len(parts) == 1 and parts[0] in ('?', 'help')):
            # 直观中文模式说明
            msg_lines = [
                "欢迎使用多模式对话。你可以使用以下命令开启新会话：",
                "",
                "1. 普通对话：",
                "   /new plain",
                "   适合日常提问、闲聊。",
                "",
                "2. 角色扮演 (Password VN)：",
                "   /new pwvn <你的角色> <Bot角色>",
                f"   例如：/new pwvn Dave Dean",
                f"   Bot 角色可选：{', '.join(self.AVAILABLE_ROLES) if hasattr(self, 'AVAILABLE_ROLES') and self.AVAILABLE_ROLES else '（请先配置角色）'}",
                "",
                "输入 /ls 可查看你所有的会话。",
                "输入 /help 查看全部指令。"
            ]
            return "\n".join(msg_lines)
        
        mode = parts[0]
        mode_args = parts[1:]

        if mode not in self._factories:
            return f"未知模式 '{mode}'.\n可用模式: {', '.join(self._factories.keys())}"
        
        session_info = None
        if mode == 'pwvn':
            if len(mode_args) < 2:
                msg_lines = [
                    "角色扮演模式需指定你的角色和 Bot 角色。",
                    "用法：/new pwvn <你的角色> <Bot角色>",
                    f"Bot 角色可选：{', '.join(self.AVAILABLE_ROLES) if hasattr(self, 'AVAILABLE_ROLES') and self.AVAILABLE_ROLES else '（请先配置角色）'}",
                    "例如：/new pwvn Dave Dean"
                ]
                return "\n".join(msg_lines)
            user_role, bot_role = mode_args[0], mode_args[1]
            try:
                self._validate_role(bot_role)
            except RoleValidationError as e:
                return str(e)
            session_info = SessionInfo(session_id=uuid.uuid4().hex, session_mode='pwvn', user_role=user_role, bot_role=bot_role)
        else: # Add other modes here
            session_info = SessionInfo(session_id=uuid.uuid4().hex, session_mode=mode)
        
        with self._lock:
            user_profile = self._get_or_create_user(user_id)
            user_profile.sessions[session_info.session_id] = session_info
            self._invalidate_active_chat(user_profile.active_session_id)
            user_profile.active_session_id = session_info.session_id
        self._save_user_profile(user_id)
        return f"新会话已在 '{mode}' 模式下创建。会话ID: {session_info.session_id[:8]}"

    async def _handle_list_sessions(self, user_id: int, args: str, **kwargs) -> str:
        with self._lock:
            user_profile = self._get_or_create_user(user_id)
        if not user_profile.sessions:
            return "你还没有任何会话。"

        lines = ["【你的会话列表】"]

        for s in user_profile.sessions.values():
            prefix = "【当前对话】->" if s.session_id == user_profile.active_session_id else "  "
            details = f"{s.bot_role} ↔ {s.user_role}, 模式: {s.session_mode}" if s.session_mode == 'pwvn' else f"模式: {s.session_mode}"
            lines.append(f"{prefix}ID: {s.session_id[:8]} ({details})")
        return "\n".join(lines)

    async def _handle_switch_session(self, user_id: int, args: str, **kwargs) -> str:
        session_id_prefix = args.strip()
        if not session_id_prefix:
            return "请输入要切换的会话ID的前几位。"

        with self._lock:
            user_profile = self._get_or_create_user(user_id)
            target_session = next((s for s in user_profile.sessions.values() if s.session_id.startswith(session_id_prefix)), None)

            if not target_session:
                return f"未找到以 '{session_id_prefix}' 开头的会话。"
            self._invalidate_active_chat(user_profile.active_session_id) # 清除旧的缓存
            user_profile.active_session_id = target_session.session_id

        self._save_user_profile(user_id)
        return f"已切换到会话: {target_session.session_id[:8]}"

    async def _handle_delete_session(self, user_id: int, args: str, **kwargs) -> str:
        session_id_prefix = args.strip()
        if not session_id_prefix:
            return "请输入要删除的会话ID的前几位。"
        
        with self._lock:
            user_profile = self._get_or_create_user(user_id)
            target_sessions = [s for s in user_profile.sessions.values() if s.session_id.startswith(session_id_prefix)]
            if not target_sessions:
                return f"未找到以 '{session_id_prefix}' 开头的会话。"
            if len(target_sessions) > 1:
                return "找到多个匹配的会话，请输入更长的ID以精确定位。"
            
            target_id = target_sessions[0].session_id
            del user_profile.sessions[target_id]

            if user_profile.active_session_id == target_id:
                # Use next(iter()) to get first element without creating full list
                user_profile.active_session_id = next(iter(user_profile.sessions.values())).session_id if user_profile.sessions else None
                self._invalidate_active_chat(target_id)
        
        self._save_user_profile(user_id)
        return f"已删除会话: {target_id[:8]}"

    async def _handle_modify_role(self, user_id: int, args: str, **kwargs) -> str:
        role_name = args.strip()
        command = kwargs.get('command')
        if not role_name:
            return "请输入角色名称。"

        session_info = self._get_active_session_info(user_id)
        if not session_info or session_info.session_mode != 'pwvn':
            return "此命令仅在 'pwvn' 模式的会话中可用。"

        with self._lock:
            if command == 'sbr': # switch bot role
                try:
                    self._validate_role(role_name)
                except RoleValidationError as e:
                    return str(e)
                session_info.bot_role = role_name
            elif command == 'sur': # switch user role
                session_info.user_role = role_name
            
            # 关键：使缓存的 ChatService 失效，强制下次重建
            self._invalidate_active_chat(session_info.session_id)
        
        self._save_user_profile(user_id)
        return f"角色已更新。当前: {session_info.user_role} ↔ {session_info.bot_role}"

    async def _handle_switch_llm(self, user_id: int, args: str, **kwargs) -> str:
        model_name = args.strip()
        if not model_name:
            return "请输入模型名称。"
        
        chat = self._get_active_chat(user_id)
        if not chat:
            msg_lines = [
                "当前无活动会话,你可以使用以下命令开启新会话：",
                "",
                "1. 普通对话：",
                "   /new plain",
                "   适合日常提问、闲聊。",
                "",
                "2. 角色扮演 (Password VN)：",
                "   /new pwvn <你的角色> <Bot角色>",
                f"   例如：/new pwvn Dave Dean",
                f"   Bot 角色可选：{', '.join(self.AVAILABLE_ROLES) if hasattr(self, 'AVAILABLE_ROLES') and self.AVAILABLE_ROLES else '（请先配置角色）'}",
                "",
                "输入 /ls 可查看你所有的会话。",
                "输入 /help 查看全部指令。"
            ]
            return "\n".join(msg_lines)

        try:
            new_llm = get_llm_by_name(model_name)
            chat.switch_llm(new_llm) # 直接在活动的 ChatService 实例上操作
            return f"当前会话的 LLM 已切换为: {model_name}"
        except Exception as e:
            return f"切换 LLM 失败: {e}"

    # --- 辅助方法 ---

    def _validate_role(self, role_name: str):
        if role_name not in self.AVAILABLE_ROLES:
            raise RoleValidationError(f"错误：无效的角色 '{role_name}'。\n可用角色: {', '.join(self.AVAILABLE_ROLES)}")

    def _get_active_session_info(self, user_id: int) -> Optional[SessionInfo]:
        with self._lock:
            user_profile = self._get_or_create_user(user_id)
            if not user_profile.active_session_id:
                return None
        return user_profile.sessions.get(user_profile.active_session_id, None)
        
    def _invalidate_active_chat(self, session_id: Optional[str]):
        if session_id and session_id in self._active_chats:
            del self._active_chats[session_id]
            logging.info(f"Invalidated cached chat service for session {session_id}")

    def _get_active_chat(self, user_id: int):
        """
        获取当前活跃的会话服务，如果不存在则提示用户使用/new创建新会话
        """
        session_info = self._get_active_session_info(user_id)
        if not session_info:
            return None

        if session_info.session_id in self._active_chats:
            return self._active_chats[session_info.session_id]

        with self._lock:
            # Double-check after acquiring lock
            if session_info.session_id in self._active_chats:
                return self._active_chats[session_info.session_id]

            factory = self._factories.get(session_info.session_mode)
            if not factory:
                logging.error(f"No factory found for session mode: '{session_info.session_mode}'")
                return None
            
            updater = functools.partial(self._update_session_config, session_info.session_id)
            try:
                chat_service = factory.create_service(session_info=session_info, llm=Settings.llm, config_updater=updater)
                self._active_chats[session_info.session_id] = chat_service
                return chat_service
            except Exception as e:
                logging.error(f"Factory failed to create service for session {session_info.session_id}: {e}", exc_info=True)
                return None

    def _update_session_config(self, session_id: str, new_config_data: Dict[str, Any]):
        """
        [执行者] 这是实际执行配置更新和持久化的方法
        """
        with self._lock:
            # 找到对应的用户和会话
            for user in self._users.values():
                session = user.sessions.get(session_id, None)
                if session:
                    # 更新 config 字典
                    session.config.update(new_config_data)
                    logging.info(f"Session {session_id} config updated with: {new_config_data}")
                    # 持久化
                    self._save_user_profile(user.user_id)
                    return
            logging.warning(f"Attempted to update config for non-existent session: {session_id}")