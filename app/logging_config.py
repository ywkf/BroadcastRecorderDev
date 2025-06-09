# app/logging_config.py
import logging
import os
import time
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler

def setup_logging():
    """统一日志配置（按日期命名文件 + 自动轮转）"""
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    LOGS_DIR = os.path.join(BASE_DIR, 'logs')
    os.makedirs(LOGS_DIR, exist_ok=True)

    # 按日期命名的日志文件（每日一个独立文件）
    log_filename = f"radio_recorder_{datetime.now().strftime('%Y-%m-%d')}.log"
    log_filepath = os.path.join(LOGS_DIR, log_filename)

    # 日志格式
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 文件处理器（每天自动创建新文件）
    file_handler = logging.FileHandler(log_filepath, encoding='utf-8')
    file_handler.setFormatter(formatter)

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # 全局配置
    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[console_handler, file_handler]
    )

    # 添加午夜自动切换（确保跨日期时创建新文件）
    def midnight_rollover():
        nonlocal file_handler
        file_handler.close()
        new_filename = f"radio_recorder_{datetime.now().strftime('%Y-%m-%d')}.log"
        file_handler = logging.FileHandler(
            os.path.join(LOGS_DIR, new_filename),
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        logging.getLogger().removeHandler(file_handler)
        logging.getLogger().addHandler(file_handler)

    # 模拟午夜检查（实际项目可用APScheduler等定时任务）
    import threading
    def schedule_midnight_check():
        while True:
            now = datetime.now()
            if now.hour == 0 and now.minute == 0:
                midnight_rollover()
            time.sleep(60)

    threading.Thread(target=schedule_midnight_check, daemon=True).start()

# 初始化日志配置
setup_logging()

def get_logger(name=__name__):
    """获取已配置的logger"""
    return logging.getLogger(name)
