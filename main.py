#!/usr/bin/env python3

import sys

if (3/2 == 1):
  sys.exit("wrong python. use 3.x")

import os, inspect
import numpy as np
import pandas as pd

#set where to find locally installed packages
currentdir = os.path.abspath(inspect.getfile(inspect.currentframe()))
libdir = os.path.dirname(currentdir) + '/lib'
sys.path.insert(0,libdir)

#import locally installed packages from requirements.txt
from flask import Flask
from pandas_datareader import data
from prophet import Prophet
import nvd3

#import timeit # for profiling
import time # for milliseconds

from werkzeug.routing import BaseConverter # that's for submitting ticker and days in the url
class RegexConverter(BaseConverter):
  def __init__(self, url_map, *items):
    super(RegexConverter, self).__init__(url_map)
    self.regex = items[0]

app = Flask(__name__)

app.url_map.converters['regex'] = RegexConverter

@app.route("/test")
def hello():
  """checks if flask works"""
  return "flask works"

#for version 1 just do not allow more than 10 days of historical data to be analyzed
@app.route('/<regex("[a-zA-Z0-9]{2,5},\d+,\d+"):pars>/')
def setup(pars):
  ticker, days, days_back = pars.split(',')
  days = int(days)
  days_back = int(days_back)
  if days > 5:
    return "No more than 5 days of history range for a given day can be analyzed"
  if days_back > 700:
    return "No more than 700 days of ticker history range can be analyzed"

  if (days_back/days < 100):
    return "Unrealistic ratio of ticker history range to record history range. Increase ticker history range or decrease record history range to be analyzed."

  return load(ticker, days, days_back)

#@app.route('/<regex("[abcABC0-9]{4,6}"):uid>-<slug>/')

#TODO figure out what multy-match pattern in flask is
# @app.route('/<regex("[a-zA-Z0-9]{2,5}"):ticker,("[0-9]{1,2}"):days">/')
# def setup(ticker, days):
#     return "pars: %s, %s" % (ticker, days)

@app.route("/") #default load
def load(ticker='FB', days=3, days_back=365):
  """main table load"""
  prophet = Prophet(ticker, days)

  source = 'google'


  #since we are using pandas anyway, let's take advantage of weekend-skipping call from the beginning
  #e.g. 'last 365 days' really means 'all weekdays in the last 365 days' which is 261, plus 3 days to prime the first 3 predictions
  #The other way is to use ".reindex" on the output instead on date_range output
  weeks = days_back // 7 #integer number of weeks in the requested range
  days_active = days_back - weeks*2 + days
  #user input makes no sense. should not hapen at this point but it's better be safe
  if days_active < 3:
    error = "User requested invalid date range"
    prophet.log(error)
    return error

  datelist = pd.bdate_range(end=pd.datetime.today(), periods=days_active).tolist()

  #a call to a third-party API - needs to be checked
  try:
    panel = data.DataReader([ticker], source, datelist[0], datelist[-1])
  except:
    error  = "failed to get data from %s" % source
    prophet.log(error)
    return error # just serve the error description in this case

  # df = panel.to_frame()
  df = panel[:,:,ticker] # drop vertical minor axis, it's one ticker anyway

  df = prophet.enrich(df)
  dict_tiers = prophet.set_tiers(df)

  source_key = 'Yield % Open'

  # avoid type collisions
  df['Tier'] = ''
  df['Up/Down Guess'] = ''
  df['Price Guess'] = ''

  millisec1 = int(round(time.time() * 1000))
  prophet.set_hmm_state(df, source_key, dict_tiers[source_key])
  millisec2 = int(round(time.time() * 1000))
  print ('process:', millisec1, millisec2, millisec2-millisec1)

  count_match_ok = int(df['Match'].value_counts()['OK'])
  count_tier_guess_no_data = int(df['Tier Guess'].value_counts()['no data'])
  percent = round(count_match_ok * 100 / days_active, 2)
  stats_message_tier = "{0} out of {1} ({2}%)".format(count_match_ok, days_active, percent)

  success_count_direction = int(df['Up/Down Guess'].value_counts()['OK'])
  percent = round(success_count_direction * 100 / (days_active-count_tier_guess_no_data), 2)
  stats_message_direction = "{0} out of {1} ({2}%)".format(success_count_direction, days_active-count_tier_guess_no_data, percent)


  #experiment with charts lib #TODO: remove at the end
  # chart_type = 'discreteBarChart'
  # chart = nvd3.discreteBarChart(name=chart_type, height=500, width=500)
  # ydata = [float(x) for x in np.random.randn(10)]
  # xdata = [int(x) for x in np.arange(10)]
  # chart.add_serie(y=ydata, x=xdata)
  # chart.buildhtml()
  # html_chart = str(chart.htmlcontent)

  # no display required for the analyzed date range itself (first <days> days) even if they got formatted to zeroes or something
  df['Tier'][0:days] = ''
  df['Yield'][0:days] = ''
  df['Yield % Open'][0:days] = ''

  #reorder
  df =df[['Open', 'High', 'Low', 'Close', 'Volume', 'Yield', 'Yield % Open', 'History', 'Tier', 'Tier Guess', 'Match', 'Up/Down Guess', 'Price Guess']]
  html_table_main = str(df.to_html())
  html_table_main = html_table_main.replace(" Guess", "<br>Guess") # not sure how to edit df title entries without changing keys of df, so just quick formatting ehre

  column_name = 'Yield % Open'
  dict_table_request = { 'Ticker': [ticker],
                        'Days to Analyze': [days],
                        'Browser Request Format': ['http://127.0.01.:5000/[<ticker>,<days>,<range>]'],
                        'Tier Low (L)': ["%s : %s" % (dict_tiers[column_name]['min'], dict_tiers[column_name]['tier_low_top'])],
                        'Tier Medium (M)': ["%s : %s" % (dict_tiers[column_name]['tier_low_top' ], dict_tiers[column_name]['tier_medium_top'])],
                        'Tier High (H)': ["%s : %s" % (dict_tiers[column_name]['tier_medium_top' ], dict_tiers[column_name]['max'])]
                      }
  df_table_request = pd.DataFrame.from_dict(dict_table_request)
  #reorder
  df_table_request = df_table_request[['Browser Request Format', 'Ticker', 'Days to Analyze', 'Tier Low (L)', 'Tier Medium (M)', 'Tier High (H)']]
  #does not work
  #df_table_header.drop(df_table_header.columns[1], axis=1) #drop bogus empty column with "0"
  html_table_request = df_table_request.to_html()

  dict_table_results = {
                        'Tier Guessed': [stats_message_tier],
                        'Up/Down Guessed': [stats_message_direction]
                      }
  df_table_results = pd.DataFrame.from_dict(dict_table_results)
  html_table_results = df_table_results.to_html()
  dict_content = {
                  'html_table_request' : html_table_request,
                  'html_table_results' : html_table_results,
                  'html_table_main'       : html_table_main
  }

  return prophet.parse_template("%s/main.html" % prophet.config.get(prophet.env, 'templates'), dict_content)



if __name__ == "__main__":
    app.run()

