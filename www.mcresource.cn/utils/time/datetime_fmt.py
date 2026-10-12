from datetime import datetime

def now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def today():
    return datetime.now().strftime('%Y-%m-%d')