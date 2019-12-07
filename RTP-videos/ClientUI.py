from tkinter import *
import tkinter.messagebox as tkMessageBox
from PIL import ImageTk



class ClientUI:
    def __init__(self, master, filelist):
        self.master = master
        self.master.protocol("WM_DELETE_WINDOW", self.handler)
        self.event_handlers = None
        self.filelist = filelist
        self.width = self.master.winfo_screenwidth()
        self.height = self.master.winfo_screenheight()
        self.isFullscreen = False
        self.pos = StringVar()
        self.createWidgets()

    def createWidgets(self):
        """Build GUI."""
        # Create Setup button
        self.resolution = Button(self.master, width=12)
        self.resolution["text"] = "流畅"
        self.resolution["command"] = self.changeResolution
        self.resolution.grid(row=2, column=4)

        # Create Play button
        self.start = Button(self.master, width=12)
        self.start["text"] = "播放"
        self.start["command"] = self.playMovie
        self.start.grid(row=2, column=0)

        # Create Pause button
        self.pause = Button(self.master, width=12)
        self.pause["text"] = "暂停"
        self.pause["command"] = self.pauseMovie
        self.pause.grid(row=2, column=1)

        # Create Teardown button
        self.teardown = Button(self.master, width=12)
        self.teardown["text"] = "停止"
        self.teardown["command"] = self.haltMovie
        self.teardown.grid(row=2, column=2)

        self.double = Button(self.master, width=12)
        self.double["text"] = "2x"
        self.double["command"] = self.doubleSpeed
        self.double.grid(row=2, column=3)

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
        self.fullscreen.grid(row=3, column=1)

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
        self.label = Label(self.master, height=18)
        self.label.grid(row=0, column=0, columnspan=5)

        self.slider = Scale(self.master, orient=HORIZONTAL, from_=0, to=1000, length=500, variable=self.pos)
        self.slider.grid(row=1, column=0, columnspan=5)
        self.slider.bind('<Button-1>', self.repositionStart)
        self.slider.bind('<ButtonRelease-1>', self.repositionEnd)

        self.top = None
        self.master.bind('<Escape>', self.onEscPressed)

    def setupMovie(self):
        self.event_handlers['setup']()

    def exitClient(self):
        self.event_handlers['teardown']()
        self.master.destroy()  # Close the gui window

    def pauseMovie(self):
        self.event_handlers['pause']()

    def playMovie(self):
        self.event_handlers['play']()

    def haltMovie(self):
        self.event_handlers['teardown']()

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
        try:
            photo = ImageTk.PhotoImage(frame)
            photo_height = 270 if not self.isFullscreen else self.height
            self.label.configure(image=photo, height=photo_height)
            self.label.image = photo
        except AttributeError:
            return

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
        self.isFullscreen = True
        self.top = Toplevel()
        self.top.geometry("%dx%d" % (self.width, self.height))
        self.top.attributes("-topmost", True)
        self.top.title('全屏播放')
        self.label = Label(self.top, height=40)
        self.label.grid(row=0, column=0, columnspan=5)
        self.event_handlers['setFullscreen'](True)

    def subtitle(self):
        pass

    def selectFile(self, event):
        index = int(self.playentry.curselection()[0])
        print(self.event_handlers, self.filelist)
        self.event_handlers['selectFile'](self.filelist[index])
        self.setupMovie()

    def changeResolution(self):
        if self.resolution["text"] == '流畅':
            self.event_handlers['setLowres'](True)
            self.resolution["text"] = '标清'
        else:
            self.event_handlers['setLowres'](False)
            self.resolution["text"] = '流畅'

    def onEscPressed(self, event):
        if self.isFullscreen:
            self.isFullscreen = False
            self.smallify()

    def smallify(self):
        self.top.destroy()
        self.top = None
        self.label = Label(self.master, height=18)
        self.label.grid(row=0, column=0, columnspan=5)
        self.event_handlers['setFullscreen'](False)

    def setHandlers(self, handlers):
        self.event_handlers = handlers