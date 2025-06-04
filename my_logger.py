import logging

_logger = None

def init_logger(log_file_path=None):
    global _logger
    _logger = logging.getLogger("crawler")
    _logger.setLevel(logging.INFO)

    formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s')

    handlers = [logging.StreamHandler()]
    if log_file_path:
        handlers.append(logging.FileHandler(log_file_path, mode='w', encoding='utf-8'))

    for handler in handlers:
        handler.setFormatter(formatter)
        _logger.addHandler(handler)

def get_logger():
    global _logger
    if _logger is None:
        raise Exception("Logger chưa được khởi tạo! Vui lòng gọi init_logger() trước.")
    return _logger
