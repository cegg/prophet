#!/usr/bin/env python3

import numpy as np
import pandas as pd
import os, sys, inspect
import configparser #for .ini file
from datetime import datetime

class Prophet:
  def __init__(self, ticker, days, inifile='./conf/prophet.ini', env='default', debug=5, logfile='log/prophet.log'):
    """instantiate the object"""
    self.env     = env #environment - for the future, to acess different sections of ini files or diferent cloud envs (something like dev, staging, prod, whatever
    self.ticker  = ticker
    self.days    = days
    self.logfile = logfile #using local default location for the logs since I might not have permissions towrite in your /var/log
    self.logfile = logfile
    self.debug   = debug #level of verbosity for the screen output and logging; not used so far

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
      string_html = string_template.format(**dict_content) #send it in as kwargs
      #print ("parsed: ", len(string_html))
      return string_html

  def enrich(self, df):
    """"set derived columns of 'Spread', 'Yield', 'Yield % Open' for further calculations"""

    df['Yield']        = df['Close'] - df['Open']
    #s = pd.Series(generate_new_column(func_diff, df['Close'], df['Open'])) #subtraction does not work inside generator
    #df['Yield'] = s

    #TODO think how Spread can be added to the model
    # df['Spread']       = df['High'] - df['Low']

    #df['Yield Avg']    = df['Yield'] #TODO figure out why setting to zero breaks calculations below

    df['Yield % Open'] = df['Yield']

    days = self.days

    for counter, val in enumerate (df['Open']):
      if counter < days: #starting days that are used for calculating things for the following days but do not have predecessors to do produce preditions of their own
        #df['Yield Avg'][counter] = 0 #avg yield for <days> previous days
        df['Yield % Open'][counter] = 0
        continue

      #get avg yield (amount and percent) for three previous days
      #df['Yield Avg'][counter]      = round (df['Yield'][counter-days:counter-1].sum() / days, 2)
      df['Yield % Open'][counter]   = round (df['Yield'][counter] / df['Open'][counter]*100, 4)
      #print ("range: ", df['Yield % Open'][counter-days:counter-1], "sum:", df['Yield % Open'][counter-days:counter-1].sum(), "sum/3:", df['Yield % Open'][counter-days:counter-1].sum() / days)
      # if counter > 50: #debug #TODO!!! REMEMBER TO REMOVE!!!
      #   break


    return df

  def set_tiers(self, df, column_names=('Yield % Open',)):
    """assigns values of numeric columns to one of 3 tiers: high, medium, low to generate HMM strings"""
    dict_tiers = {}

    for column_name in (column_names):
      if (df[column_name].dtype == np.float64 or df[column_name].dtype == np.int64): #check once per column_name
        dict_tiers[column_name] = {}
        dict_tiers[column_name]['min'] = df[column_name].min() #assign these two once per column_name
        dict_tiers[column_name]['max'] = df[column_name].max()
        #TODO: try on <days> range instead of the whole column
        dict_tiers[column_name]['one_third'] = (dict_tiers[column_name]['max'] - dict_tiers[column_name]['min'])/3
        dict_tiers[column_name]['tier_low_top' ]   = round(dict_tiers[column_name]['min'] + dict_tiers[column_name]['one_third'], 4)
        dict_tiers[column_name]['tier_medium_top'] = round(dict_tiers[column_name]['min'] + dict_tiers[column_name]['one_third']*2, 4)
        dict_tiers[column_name]['tier_high_top']   = round(dict_tiers[column_name]['max'])

        dict_tiers[column_name]['tier_low_mean'] = round((dict_tiers[column_name]['tier_low_top'] - dict_tiers[column_name]['min'])/2, 2)
        dict_tiers[column_name]['tier_medium_mean'] = round((dict_tiers[column_name]['tier_medium_top'] - dict_tiers[column_name]['tier_low_top'])/2, 2)
        dict_tiers[column_name]['tier_high_mean'] = round((dict_tiers[column_name]['tier_high_top'] - dict_tiers[column_name]['tier_medium_top'])/2, 2)
        print (dict_tiers[column_name]['tier_high_top'], dict_tiers[column_name]['tier_medium_top'], dict_tiers[column_name]['tier_high_mean'])

        #print('column_name: ', column_name, 'min-max', dict_tiers[column_name]['min'], dict_tiers[column_name]['max'])
    return dict_tiers

  def set_hmm_state(self, df, source_key, target_key2, dict_tiers_source):
    df['History'] = ''
    df['Tier Guess'] = ''
    df['Match'] = ''
    target_column2 = df[target_key2]
    counters = {}
    for counter, record in enumerate(df[source_key]):
      # if counter > 50: #TODO REMOVE!!!
      #   break

      #actual state (even tier0)
      target_column2[counter] = set_days_state([df[source_key][counter],], dict_tiers_source)
      if counter < self.days: #starting days that are used for calculating things for the following days but do not have predecessors to do produce preditions of their own
        continue

      #History of <days> days
      df['History'][counter] = set_days_state(df[source_key][counter-self.days:counter], dict_tiers_source) #counter in the range means counter-1
      if df['History'][counter] not in counters: #maybe not pythonic, it's not an exception, so no try /except
        counters[df['History'][counter]] = {}

      if target_column2[counter] not in counters[df['History'][counter]]:
        counters[df['History'][counter]][target_column2[counter]] = 0

      counters[df['History'][counter]][target_column2[counter]] += 1 #keep track of frequency
      #pull out the most popular next entry for a given HMM
      df['Tier Guess'][counter] =  max(counters[df['History'][counter]], key=counters[df['History'][counter]].get)
      if df['Tier Guess'][counter] == target_column2[counter]:
        df['Match'][counter] = 'OK'

      if df['Tier Guess'][counter][0] == target_column2[counter][0]:
        df['Up/Down Guess'][counter] = 'OK'

      df['Price Guess'][counter] = df['Close'][counter-1]
      if df['Tier Guess'][counter][-1] == 'L':
        df['Price Guess'][counter] += dict_tiers_source['tier_low_mean']
      elif df['Tier Guess'][counter][-1] == 'M':
        df['Price Guess'][counter] += dict_tiers_source['tier_medium_mean']
      elif df['Tier Guess'][counter][-1] == 'H':
        df['Price Guess'][counter] += dict_tiers_source['tier_high_mean']

    return target_column2


def set_days_state(day_range, dict_tiers_source):
  """ for each day  in the input define HMM symbol, e.g. +M (up medium) or -H (down high), and concatenate them into HMM.
  Works on single day as well"""

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

# def generate_new_column(func, column1, column2):
#   """a generator for various calculations"""
#   zz = []
#   for counter, x in column1:
#     print(x, y, type(x), type(y))
#     z = func(x, y)
#     zz.append(z)
#     #yield float(z)
#   return zz



def generate_new_column(func, column1, column2):
  """a generator for various calculations"""
  yield func(column1, column2)

  # zz = []
  # for x, y in zip(column1, column2):
  #   print(x, y, type(x), type(y))
  #   #z = func(x, y)
  #   z = x-y
  #   zz.append(z)
  #   #yield float(z)
  # return zz

def func_diff(x, y):
  return x-y
  # #x = np.asscalar(x)
  # #y = np.asscalar(y)
  # print ("func: ", (x-y))
  # return float(x-y)
  # #return np.subtract(x,y)
  # #return (x-y)

