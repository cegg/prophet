#!/usr/bin/env python3

import numpy as np
import pandas as pd
import os, sys, inspect
import configparser
from datetime import datetime

class Prophet:
  def __init__(self, ticker, days, inifile='./conf/prophet.ini', env='default', debug=5, logfile='log/prophet.log'):
    """instantiate the object"""
    self.env     = env #environment - for the future, to acess different sections of ino files or diferent cloud envs (something like dev, staging, prod, whatever
    self.ticker  = ticker
    self.days    = days
    self.logfile = logfile #using local default location for the logs since I might not have permissions towrite in your /var/log
    self.logfile = logfile
    self.debug   = debug

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
      #print ("parsed: ", len(string_html))
      return string_html

  def enrich(self, df):

    df['Spread']       = df['High'] - df['Low']
    df['Yield']        = df['Close'] - df['Open']
    #df['Yield Avg']    = df['Yield'] #TODO figure out why setting to zero breaks calculations below
    df['Yield % Open'] = df['Yield']
    #df['Yield % Open 3'] = df['Yield']

    days = self.days

   #  for counter, val in enumerate (df_temp['Yield']):
   #    z = generate_series_yield(df_temp)

    # print ("ZZZ: ", z)

    for counter, val in enumerate (df['Open']):
      if counter < days: #starting days that are used for calculating things for the following days but do not have predecessors to do produce preditions of their own
        #df['Yield Avg'][counter] = 0
        df['Yield % Open'][counter] = 0
        #df['Yield % Open 3'][counter] = 0
        continue

      #get avg yield (amount and percent) for three previous days
      #print (counter-days, counter-1, df['Yield'][counter-days:counter-1].sum() / days)
      #df['Yield Avg'][counter]      = round (df['Yield'][counter-days:counter-1].sum() / days, 2)
      df['Yield % Open'][counter]   = round (df['Yield'][counter] / df['Open'][counter]*100, 4)
      #this one below is not getting calculated correctly
      #df['Yield % Open 3'][counter] = round (df['Yield % Open'][counter-days:counter-1].sum() / days, 6)
      #print ("range: ", df['Yield % Open'][counter-days:counter-1], "sum:", df['Yield % Open'][counter-days:counter-1].sum(), "sum/3:", df['Yield % Open'][counter-days:counter-1].sum() / days)
      if counter > 50: #debug #TODO!!! REMEMBER TO REMOVE!!!
        break


    return df

  def set_tiers(self, df, column_names=('Yield % Open',)):
    """assigns values of numeric columns to one of 3 tiers: high, medium, low to generate HMM strings"""
    dict_tiers = {}

    for column_name in (column_names):
      if (df[column_name].dtype == np.float64 or df[column_name].dtype == np.int64): #check once per column_name
        dict_tiers[column_name] = {}
        dict_tiers[column_name]['min'] = df[column_name].min() #assign these two once per column_name
        dict_tiers[column_name]['max'] = df[column_name].max()
        dict_tiers[column_name]['one_third'] = (dict_tiers[column_name]['max'] - dict_tiers[column_name]['min'])/3
        #for day in range(1, self.days+1): #mini-generator :-)
        dict_tiers[column_name]['tier_low_top' ]   = round(dict_tiers[column_name]['min'] + dict_tiers[column_name]['one_third'], 4)
        dict_tiers[column_name]['tier_medium_top'] = round(dict_tiers[column_name]['min'] + dict_tiers[column_name]['one_third']*2, 4)
        dict_tiers[column_name]['tier_high_top']   = round(dict_tiers[column_name]['max'])

        #print('column_name: ', column_name, 'min-max', dict_tiers[column_name]['min'], dict_tiers[column_name]['max'])
    return dict_tiers

  def set_hmm_state(self, df, source_key, target_key1, target_key2, target_key3, dict_tiers_source):
    target_column1 = df[target_key1]
    target_column2 = df[target_key2]
    target_column3 = df[target_key3]
    counters = {}
    for counter, record in enumerate(df[source_key]):
      # if counter > 50: #TODO REMOVE!!!
      #   break


      #State
      target_column2[counter] = set_days_state([df[source_key][counter],], dict_tiers_source)
      if counter < self.days: #starting days that are used for calculating things for the following days but do not have predecessors to do produce preditions of their own
        continue

      #History
      target_column1[counter] = set_days_state(df[source_key][counter-self.days:counter], dict_tiers_source) #counter in the range means counter-1
      if target_column1[counter] not in counters: #maybe not pythonic, but try /except would have to do the same assignment
        counters[target_column1[counter]] = {}

      if target_column1[counter] not in counters[target_column1[counter]]:
        counters[target_column1[counter]][target_column2[counter]] = 0

      counters[target_column1[counter]][target_column2[counter]] += 1
      #pull out the most popular next entry for a given HMM
      target_column3[counter] =  max(counters[target_column1[counter]], key=counters[target_column1[counter]].get)
      if target_column3[counter] == target_column2[counter]:
        df['Check'][counter] = 'OK'

      #TODO: introduce predicted price column



    return target_column1, target_column2, target_column3


def set_days_state(day_range, dict_tiers_source):
  day_states = []
  for day_record in day_range:
    if (day_record < dict_tiers_source['tier_low_top']):
      day_state = 'L' #low
    elif (day_record < dict_tiers_source['tier_medium_top']):
      day_state = 'M' #medium
    else:
      day_state = 'H' #high

    day_state = '+' + day_state if (day_record > 0) else ('-' + day_state)
    day_states.append(day_state)
  return '|'.join(day_states)


def generate_series_yield(df, counter, days):
  yield round (df['Yield'][counter-days:counter-1].sum() / days, 2)
