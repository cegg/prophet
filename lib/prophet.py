#!/usr/bin/env python3

import numpy as np
import pandas as pd
import os, sys, inspect
import configparser #for .ini file
from datetime import datetime
import random

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
    """get html template to feed the assigned data to"""
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
        #print (dict_tiers[column_name]['tier_high_top'], dict_tiers[column_name]['tier_medium_top'], dict_tiers[column_name]['tier_high_mean'])

        #print('column_name: ', column_name, 'min-max', dict_tiers[column_name]['min'], dict_tiers[column_name]['max'])
    return dict_tiers

  def set_hmm_state(self, df, source_key, dict_tiers_source):
    """assign actual state from historicaldata (up/down and tier char) for the record, e,g, +M"""
    df['History'] = ''
    df['Tier Guess'] = ''
    df['Match'] = ''
    counters = {}
    for counter, record in enumerate(df[source_key]):
      # if counter > 50: #TODO REMOVE!!!
      #   break

      #actual state
      df['Tier'][counter] = set_days_state([df[source_key][counter],], dict_tiers_source)

      #History of <days> days
      df['History'][counter] = set_days_state(df[source_key][counter-self.days:counter], dict_tiers_source) #counter in the range means counter-1
      if df['History'][counter] not in counters: #maybe not pythonic, but it's not an exception, so no try /except
        counters[df['History'][counter]] = {}

      if df['Tier'][counter] not in counters[df['History'][counter]]:
        counters[df['History'][counter]][df['Tier'][counter]] = 0

      if counter < self.days: #starting days that are used for calculating things for the following days but do not have predecessors to do produce preditions of their own
        continue

      counters[df['History'][counter]][df['Tier'][counter]] += 1 #keep track of frequency
      if not set_guesses(df, counters, counter, dict_tiers_source):
        continue

    #backpropagate later-set assumptions  - if we want to use all date range as one unit, i.e. not only chronologically sequencial assumptions
    #can be commented out for the case of only causal chronology
    for counter, record in enumerate(df[source_key]):
      if counter < self.days:
        continue
      if not set_guesses(df, counters, counter, dict_tiers_source):
        continue

    return

def set_guesses(df, counters, counter, dict_tiers_source):
  """set 'Tier Guess', 'Up/Down Guess', and 'Price Guess' columns"""
  #pull out the most popular next entry for a given HMM
  #e.g. '-M|+M|-M': {'+M': 15, '-M': 11, '-L': 1} would return '+M'
  #e.g. '+H|+H|+H': {'-L': 1} would return return 'no data' - a single occurence, does nto influence anything besides itself
  #e.g. '-L|+H|-M': {'+M': 1, '-M': 1} - if curent record had +M, then returns the other one ( -M)
  #e.g. '-L|+H|-M': {'+M': 1, '-M': 1, '+L': 1} - returns randomly selected out of all excluding current record pattern, i.e if current record is '+M' it's randomly selected from the other two
  #print ("\n<======", counters[df['History'][counter]], "======>")
  list_counter_value = list(counters[df['History'][counter]].values())

  if len(list_counter_value) == 0:
    #nothing assigned so far, set default and keep looping
    df['Tier Guess'][counter] = 'no data'
    #print ("CASE 1 no data so far, SKIPPING")
    return
  elif len(list_counter_value) == 1:
    if list_counter_value[0] == 1:
      #just one entry of 1, which means current record itself, should be ignored
      df['Tier Guess'][counter] = 'no data'
      #print ("CASE 2 one entry, ==1, SKIPPING")
      return
    else:
      #good data but one entry, well, just use it
      df['Tier Guess'][counter] = list(counters[df['History'][counter]].keys())[0] #in python3 needs to be 'list'ed because it's an object now
      #print ("CASE 3, one entry, good data, set to ", df['Tier Guess'][counter])
  elif check_all_values_equal(list_counter_value): #more than one entry but all counters are equal
    #if counters are higher than 1, take the most recent one, otherwise consider no data
    if list_counter_value[0] == 1:
      #print ("CASE 4, more than one and all equal and ==1, choosing randomly from non-current: ", list_counter_value)
      dict_temp = counters[df['History'][counter]].copy()
      del dict_temp[df['Tier'][counter]]
      df['Tier Guess'][counter] = random.choice(list(dict_temp.keys()))
    else: #there is some inconclusive statistics here, let's select one randomly. That probably will break a lot of ties further down the loop
      #TODO: maybe assign to the tier that is close the latest entry in the HMM instead?
      df['Tier Guess'][counter] = random.choice(list(counters[df['History'][counter]].keys())) #call list on the returned object in python3
      #print ("CASE 5, more than one and all equal but greater than 1, choosing randomly from : ", list_counter_value, "vinner:", df['Tier Guess'][counter])
  else:
    #good, substantial data to make a decision
    df['Tier Guess'][counter] =  max(counters[df['History'][counter]], key=counters[df['History'][counter]].get)
    #print ("CASE 6: winner: ", df['Tier Guess'][counter])

  if df['Tier Guess'][counter] == df['Tier'][counter]:
    df['Match'][counter] = 'OK'

  if df['Tier Guess'][counter][0] == df['Tier'][counter][0]:
    df['Up/Down Guess'][counter] = 'OK'

  df['Price Guess'][counter] = df['Close'][counter-1]
  if df['Tier Guess'][counter][-1] == 'L':
    df['Price Guess'][counter] += dict_tiers_source['tier_low_mean']
  elif df['Tier Guess'][counter][-1] == 'M':
    df['Price Guess'][counter] += dict_tiers_source['tier_medium_mean']
  elif df['Tier Guess'][counter][-1] == 'H':
    df['Price Guess'][counter] += dict_tiers_source['tier_high_mean']
  return 1

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

def check_all_values_equal(list_values):
  """detect if all prediction tier HMM happened to have the same count"""
  return list_values[1:] == list_values[:-1]


# does not work - returns NaN no matter how the input data is formatted
# def generate_new_column(func, column1, column2):
#   """a generator for various calculations"""
#   yield func(column1, column2)

# def func_diff(x, y):
#   return x-y


