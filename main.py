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
  if days_back > 500:
    return "No more than 500 days of ticker history range can be analyzed"

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
  #date_end =  datetime.now() #also can be submitted in API call parameters...
  #date_start = date_end - datetime.now()

  #since we are using pandas anyway, let's take advantage of weekend-skipping call from the beginning
  #'last 365 days' really means 'all weekdays in the last 365 days' which is 261, plus 3 days to prime the first 3 predictions
  #The other way is to use ".reindex" on the output instead on date_range output
  days_active = days_back - 52*2 + days
  datelist = pd.bdate_range(end=pd.datetime.today(), periods=days_active).tolist()

  #a call to a third-party API - needs to be checked
  try:
    panel = data.DataReader([ticker], source, datelist[0], datelist[-1])
  except:
    error  = "failed to get data from %s" % source
    prophet.log(error)
    return error # just serve the error description in this case

  # experiment with just 'Close' call #TODO remove at the end if not needed
  panel_close = panel.ix['Close']
  close_table = panel_close.describe()
  html_close_table = str(close_table.to_html())

  #panel = panel.dropna(axis=1, how='any')

  # df = panel.to_frame()
  df = panel[:,:,'FB'] # drop vertical minor axis, it's one ticker anyway

  df = prophet.enrich(df)
  dict_tiers = prophet.set_tiers(df)
  print ("set tiers: ", dict_tiers)

  source_key = 'Yield % Open'

  target_key1 = 'History'
  df[target_key1] = ''

  target_key2 = 'State'
  df[target_key2] = ''

  target_key3 = 'Prediction'
  df[target_key3] = ''

  df['Check'] = ''
  df[target_key1], df[target_key2], df[target_key3] = prophet.set_hmm_state(df, source_key, target_key1, target_key2, target_key3, dict_tiers[source_key])

  success_count = "%s out of %s" % (df['Check'].value_counts()['OK'], days_active)

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

  html_panel = str(df.to_html())

  dict_table_header = { 'Ticker': [ticker],
                        'Days to Analyze': [days],
                        'Browser Request': ['http://127.0.01.:5000/[<ticker>,<days>]'],
                        'Predicted': success_count
                      }
  df_table_header = pd.DataFrame.from_dict(dict_table_header)
  html_table_header = df_table_header.to_html()

  dict_content = {
                  'html_header_table' : html_table_header,
                  'html_close_table'  : html_close_table,
                  'html_chart'        : str(html_chart),
                  'html_panel'       : html_panel
  }

  return prophet.parse_template("%s/main.html" % prophet.config.get(prophet.env, 'templates'), dict_content)



if __name__ == "__main__":
    app.run()

