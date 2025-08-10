"""
此模块负责创建和管理大语言模型（LLM）的实例。

它提供了一个中心化的工厂函数 `get_llm_by_name` 来根据名称创建不同的 LLM，
并提供一个初始化函数 `initialize_global_llm` 在应用启动时设置全局默认的 LLM。
"""
import logging
from typing import Any

from llama_index.core import Settings
from llama_index.llms.deepseek import DeepSeek
from llama_index.llms.ollama import Ollama
from llama_index.llms.gemini import Gemini
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

from config import settings

def get_llm_by_name(model_name: str) -> Any:
    """
    LLM 工厂函数，根据提供的模型名称字符串创建并返回一个 LLM 实例。

    支持的模型前缀:
    - 'deepseek-': 使用 DeepSeek API。需要 DEEPSEEK_API_KEY 环境变量。
    - 'ollama/': 使用本地 Ollama 服务。例如 'ollama/qwen2.5'。

    Args:
        model_name (str): 模型的唯一标识符。

    Raises:
        ValueError: 如果模型不受支持或缺少必要的配置（如 API Key）。

    Returns:
        Any: 一个实现了 LlamaIndex LLM 接口的实例。
    """
    logging.info(f"Attempting to create LLM instance for model: '{model_name}'")
    
    if model_name.startswith("deepseek-"):
        api_key = settings.DEEPSEEK_API_KEY
        if not api_key:
            logging.error("DEEPSEEK_API_KEY not found in environment variables.")
            raise ValueError("DeepSeek API key not found in environment variables.")
        return DeepSeek(model=model_name, api_key=api_key)
    
    elif model_name.startswith("ollama/") and settings.USE_OLLAMA:
        # 从 'ollama/qwen2.5' 中提取 'qwen2.5'
        _, ollama_model_name = model_name.split("/", 1)
        if not ollama_model_name:
            raise ValueError("Ollama model name cannot be empty. E.g., 'ollama/qwen2.5'")
        # 假设 Ollama 服务正在本地运行
        return Ollama(model=ollama_model_name)
    
    elif model_name.startswith("gemini-"):
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            logging.error("GEMINI_API_KEY not found in environment variables.")
            raise ValueError("Gemini API key not found in environment variables.")
        # 允许用户以 gemini-pro, gemini-1.5-pro-001 等方式指定模型
        return Gemini(model=model_name, api_key=api_key)
    
    else:
        # 如果未来支持更多模型，可以在这里添加 elif 分支
        logging.error(f"Unsupported model prefix for: '{model_name}'")
        raise ValueError(f"Unsupported model: '{model_name}'. Supported prefixes: 'deepseek-', 'ollama/', 'gemini-' ")


def initialize_global_llm() -> None:
    """
    在应用程序启动时，初始化一个全局默认的 LLM 实例。

    这个函数会根据 `config/settings.py` 中的 `USE_OLLAMA` 配置
    来决定是使用 Ollama还是 DeepSeek 作为默认模型，并将其设置到
    `llama_index.core.Settings.llm` 中，供项目中所有依赖全局设置的地方使用。

    Raises:
        RuntimeError: 如果在初始化过程中发生严重错误（如配置缺失）。
    """
    try:
        # 优先级：Ollama > Gemini > DeepSeek
        if settings.USE_OLLAMA:
            default_model = "ollama/qwen2.5"
        elif settings.GEMINI_API_KEY:
            default_model = "gemini-2.5-flash"
        else:
            default_model = "deepseek-chat"
        
        logging.info(f"Initializing global default LLM with: '{default_model}'")
        
        # 使用工厂函数创建实例
        llm_instance = get_llm_by_name(default_model)
        
        # 设置为 LlamaIndex 的全局 LLM
        Settings.llm = llm_instance
        
        logging.info("Global default LLM has been successfully initialized.")

        embed_model = HuggingFaceEmbedding(model_name="all-MiniLM-L6-v2")
        Settings.embed_model = embed_model

    except ValueError as e:
        # 将配置或实例化错误包装成一个更严重的运行时错误，因为这会导致应用无法启动
        raise RuntimeError(f"Fatal error during LLM initialization: {e}")