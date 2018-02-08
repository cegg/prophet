#!/usr/bin/env python3

import numpy as np
import pandas as pd
from datetime import datetime
import timeit

def main():
  z = datetime.now()
  dict_test = {"one": [z, z, z, z], "two": [5.9,6.111,7.7,8.6], "three": [12.9,12.8,12.7,12.5]}

  df = pd.DataFrame.from_dict(dict_test)


  #doubles = list(print(x) for x in n (n for n in df))
  #print ("doubles:", doubles)

  s = pd.Series(generate(diff, dict_test['two'], dict_test['three']))
  print ("after", s)

  df['four'] = s



def diff(x, y):
  return x-y

def generate(func, df_column1, df_column2):
  for x, y  in zip(df_column1, df_column2):
    print (type(x), type(y), x-y)
    yield func(x,y)


if __name__ == "__main__":
    main()
