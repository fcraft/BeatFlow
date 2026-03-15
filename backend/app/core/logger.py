"""日志配置"""
import logging
import sys
from typing import Any, Dict

from pythonjsonlogger import jsonlogger
from app.core.config import settings


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """自定义JSON日志格式化器"""
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
        """添加额外字段"""
        super().add_fields(log_record, record, message_dict)
        
        # 添加应用信息
        log_record["app_name"] = settings.APP_NAME
        log_record["app_env"] = settings.APP_ENV
        
        # 添加时间戳
        log_record["timestamp"] = record.created
        
        # 添加日志级别
        log_record["severity"] = record.levelname
        
        # 添加文件名和行号
        if record.pathname:
            log_record["file"] = record.pathname
        if record.lineno:
            log_record["line"] = record.lineno
        
        # 处理异常信息
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)


def setup_logging():
    """设置日志配置"""
    # 创建根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.LOG_LEVEL.upper())
    
    # 清除现有处理器
    root_logger.handlers.clear()
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    
    # 根据配置选择格式化器
    if settings.LOG_FORMAT.lower() == "json":
        formatter = CustomJsonFormatter(
            "%(timestamp)s %(severity)s %(app_name)s %(module)s %(funcName)s %(message)s"
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # 设置第三方库日志级别
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)
    
    return root_logger


# 全局日志记录器
logger = logging.getLogger(__name__)