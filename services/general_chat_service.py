import logging
from typing import Any, Optional
from llama_index.core.llms import ChatMessage

from core.interfaces import IChatService
# 注意：这个服务可以不依赖 RAG，或者使用一个通用的 KnowledgeBase
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.storage.chat_store import SimpleChatStore
from pathlib import Path
from config.settings import CHAT_HISTORY_PATH

class GeneralChatService(IChatService):
    """
    一个通用的、无角色设定的聊天服务，支持持久化聊天记录。
    """
    DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant."
    
    def __init__(self, session_id: str, llm: Any, system_prompt_template: Optional[str] = None):
        self.session_id = session_id
        self.llm = llm
        self.system_prompt = system_prompt_template or self.DEFAULT_SYSTEM_PROMPT
        
        self._setup_storage()
        self.chat_mem = ChatMemoryBuffer.from_defaults(
            chat_store=self.chat_store,
            chat_store_key=self.session_id,
            token_limit=20000
        )
        logging.info(f"GeneralChatService for session {session_id} initialized.")

    def _setup_storage(self):
        self.chat_store = SimpleChatStore()
        self.storage_dir = Path(CHAT_HISTORY_PATH)
        self.storage_dir.mkdir(exist_ok=True)

    def _build_prompt(self, message: str) -> list[ChatMessage]:
        history = self.chat_mem.get()
        messages = [
            ChatMessage(role="system", content=self.system_prompt),
            *history[-40:],
            ChatMessage(role="user", content=message)
        ]
        return messages

    def get_response(self, message: str) -> str:
        messages = self._build_prompt(message)
        response = self.llm.chat(messages)
        reply = response.message.content

        self._update_history(message, reply)
        return reply

    def _update_history(self, user_input: str, reply: str):
        self.chat_mem.put_messages([
            ChatMessage(role="user", content=user_input),
            ChatMessage(role="assistant", content=reply)
        ])
        self._save_session()

    def _save_session(self) -> bool:
        if not self.session_id:
            return False
        self.chat_store.persist(self.storage_dir / f"general_{self.session_id}.json")
        return True

    def switch_llm(self, llm: Any) -> None:
        self.llm = llm
