from ClientController import Client
from Exception import *

client = Client('127.0.0.1', 8554, 32254, 'rtp://127.0.0.1:8554')
try:
    client.run()
except Error as e:
    e.text()
