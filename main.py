#!/usr/bin/env python3

import numpy as np
import pandas as pd
import os, sys, inspect

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
#app = Flask(__name__, static_folder='static') 'static' has no effect

@app.route("/test")
def hello():
  """checks if flask works"""
  return "flask works"

@app.route("/")
def load():
  """main table load"""
  ticker = 'FB' #that really is better to be submitted in the route /FB but that's not in the requirements
  prophet = Prophet(ticker)

  source = 'google'
  #date_end =  datetime.now() #also can be submitted in API call parameters...
  #date_start = date_end - datetime.now()

  #since we are using pandas anyway, let's take advantage of weekend-skipping call from the beginning
  #'last 365 days' really means 'all weekdays in the last 365 days' which is 261. The other way is to use ".reindex" on the output instead
  datelist = pd.bdate_range(end=pd.datetime.today(), periods=365 - 52*2).tolist()

  date_start = datelist[0]
  date_end = datelist[-1]

  #a call to a third-party - needs to be checked
  try:
    panel = data.DataReader([ticker], source, date_start, date_end)
  except:
    error  = "failed to get data from %s" % source
    prophet.log(error)
    return error # just serve the error description in this case

  print (dir(panel))
  print (panel.to_frame())
  print (dir(panel))

  panel_close = panel.ix['Close']
  close_table = panel_close.describe()

#  chart_type = 'multiBarHorizontalData'
#  chart = nvd3.multiBarHorizontalData(name=chart_type, height=500, width=500)

  chart_type = 'discreteBarChart'
  chart = nvd3.discreteBarChart(name=chart_type, height=500, width=500)


  ydata = [float(x) for x in np.random.randn(10)]
  xdata = [int(x) for x in np.arange(10)]

  chart.add_serie(y=ydata, x=xdata)
  chart.buildhtml()
  chart_html = chart.htmlcontent
  panel_html = str(panel.to_frame().to_html())
  #content = str(close_table) + str(chart_html) + str(panel.to_frame().to_html())
  dict_content = {'close_table': str(close_table), 'chart_html': str(chart_html), 'panel_html': panel_html}
  return prophet.parse_template("%s/main.html" % prophet.config.get(prophet.env, 'templates'), dict_content)

  #return chart_html
  #return str(close_table) + str(chart_html) + str(panel.to_frame().to_html())


if __name__ == "__main__":
    app.run()

