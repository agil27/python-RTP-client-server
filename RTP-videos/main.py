from ClientController import ClientController as cc

mycc = cc('127.0.0.1', 8554, 32254, 'rtp://127.0.0.1:8554')
mycc.run()
