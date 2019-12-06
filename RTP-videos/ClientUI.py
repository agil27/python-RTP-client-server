from tkinter import *
import tkinter.messagebox as tkMessageBox
from PIL import Image, ImageTk
from io import BytesIO


class ClientUI:
    def __init__(self, master, eventhandlers, filelist):
        self.master = master
        self.master.protocol("WM_DELETE_WINDOW", self.handler)
        self.event_handlers = eventhandlers
        self.filelist = filelist
        self.pos = StringVar()
        self.createWidgets()

    def createWidgets(self):
        """Build GUI."""
        # Create Setup button
        self.setup = Button(self.master, width=12)
        self.setup["text"] = "启动"
        self.setup["command"] = self.setupMovie
        self.setup.grid(row=2, column=0)

        # Create Play button
        self.start = Button(self.master, width=12)
        self.start["text"] = "播放"
        self.start["command"] = self.playMovie
        self.start.grid(row=2, column=1)

        # Create Pause button
        self.pause = Button(self.master, width=12)
        self.pause["text"] = "暂停"
        self.pause["command"] = self.pauseMovie
        self.pause.grid(row=2, column=2)

        # Create Teardown button
        self.teardown = Button(self.master, width=12)
        self.teardown["text"] = "停止"
        self.teardown["command"] = self.exitClient
        self.teardown.grid(row=2, column=3)

        self.double = Button(self.master, width=12)
        self.double["text"] = "2x"
        self.double["command"] = self.doubleSpeed
        self.double.grid(row=3, column=1)

        self.mute = Button(self.master, width=12)
        self.mute["text"] = "静音"
        self.mute["command"] = self.muteSound
        self.mute.grid(row=3, column=0)

        self.audiofwd = Button(self.master, width=12)
        self.audiofwd["text"] = "音频快进"
        self.audiofwd["command"] = self.audioForward
        self.audiofwd.grid(row=3, column=2)

        self.audiobwd = Button(self.master, width=12)
        self.audiobwd["text"] = "音频后退"
        self.audiobwd["command"] = self.audioBackward
        self.audiobwd.grid(row=3, column=3)

        self.fullscreen = Button(self.master, width=12)
        self.fullscreen["text"] = "全屏"
        self.fullscreen["command"] = self.fullScreen
        self.fullscreen.grid(row=2, column=4)

        self.sub = Button(self.master, width=12)
        self.sub["text"] = "显示弹幕"
        self.sub["command"] = self.subtitle()
        self.sub.grid(row=3, column=4)

        self.playentry = Listbox(self.master, width=25, height=20)
        for s in self.filelist:
            self.playentry.insert(END, s)
        self.playentry.grid(row=0, column=5, rowspan=4)
        self.playentry.bind('<Double-1>', self.selectFile)

        self.scroll = Scrollbar(self.master, command=self.playentry.yview)
        self.scroll.grid(row=0, column=6)
        self.playentry.configure(yscrollcommand=self.scroll.set)

        # Create a label to display the movie
        self.label = Label(self.master, height=19)
        self.label.grid(row=0, column=0, columnspan=5)

        self.slider = Scale(self.master, orient=HORIZONTAL, from_=0, to=1000, length=500, variable=self.pos)
        self.slider.grid(row=1, column=0, columnspan=5)
        self.slider.bind('<Button-1>', self.repositionStart)
        self.slider.bind('<ButtonRelease-1>', self.repositionEnd)

    def setupMovie(self):
        self.event_handlers['setup']()

    def exitClient(self):
        self.event_handlers['teardown']()
        self.master.destroy()  # Close the gui window

    def pauseMovie(self):
        self.event_handlers['pause']()

    def playMovie(self):
        self.event_handlers['play']()

    def repositionStart(self, pos):
        self.event_handlers['pause']()

    def repositionEnd(self, pos):
        position = int(self.pos.get())
        if position == 0:
            position = 1
        if position == 1000:
            position = 999
        self.event_handlers['reposition'](position)

    def updateMovie(self, frame):
        image_tk = Image.open(BytesIO(frame))
        photo = ImageTk.PhotoImage(image_tk)
        self.label.configure(image=photo, height=270)
        self.label.image = photo

    def updateSlider(self, position):
        self.pos.set(position)

    def handler(self):
        self.pauseMovie()
        if tkMessageBox.askokcancel("退出?", "你确认要退出吗"):
            self.exitClient()
        else:
            self.playMovie()

    def doubleSpeed(self):
        if self.double["text"] == '2x':
            self.double["text"] = '1x'
        else:
            self.double["text"] = '2x'
        self.event_handlers['double']()

    def muteSound(self):
        self.event_handlers["mute"]()

    def audioBias(self, bias):
        self.event_handlers["audioBias"](bias)

    def audioForward(self):
        self.audioBias(60)

    def audioBackward(self):
        self.audioBias(-60)

    def fullScreen(self):
        w = self.master.winfo_screenwidth()
        h = self.master.winfo_screenheight()
        self.master.geometry("%dx%d" % (w, h))
        self.master.attributes("-topmost", True)

    def subtitle(self):
        pass

    def selectFile(self, event):
        index = int(self.playentry.curselection()[0])
        self.event_handlers['selectFile'](self.filelist[index])
