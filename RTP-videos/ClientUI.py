from tkinter import *
import tkinter.messagebox as tkMessageBox
from PIL import Image, ImageTk
from io import BytesIO
from Constants import *

class ClientUI:
    def __init__(self, master, eventhandlers):
        self.master = master
        self.master.protocol("WM_DELETE_WINDOW", self.handler)
        self.event_handlers = eventhandlers
        self.createWidgets()


    def createWidgets(self):
        """Build GUI."""
        # Create Setup button
        self.setup = Button(self.master, width=20, padx=3, pady=3)
        self.setup["text"] = "Setup"
        self.setup["command"] = self.setupMovie
        self.setup.grid(row=1, column=0, padx=2, pady=2)

        # Create Play button
        self.start = Button(self.master, width=20, padx=3, pady=3)
        self.start["text"] = "Play"
        self.start["command"] = self.playMovie
        self.start.grid(row=1, column=1, padx=2, pady=2)

        # Create Pause button
        self.pause = Button(self.master, width=20, padx=3, pady=3)
        self.pause["text"] = "Pause"
        self.pause["command"] = self.pauseMovie
        self.pause.grid(row=1, column=2, padx=2, pady=2)

        # Create Teardown button
        self.teardown = Button(self.master, width=20, padx=3, pady=3)
        self.teardown["text"] = "Teardown"
        self.teardown["command"] = self.exitClient
        self.teardown.grid(row=1, column=3, padx=2, pady=2)

        # Create a label to display the movie
        self.label = Label(self.master, height=19)
        self.label.grid(row=0, column=0, columnspan=4, sticky=W + E + N + S, padx=5, pady=5)


    def setupMovie(self):
        self.event_handlers['setup']()


    def exitClient(self):
        self.event_handlers['teardown']()
        self.master.destroy()  # Close the gui window


    def pauseMovie(self):
        self.event_handlers['pause']()


    def playMovie(self):
        self.event_handlers['play']()


    def updateMovie(self, frame):
        image_tk = Image.open(BytesIO(frame))
        photo = ImageTk.PhotoImage(image_tk)
        self.label.configure(image=photo, height=360)
        self.label.image = photo


    def handler(self):
        self.pauseMovie()
        if tkMessageBox.askokcancel("退出?", "你确认要退出吗"):
            self.exitClient()
        else:
            self.playMovie()

