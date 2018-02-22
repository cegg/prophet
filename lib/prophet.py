#!/usr/bin/env python3

import numpy as np
import pandas as pd
import os, sys, inspect
import configparser #for .ini file
from datetime import datetime
import random
import time


class Prophet:
  def __init__(self, ticker, days, inifile='./conf/prophet.ini', env='default', debug=5, logfile='log/prophet.log'):
    """instantiate the object"""
    self.env     = env #environment - for the future, to acess different sections of ini files or diferent cloud envs (something like dev, staging, prod, whatever
    self.ticker  = ticker
    self.days    = days
    self.logfile = logfile #using local default location for the logs since I might not have permissions to write in your /var/log
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

    log_directory = 'log'
    try:
        os.stat(log_directory)
    except:
        os.mkdir(log_directory)

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
    df['#'] = range(len(df))
    df['Yield']        = df['Close'] - df['Open']
    df['Yield % Open']   = round (df['Yield'] / df['Open']*100, 4)
    days = self.days
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

    millisec1 = int(round(time.time() * 1000))

    tier          = []
    history       = []
    tier_guess    = []
    price_guess   = []
    match         = []
    up_down_guess = []
    counter = -1
    for record in df.itertuples():
      counter += 1

      #actual state
      tier_item = set_days_state([df[source_key][counter],], dict_tiers_source)
      tier.append(tier_item)

      history_item = set_days_state(df[source_key][counter-self.days:counter], dict_tiers_source) #counter in the range means counter-1
      history.append(history_item)
      if history_item not in counters: #maybe not pythonic, but it's not an exception, so no try /except
        counters[history_item] = {}

      if tier_item not in counters[history_item]:
        counters[history_item][tier_item] = 0

      #if counter < self.days: #starting days that are used for calculating things for the following days but do not have predecessors to do produce preditions of their own
      #  continue

      close_item_previous = df['Close'][counter-1]
      counters[history_item][tier_item] += 1 #keep track of frequency of current state by previous chain

      # try:
      #   (tier_guess_item, price_guess_item, match_item, up_down_guess_item) = set_guesses(counter, counters, tier_item, history_item, close_item_previous, dict_tiers_source)
      # except:
      #   print('no data case at ' , counter)
      #   tier_guess_item = 'no data'
      #   price_guess_item = 'no data'
      #   match_item = 'no data'
      #   up_down_guess_item = 'no data'
      (tier_guess_item, price_guess_item, match_item, up_down_guess_item) = set_guesses(counter, counters, tier_item, history_item, close_item_previous, dict_tiers_source)

      tier_guess.append(tier_guess_item)
      price_guess.append(price_guess_item)
      match.append(match_item)
      up_down_guess.append(up_down_guess_item)

    df['Tier']    = tier
    df['History'] = history
    df['Tier Guess'] = tier_guess
    df['Price Guess'] = price_guess
    df['Match'] = match
    df['Up/Down Guess'] = up_down_guess
    self.log('set df')
    millisec2 = int(round(time.time() * 1000))
    msg = 'set_hmm_state: %s, %s, %s' % ( millisec1, millisec2, millisec2-millisec1)
    self.log(msg)

    tier_guess    = []
    price_guess   = []
    match         = []
    up_down_guess = []
    #backpropagate later-set assumptions  - if we want to use all date range as one unit, i.e. not only chronologically sequencial assumptions
    #can be commented out for the case of only causal chronology
    #for counter, record in enumerate(df[source_key]):
    counter = -1
    for record in df.itertuples():
      counter += 1
      #if counter < self.days:
      #  continue
      close_item_previous = df['Close'][counter-1]
      tier_item = df['Tier'][counter]
      history_item = df['History'][counter]

      # try:
      #   (tier_guess_item, price_guess_item, match_item, up_down_guess_item) = set_guesses(counter, counters, tier_item, history_item, close_item_previous, dict_tiers_source)
      # except:
      #   print('no data case at ' , counter)
      #   tier_guess_item = 'no data'
      #   price_guess_item = 'no data'
      #   match_item = 'no data'
      #   up_down_guess_item = 'no data'
      (tier_guess_item, price_guess_item, match_item, up_down_guess_item) = set_guesses(counter, counters, tier_item, history_item, close_item_previous, dict_tiers_source)


      tier_guess.append(tier_guess_item)
      price_guess.append(price_guess_item)
      match.append(match_item)
      up_down_guess.append(up_down_guess_item)

    df['Tier']    = tier
    df['History'] = history
    df['Tier Guess'] = tier_guess
    df['Price Guess'] = price_guess
    df['Match'] = match
    df['Up/Down Guess'] = up_down_guess

    return

  def set_hmm_state_v1(self, df, source_key, dict_tiers_source):
    """assign actual state from historicaldata (up/down and tier char) for the record, e,g, +M"""
    df['History'] = ''
    df['Tier Guess'] = ''
    df['Match'] = ''
    counters = {}

    counter = -1
    for record in df.itertuples():
      counter += 1
    #for counter, record in enumerate(df[source_key]):
      # if counter > 50: #TODO REMOVE!!!
      #   break

      # millisec1 = int(round(time.time() * 1000))

      #actual state
      df['Tier'][counter] = set_days_state([df[source_key][counter],], dict_tiers_source)

      # millisec2 = int(round(time.time() * 1000))
      # msg = '111: set_days_state1: %s, %s, %s' % ( millisec1, millisec2, millisec2-millisec1)
      # self.log(msg)

      # millisec1 = int(round(time.time() * 1000))
      #History of <days> days
      df['History'][counter] = set_days_state(df[source_key][counter-self.days:counter], dict_tiers_source) #counter in the range means counter-1
      if df['History'][counter] not in counters: #maybe not pythonic, but it's not an exception, so no try /except
        counters[df['History'][counter]] = {}

      # millisec2 = int(round(time.time() * 1000))
      # msg = '112: set_days_state2: %s, %s, %s' % ( millisec1, millisec2, millisec2-millisec1)
      # self.log(msg)

      if df['Tier'][counter] not in counters[df['History'][counter]]:
        counters[df['History'][counter]][df['Tier'][counter]] = 0

      if counter < self.days: #starting days that are used for calculating things for the following days but do not have predecessors to do produce preditions of their own
        continue

      # millisec1 = int(round(time.time() * 1000))
      counters[df['History'][counter]][df['Tier'][counter]] += 1 #keep track of frequency
      if not set_guesses_old(df, counters, counter, dict_tiers_source):
        continue
      # millisec2 = int(round(time.time() * 1000))
      # msg = '113: set_guesses: %s, %s, %s' % ( millisec1, millisec2, millisec2-millisec1)
      # self.log(msg)

    #millisec1 = int(round(time.time() * 1000))
    #backpropagate later-set assumptions  - if we want to use all date range as one unit, i.e. not only chronologically sequencial assumptions
    #can be commented out for the case of only causal chronology
    #for counter, record in enumerate(df[source_key]):
    counter = -1
    for record in df.itertuples():
      counter += 1
      if counter < self.days:
        continue
      if not set_guesses_old(df, counters, counter, dict_tiers_source):
        continue

    # millisec2 = int(round(time.time() * 1000))
    # msg = 'backpropagate: %s, %s, %s' % ( millisec1, millisec2, millisec2-millisec1)
    # self.log(msg)

    return

def set_guesses(counter, counters, tier_item, history_item, close_item_previuos, dict_tiers_source):
  """set 'Tier Guess', 'Up/Down Guess', and 'Price Guess' columns"""
  #pull out the most popular next entry for a given HMM
  #e.g. '-M|+M|-M': {'+M': 15, '-M': 11, '-L': 1} would return '+M'
  #e.g. '+H|+H|+H': {'-L': 1} would return return 'no data' - a single occurence, does nto influence anything besides itself
  #e.g. '-L|+H|-M': {'+M': 1, '-M': 1} - if curent record had +M, then returns the other one ( -M)
  #e.g. '-L|+H|-M': {'+M': 1, '-M': 1, '+L': 1} - returns randomly selected out of all excluding current record pattern, i.e if current record is '+M' it's randomly selected from the other two
  #print ("\n<======", counters[history_item], "======>")
  list_counter_value = list(counters[history_item].values())

  if len(list_counter_value) == 0:
    #nothing assigned so far, set default and keep looping
    #print ("CASE 1 no data so far, SKIPPING")
    return 'no data', 'no data', 'no data', 'no data'
  elif len(list_counter_value) == 1:
    if list_counter_value[0] == 1:
      #just one entry of 1, which means current record itself, should be ignored
      #print ("CASE 2 one entry, ==1, SKIPPING")
      return 'no data', 'no data', 'no data', 'no data'
    else:
      #good data but one entry, well, just use it
      tier_guess_item = list(counters[history_item].keys())[0] #in python3 needs to be 'list'ed because it's an object now
      #print ("CASE 3, one entry, good data, set to ", tier_guess_item)
  elif check_all_values_equal(list_counter_value): #more than one entry but all counters are equal
    #if counters are higher than 1, take the most recent one, otherwise consider no data
    if list_counter_value[0] == 1:
      #print ("CASE 4, more than one and all equal and ==1, choosing randomly from non-current: ", list_counter_value)
      dict_temp = counters[history_item].copy()
      del dict_temp[tier_item]
      tier_guess_item = random.choice(list(dict_temp.keys()))
    else: #there is some inconclusive statistics here, let's select one randomly. That probably will break a lot of ties further down the loop
      #TODO: maybe assign to the tier that is close the latest entry in the HMM instead?
      tier_guess_item = random.choice(list(counters[history_item].keys())) #call list on the returned object in python3
      #print ("CASE 5, more than one and all equal but greater than 1, choosing randomly from : ", list_counter_value, "vinner:", tier_guess_item)
  else:
    #good, substantial data to make a decision
    tier_guess_item =  max(counters[history_item], key=counters[history_item].get)
    #print ("CASE 6: winner: ", tier_guess_item)


  match_item = ''
  if tier_guess_item == tier_item:
    match_item = 'OK'

  up_down_guess_item = ''
  if tier_guess_item[0] == tier_item[0]:
    up_down_guess_item = 'OK'

  price_guess_item = close_item_previuos
  if tier_guess_item[-1] == 'L':
    price_guess_item += dict_tiers_source['tier_low_mean']
  elif tier_guess_item[-1] == 'M':
    price_guess_item += dict_tiers_source['tier_medium_mean']
  elif tier_guess_item[-1] == 'H':
    price_guess_item += dict_tiers_source['tier_high_mean']

  return tier_guess_item, price_guess_item, match_item, up_down_guess_item


def set_guesses_old(df, counters, counter, dict_tiers_source):
  #yield generate_new_column(1,2)

  """deprecated - set 'Tier Guess', 'Up/Down Guess', and 'Price Guess' columns"""
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


