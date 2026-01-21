
from datetime import datetime

def log(*args, **kwargs):
    ts = datetime.utcnow().isoformat()
    print('[FFTECH]', ts, *args, kwargs if kwargs else '')
