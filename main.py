#!/usr/bin/env python3

import sys

if (3/2 == 1):
  sys.exit("wrong python. use 3.x")

import os, inspect
import numpy as np
import pandas as pd


#set where to find the locally installed packages are
currentdir = os.path.abspath(inspect.getfile(inspect.currentframe()))
libdir = os.path.dirname(currentdir) + '/lib'
sys.path.insert(0,libdir)

#import locally installed packages from requirements.txt
from flask import Flask
from pandas_datareader import data
from prophet import Prophet
#from datetime import datetime
import nvd3

app = Flask(__name__)

@app.route("/test")
def hello():
  """checks if flask works"""
  return "flask works"

from werkzeug.routing import BaseConverter
class RegexConverter(BaseConverter):
  def __init__(self, url_map, *items):
    super(RegexConverter, self).__init__(url_map)
    self.regex = items[0]

app.url_map.converters['regex'] = RegexConverter

#for version 1 just do not allow more than 10 days of historical data to be analyzed
@app.route('/<regex("[a-zA-Z0-9]{2,5},\d{1}"):pars>/')
def setup(pars):
  ticker, days = pars.split(',')
  print (ticker, days)
  return load(ticker, int(days))

#@app.route('/<regex("[abcABC0-9]{4,6}"):uid>-<slug>/')

#TODO figure out what multy-match pattern in flask is
# @app.route('/<regex("[a-zA-Z0-9]{2,5}"):ticker,("[0-9]{1,2}"):days">/')
# def setup(ticker, days):
#     return "pars: %s, %s" % (ticker, days)

@app.route("/")
def load(ticker='FB', days=3):
  """main table load"""
  prophet = Prophet(ticker)

  print ("load:", ticker, days)
  source = 'google'
  #date_end =  datetime.now() #also can be submitted in API call parameters...
  #date_start = date_end - datetime.now()

  #since we are using pandas anyway, let's take advantage of weekend-skipping call from the beginning
  #'last 365 days' really means 'all weekdays in the last 365 days' which is 261, plus 3 days to prime the first 3 predictions
  #The other way is to use ".reindex" on the output instead on date_range output
  datelist = pd.bdate_range(end=pd.datetime.today(), periods=365 - 52*2 + days).tolist()

  date_start = datelist[0]
  date_end = datelist[-1]

  #a call to a third-party API - needs to be checked
  try:
    panel = data.DataReader([ticker], source, date_start, date_end)
  except:
    error  = "failed to get data from %s" % source
    prophet.log(error)
    return error # just serve the error description in this case

  print (panel)
  print ("panel type", type(panel))

  panel_close = panel.ix['Close']
  close_table = panel_close.describe()
  html_close_table = str(close_table.to_html())

  #panel = panel.dropna(axis=1, how='any')

  df = panel.to_frame()
  print ("frame type: ", type(df))
  df['Spread']       = df['High'] - df['Low']
  df['Yield']        = df['Close'] - df['Open']
  df['Yield Avg']    = df['Yield'] #TODO figure out why setting to zero breaks calculations below
  df['Yield % Open'] = df['Yield']
  df['Yield % Open 3'] = df['Yield']

  #days = 3 # data for the previous 3 days; can be externalized
  for counter, val in enumerate (df['Yield']):
    if counter < days:
      df['Yield Avg'][counter] = 0
      df['Yield % Open'][counter] = 0
      df['Yield % Open 3'][counter] = 0
      continue

    print ("counter:", counter)
    #get avg yield (amount and percent) for three previous days
    #print (counter-days, counter-1, df['Yield'][counter-days:counter-1].sum() / days)
    df['Yield Avg'][counter]      = round (df['Yield'][counter-days:counter-1].sum() / days, 2)
    df['Yield % Open'][counter]   = round (df['Yield'][counter] / df['Open'][counter]*100, 6)
    #this one below is not getting calculated correctly
    df['Yield % Open 3'][counter] = round (df['Yield % Open'][counter-days:counter-1].sum() / days, 6)
    print ("range: ", df['Yield % Open'][counter-days:counter-1], "sum:", df['Yield % Open'][counter-days:counter-1].sum(), "sum/3:", df['Yield % Open'][counter-days:counter-1].sum() / days)
    if counter > 5:
      break





#  chart_type = 'multiBarHorizontalData'
#  chart = nvd3.multiBarHorizontalData(name=chart_type, height=500, width=500)

#example chart
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
                        'Request': ['http://127.0.01.:500/<ticker>,<days>']
                      }
  df_table_header = pd.DataFrame.from_dict(dict_table_header)
  html_table_header = df_table_header.to_html()

  dict_content = {'ticker'            : ticker,
                  'days'              : days,
                  'html_header_table' : html_table_header,
                  'html_close_table'  : html_close_table,
                  'html_chart'        : str(html_chart),
                  'html_panel'       : html_panel
  }

  return prophet.parse_template("%s/main.html" % prophet.config.get(prophet.env, 'templates'), dict_content)



if __name__ == "__main__":
    app.run()

