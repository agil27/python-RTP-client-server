from Client import *
from tkinter import Tk

window = Tk()
client = Client(window, '127.0.0.1', 8554, 32254, 'rtp://127.0.0.1:8554')
window.mainloop()
