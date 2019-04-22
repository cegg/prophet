Stock Analyser by ticker, sample size and period
  Gets data for the last <period> days and for each day predicts the stock priced based on the stats from the <analysis days range> previous days
  Web version served with Flask
  Default: http://127.0.01:5000/
  With parameters: http://127.0.01:5000/<ticker symbol>,<days back to analyze>,<range days>
  Example: http://127.0.01:5000/FB,3,300


Getting Started

  unzip
  
  cd prophet
  
  pip3 install -t lib -r requirements.txt
  
  python3 main.py
  

  github:

Prerequisites
  all prerequisites are installed with pip3 step in "Geting Started" section (listed in requirements.txt)

Running the tests
  TODO

Author
  Igor Pozdnyakov

License
  GNU General Public License v3.0
