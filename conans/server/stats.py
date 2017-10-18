""" Implement as a trigger of a request has the following problems:

a) Several workers could produce several calls, to control it you have to create a lock in a file
b) If there are connectivity problems, it could block ALL the workers waiting to the first one to end
c) Delay in every request, even in the best case

Better to launch a thread, and not blocking.
"""
import datetime
import functools
import json
import os
import platform
import sys
import threading
import time

import fasteners
import requests
import schedule

from conans import __version__ as conan_version
from conans.tools import get_mac_digest
from conans.util.files import save


def catch_exceptions(job_func):
    @functools.wraps(job_func)
    def wrapper(*args, **kwargs):
        try:
            return job_func(*args, **kwargs)
        except Exception as exc:
            pass
    return wrapper


class CallHomeScheduler(object):

    def __init__(self, path_config, interval_check=None, interval_send=None):
        self.path_config = path_config
        self.interval_check = interval_check or datetime.timedelta(minutes=60)
        self.interval_send = interval_send or datetime.timedelta(hours=24)

    @catch_exceptions
    def tick(self):
        # Read file, blocking (many workers could concur), check if we need to send
        # If true, send and update the file, if false, unlock and exit
        with fasteners.InterProcessLock(self.path_config + ".lock"):
            if not os.path.exists(self.path_config):
                save(self.path_config, "")
            with open(self.path_config) as the_file:
                last_time_sent = the_file.read()

            now = int(time.time())
            if not self._is_valid_past_timestamp(last_time_sent):
                last_time_sent = None

            if not last_time_sent:
                self._send_metrics(now, now)
            else:
                if (now - int(last_time_sent)) > self.interval_send.total_seconds():
                    self._send_metrics(last_time_sent, now)

    @staticmethod
    def _is_valid_past_timestamp(the_str):
        if len(the_str) != 10:
            return False
        return time.time() >= int(the_str)

    def _send_metrics(self, last_sent, now):
        data = self._get_data(last_sent, now)
        data = json.dumps(data)
        requests.post('https://api.bintray.net/products/conan/conan_server/stats/usage',
                      data=data)
        save(self.path_config, str(now))

    @staticmethod
    def _get_data(last_sent, now):

        def format_date(ts):
            return datetime.datetime.utcfromtimestamp(float(ts)).strftime('%Y-%m-%dT%H:%M:%S.000Z')

        last_sent_dt = format_date(last_sent)
        now_dt = format_date(now)

        ret = {
            "product": "conan_server",
            "repository": "PlainInstallers",
            "package": "WinInstaller",
            "version": "1.0",
            "environment": {
                   "conan_version": conan_version,
                   "os": platform.system(),
                   "python_version": sys.version,
                   "service_id": get_mac_digest()
            },
            "Measures": {
                "from_dt": last_sent_dt,
                "now_dt": now_dt,
                "current_num_packages": 22,
                "current_num_recipes": 34
            }
        }

        return ret

    def launch_scheduler(self):

        cease_continuous_run = threading.Event()

        schedule.every(self.interval_check.total_seconds()).seconds.do(self.tick)

        class ScheduleThread(threading.Thread):

            @classmethod
            def run(cls):
                while not cease_continuous_run.is_set():
                    schedule.run_pending()
                    time.sleep(1)  # Each second will awake to check if it needs to run tasks

        continuous_thread = ScheduleThread()
        continuous_thread.start()
