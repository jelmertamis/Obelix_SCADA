import time
from obelix.config import Config

log_messages = []

def log(msg):
    ts = time.strftime('%H:%M:%S')
    entry = f'[{ts}] {msg}'
    log_messages.append(entry)
    if len(log_messages) > Config.MAX_LOG:
        del log_messages[:-Config.MAX_LOG]
    print(entry)