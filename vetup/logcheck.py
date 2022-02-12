#!/usr/bin/env python

import os
import dotenv
from pathlib import Path
import re
import sys
import json
from datetime import date, datetime, timedelta


dotenv.load_dotenv()

import vulogging
logger = vulogging.getLogger("index")

from enum import Enum
from dataclasses import dataclass



@dataclass
class Message:
    class LEVEL(Enum):
        INFO = ('info', '\033[0m', 'text-dark')
        ERROR = ('error', '\033[31m', 'text-danger') # red
        WARN = ('warn', '\033[33m', 'text-warning') # orange
        
        def __init__(self, name, ascii, html=""):
            self.ascii = ascii
            self.html = html
    
    TYPE = Enum("TYPE", "H1 H2 MSG")
    msg: str = ""
    typ: TYPE = TYPE.MSG
    level: LEVEL = LEVEL.INFO


def check_logs(n_days=1):
    msgs = []
    msgs += check_nginx_logs(n_days)
    msgs += check_gunicorn_logs(n_days)
    return msgs

def check_nginx_logs(n_days=1):
    
    msgs = []
    nginx_logdir = Path(os.getenv("VU_NGINX_LOG_DIR"))
    
    logpath = nginx_logdir.joinpath("access.log.1").resolve()
    msgs += check_nginx_log(logpath, n_days)
    
    logpath = nginx_logdir.joinpath("access.log").resolve()
    msgs += check_nginx_log(logpath, n_days)

    return msgs

def check_nginx_log(logpath, n_days=1):
    n_days_td = timedelta(days=n_days)
    msgs = []
    
    msgs.append(Message(f"Checking log {logpath}", Message.TYPE.H2))

    if (not logpath.exists()):
        msgs.append(Message("nginx access log does not exist: {}".format(logpath), level=Message.LEVEL.ERROR))
        return msgs
    
    status_count = {}
    req_count = 0
    with logpath.open("r") as log:
        for line in log:
            match = re.search(r'(?P<ipaddr>[\d\.]+) - - \[(?P<timestr>[^\]]*)] "(?P<query>[^"]*)" (?P<status>\d+) (?P<bytes>\d+) "(?P<referrer>[^"]*)" "(?P<agent>[^"]*)"', line)
            if match:
                time = datetime.strptime(match.group('timestr'), "%d/%b/%Y:%H:%M:%S %z")
                if (time.date() > date.today() - n_days_td):
                    status = int(match.group('status'))
                    status_count[status] = status_count.get(status, 0) + 1
                    req_count += 1
                    if (status >=500 and status < 600): 
                        msgs.append(Message(line.rstrip(), level=Message.LEVEL.ERROR))
                    elif (status >= 400 and status < 500):
                        if (not ( status == 404 and  'favicon.ico' in match.group('query'))):
                            msgs.append(Message(line.rstrip(), level=Message.LEVEL.WARN))

    msgs.append(Message(f"Summary: {req_count} requests; statuses: {status_count}"))
    return msgs

def check_gunicorn_logs(n_days=1):
    msgs = []
    
    logdir = Path(os.getenv("VU_PROJECT_DIR")).joinpath("logs")
    logpath = logdir.joinpath("gunicorn.log.1")
    msgs += check_gunicorn_log(logpath, n_days)
    logpath = logdir.joinpath("gunicorn.log")
    msgs += check_gunicorn_log(logpath, n_days)
    
    return msgs

def check_gunicorn_log(logpath, n_days=1):
    n_days_td = timedelta(days=n_days)
    msgs = []
    
    msgs.append(Message(f"Checking log {logpath}", Message.TYPE.H2))
    if (not logpath.exists()):
        msgs.append(Message("gunicorn access log does not exist: {}".format(logpath), level=Message.LEVEL.ERROR))
        return msgs
    
    with logpath.open("r") as log:        
        multiline_msg = None
        for line in log:
            if (multiline_msg is not None and not line.startswith("[")):
                multiline_msg.msg += line
            else:  
                if multiline_msg is not None: multiline_msg.msg = multiline_msg.msg.rstrip()
                multiline_msg = None
                match = re.search(r'\[(?P<timestr>[^\]]*)\] \[(?P<pid>\d+)\] \[(?P<level>\w+)\] (?P<msg>.*)\n', line)
                if match:
                    time = datetime.strptime(match.group('timestr'), "%Y-%m-%d %H:%M:%S %z")
                    print(match.groups())
                    if (time.date() > date.today() - n_days_td):
                        if (match.group('level') != 'INFO'):
                            multiline_msg = Message(line, level=Message.LEVEL.ERROR)
                            msgs.append(multiline_msg)
                else:
                    match = re.search(r'\[(?P<timestr>[^\],]*)(?:,\d*)?\] (?P<msg>.*)\n', line)
                    if match:
                        time = datetime.strptime(match.group('timestr'), "%Y-%m-%d %H:%M:%S")
                        if (time.date() > date.today() - n_days_td):
                            multiline_msg = Message(line, level=Message.LEVEL.ERROR)
                            msgs.append(multiline_msg)

                        
    return msgs
                

if __name__ == "__main__":
#    parser = argparse.ArgumentParser(description='Index decisions')
#    parser.add_argument('dirs', nargs='+', help="one or more directories containing files to be processed; these will be searched recursively")
#    args = parser.parse_args()

    
    msgs = check_nginx_logs()

    msgs = msgs + check_gunicorn_logs()
    
    for msg in msgs:
        if (msg.typ != msg.TYPE.MSG):
            print()

        pre = msg.level.ascii
        post = msg.LEVEL.INFO.ascii
        print(f"{pre}{msg.msg}{post}")
        if (msg.typ == msg.TYPE.H1):
            print("=" * 80)
        elif (msg.typ == msg.TYPE.H2):
            print("-" * 80)
    
