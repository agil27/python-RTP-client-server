from ClientController import ClientController as cc
from Exception import *

mycc = cc('127.0.0.1', 8554, 32254, 'rtp://127.0.0.1:8554')
try:
    mycc.run()
except Error as e:
    e.text()
