#!/usr/bin/env python3

import numpy as np
import pandas as pd
import os, sys, inspect
import configparser
from datetime import datetime

class Prophet:
  def __init__(self, ticker, inifile='./conf/prophet.ini', env='default', debug=5, logfile='log/prophet.log'):
    """instantiate the object"""
    self.env = env #something like dev, staging, prod, whatever
    self.ticker = ticker
    self.logfile = logfile #using local default location for the logs since I might not have permissions towrite in your /var/log
    self.logfile = logfile
    self.debug = debug

    if (os.path.isfile(inifile) != True):
      error = "Config file does not exist: %s" % inifile
      self.log(error)
      raise Exception(error)

    self.config = configparser.ConfigParser()
    try:
      self.config.read(inifile)
    except:
      error = "failed to read %s" % inifile
      self.log(error)
      raise Exception(error)

    return

  def log(self, msg):
    """log a message in the app logfile, just to avoid installing logging"""
    try:
      with open(self.logfile, "a") as filehandle_log:
        filehandle_log.write("%s: %s\n" % (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), msg))
    except:
      raise Exception('Can not write to the log file:', self.logfile)
    return 0

  def parse_template(self, file_template, dict_content):
    if not os.path.exists(file_template):
      return "template file %s does not exist" % file_template

    with open(file_template, "r") as handle_template:
      string_template = handle_template.read()
      #print "file_template", file_template,
      #print "string_template", string_template
      #print (dict_content)
      #string_html = string_template % dict_content
      string_html = string_template.format(**dict_content) #send in as kwargs
      print ("parsed: ", len(string_html))
      return string_html


