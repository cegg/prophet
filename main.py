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

import timeit # for profiling

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

  import datetime

  source = 'google'
  #date_end =  datetime.now() #also can be submitted in API call parameters...
  #date_start = date_end - datetime.now()

  #since we are using pandas anyway, let's take advantage of weekend-skipping call from the beginning
  #'last 365 days' really means 'all weekdays in the last 365 days' which is 261, plus 3 days to prime the first 3 predictions
  #The other way is to use ".reindex" on the output instead on date_range output
  weeks = days_back // 7
  days_active = days_back - weeks*2 + days
  #user input makes no sense. should not hapen at this point but it's better be safe
  if days_active < 3:
    error = "User requested invalid date range"
    prophet.log(error)
    return error

  datelist = pd.bdate_range(end=pd.datetime.today(), periods=days_active).tolist()


  dt_obj = datetime.datetime.strptime('20.12.2016 09:38:42,76',
                           '%d.%m.%Y %H:%M:%S,%f')
  millisec1 = dt_obj.timestamp() * 1000
  #a call to a third-party API - needs to be checked
  try:
    panel = data.DataReader([ticker], source, datelist[0], datelist[-1])
  except:
    error  = "failed to get data from %s" % source
    prophet.log(error)
    return error # just serve the error description in this case
  dt_obj = datetime.datetime.strptime('20.12.2016 09:38:42,76',
                           '%d.%m.%Y %H:%M:%S,%f')
  millisec2 = dt_obj.timestamp() * 1000
  print ('call:', millisec1, millisec2, millisec2-millisec1)

  # experiment with just 'Close' call #TODO remove at the end if not needed
  panel_close = panel.ix['Close']
  close_table = panel_close.describe()
  html_close_table = str(close_table.to_html())

  #panel = panel.dropna(axis=1, how='any')

  # df = panel.to_frame()
  df = panel[:,:,ticker] # drop vertical minor axis, it's one ticker anyway

  dt_obj = datetime.datetime.strptime('20.12.2016 09:38:42,76',
                           '%d.%m.%Y %H:%M:%S,%f')
  millisec1 = dt_obj.timestamp() * 1000
  df = prophet.enrich(df)
  dict_tiers = prophet.set_tiers(df)
  #print ("set tiers: ", dict_tiers)

  source_key = 'Yield % Open'

  target_key1 = 'History'
  df[target_key1] = ''

  target_key2 = 'State'
  df[target_key2] = ''

  target_key3 = 'Prediction'
  df[target_key3] = ''

  df['Check'] = ''
  #df['Predict Price'] = ''
  df['Up/Down Guess'] = ''
  df['Price Guess'] = ''
  df[target_key1], df[target_key2], df[target_key3] = prophet.set_hmm_state(df, source_key, target_key1, target_key2, target_key3, dict_tiers[source_key])
  dt_obj = datetime.datetime.strptime('20.12.2016 09:38:42,76',
                           '%d.%m.%Y %H:%M:%S,%f')
  millisec2 = dt_obj.timestamp() * 1000
  print ('process:', millisec1, millisec2, millisec2-millisec1)

  success_count_tier = int(df['Check'].value_counts()['OK'])
  percent = round(success_count_tier * 100 / days_active, 2)
  stats_message_tier = "{0} out of {1} ({2}%)".format(success_count_tier, days_active, percent)

  success_count_direction = int(df['Up/Down Guess'].value_counts()['OK'])
  percent = round(success_count_direction * 100 / days_active, 2)
  stats_message_direction = "{0} out of {1} ({2}%)".format(success_count_direction, days_active, percent)

#  chart_type = 'multiBarHorizontalData' #does not work
#  chart = nvd3.multiBarHorizontalData(name=chart_type, height=500, width=500)

  #experiment with charts lib #TODO: remove at the end
  chart_type = 'discreteBarChart'
  chart = nvd3.discreteBarChart(name=chart_type, height=500, width=500)
  ydata = [float(x) for x in np.random.randn(10)]
  xdata = [int(x) for x in np.arange(10)]
  chart.add_serie(y=ydata, x=xdata)
  chart.buildhtml()
  html_chart = chart.htmlcontent


  dt_obj = datetime.datetime.strptime('20.12.2016 09:38:42,76',
                           '%d.%m.%Y %H:%M:%S,%f')
  millisec1 = dt_obj.timestamp() * 1000
  html_table_main = str(df.to_html())
  dt_obj = datetime.datetime.strptime('20.12.2016 09:38:42,76',
                           '%d.%m.%Y %H:%M:%S,%f')
  millisec2 = dt_obj.timestamp() * 1000
  print ('html:', millisec1, millisec2, millisec2-millisec1)

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
                  'html_close_table'  : html_close_table,
                  'html_chart'        : str(html_chart),
                  'html_table_main'       : html_table_main
  }

  return prophet.parse_template("%s/main.html" % prophet.config.get(prophet.env, 'templates'), dict_content)



if __name__ == "__main__":
    app.run()

