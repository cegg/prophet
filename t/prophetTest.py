import os
import sys
import inspect
import datetime

import unittest
from contextlib import closing

currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
libdir = os.path.dirname(currentdir) + '/lib'
sys.path.insert(0, libdir)

default_config = os.path.dirname(currentdir) + '/conf/prophet.ini'

class prophetTest(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.test = prophet(default_config, 'default')

    def test_init(self):
        self.assertTrue(isinstance(self.test, prophet), 'init')

    def test_log(self):

        self.assertTrue(self.test.log(0, 'test message') == 0)
        self.assertTrue(self.test(1000, 'test message two') == 1)

    def test_check_flask(self):
        started = datetime.datetime.now()
        self.test.log_started(started)
        last_started = self.test.get_last_started()
        self.assertTrue(last_started == started.replace(microsecond=0), 'check valid timestamp')
        self.test.log_started()
        last_started = self.tm.get_last_started()
        self.assertTrue('?????' == '?????')

    def test_get_panel(self):
        self.assertTrue('?????' == '?????')

if __name__ == '__main__':
    unittest.main()
