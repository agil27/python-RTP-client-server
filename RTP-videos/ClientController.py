import socket, threading
from RtpPacket import RtpPacket
from utils import LinkList
import sounddevice as sd
from Exception import *
from Constants import *
from RtspTools import ResponseParser, RequestSender
from ClientUI import ClientUI
from tkinter import Tk
from PIL import Image
from io import BytesIO


class ClientController:
    def __init__(self, serveraddr, serverport, rtpport, filename, ui, width, height):
        self.server_addr = serveraddr
        self.server_port = serverport
        self.rtp_port = int(rtpport)
        self.filename = filename
        self.client_ui = ui
        self.screen_width = width
        self.screen_height = height
        self.initVariables()

    def initVariables(self):
        self.rtsp_seq = 0
        self.session_id = 0
        self.teardown_acked = False
        self.state = INIT
        self.request_sent = NULLREQ

        self.rtp_socket = None
        self.rtsp_socket = None

        self.video_framerate = 0
        self.audio_samplerate = 0
        self.total_frames = 0
        self.video_frame_seq = 0
        self.audio_frame_seq = 0
        self.frame_buffer = b''
        self.video_buffer = LinkList()
        self.audio_buffer = LinkList()

        self.video_thread = None
        self.audio_thread = None
        self.receive_thread = None
        self.listen_thread = None

        self.event = None
        self.video_consume_semaphore = None
        self.audio_consume_semaphore = None
        self.synchronize_semaphore = None
        self.current_timestamp = 0

        self.step = 1
        self.changeSpeed = False
        self.is_mute = False
        self.audio_bias = 0
        self.audio_bias_set = False
        self.low_resolution = False
        self.changeResolution = False
        self.fullscreen = False
        self.changeFullscreen = False
        self.subtitleRequired = False
        self.switchSubtitle = False

    def connect(self):
        self.rtsp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print(self.rtsp_socket, self.server_addr, self.server_port)
        try:
            self.rtsp_socket.connect((self.server_addr, self.server_port))
        except:
            raise ConnectionError
        self.receive_thread = threading.Thread(target=self.receiveResponse)
        self.receive_thread.setDaemon(True)
        self.receive_thread.start()

    def setup(self):
        self.connect()
        print(self.filename, self.state)
        if self.state == INIT:
            self.sendDescribe()

    def teardown(self):
        self.sendTeardown()

    def pause(self):
        if self.state == PLAYING:
            self.sendPause()

    def play(self):
        if self.state == READY:
            self.event.set()
            self.createThreads()
            self.sendPlay()

    def reposition(self, permillage):
        if self.state == READY:
            self.video_buffer = LinkList()
            self.audio_buffer = LinkList()
            startPosition = int(permillage / 1000 * self.total_frames)
            self.sendReposition(startPosition)
            self.event.set()

    def createThreads(self):
        if self.audio_thread is None:
            self.audio_thread = threading.Thread(target=self.playAudio)
            self.audio_thread.setDaemon(True)
            self.audio_thread.start()
        if self.video_thread is None:
            self.video_thread = threading.Thread(target=self.playVideo)
            self.video_thread.setDaemon(True)
            self.video_thread.start()
        if self.listen_thread is None:
            self.listen_thread = threading.Thread(target=self.listenForRtp)
            self.listen_thread.setDaemon(True)
            self.listen_thread.start()

    def playVideo(self):
        while self.video_buffer.len() < 20:
            pass
        while True:
            try:
                if self.teardown_acked:
                    return
                self.event.wait()
                self.video_consume_semaphore.acquire()
                current_frame, self.current_timestamp = self.retrieveFrame(mediatype=VIDEO)
                current_image = Image.open(BytesIO(current_frame))
                if self.fullscreen:
                    current_image = current_image.resize((self.screen_width, self.screen_height), Image.ANTIALIAS)
                elif self.low_resolution:
                    current_image = current_image.resize((480, 270), Image.ANTIALIAS)
                self.client_ui.updateMovie(current_image)
                if not self.fullscreen:
                    self.video_control_event.wait(TIME_ELAPSED)
            except:
                continue

    def playAudio(self):
        while self.video_buffer.len() < 20:
            pass
        while True:
            try:
                if self.teardown_acked:
                    return
                self.event.wait()
                self.audio_consume_semaphore.acquire()
                if not self.is_mute:
                    self.audio_stream.write(self.retrieveFrame(mediatype=AUDIO))
            except:
                continue

    def listenForRtp(self):
        print('\nListening...')
        while True:
            try:
                if self.teardown_acked:
                    return
                self.event.wait()
                data = self.rtp_socket.recv(MAX_UDP_BANDWIDTH)
                if data:
                    packet = RtpPacket()
                    packet.decode(data)
                    current_frame_seq = packet.seqNum()
                    marker = packet.getMarker()
                    media_type = packet.getType()
                    self.receiveIncomingPacket(packet, current_frame_seq, marker, media_type)
            except:
                break

    def receiveIncomingPacket(self, packet, seq, marker, media_type):
        if media_type == VIDEO:
            if seq > self.video_frame_seq:
                self.video_frame_seq = seq
                payload = packet.getPayload()
                timestamp = packet.timestamp()
                self.restoreFrame(payload, marker, timestamp, VIDEO)
        if media_type == AUDIO:
            if seq > self.audio_frame_seq:
                self.audio_frame_seq = seq
                payload = packet.getPayload()
                timestamp = packet.timestamp()
                self.restoreFrame(payload, marker, timestamp, AUDIO)

    def restoreFrame(self, payload, marker, timestamp, mediatype):
        if mediatype == VIDEO:
            self.frame_buffer += payload
            if marker:
                self.video_buffer.push((self.frame_buffer, timestamp))
                self.video_consume_semaphore.release()
                self.frame_buffer = b''
        if mediatype == AUDIO:
            self.audio_buffer.push(payload)
            self.audio_consume_semaphore.release()

    def retrieveFrame(self, mediatype):
        if mediatype == VIDEO:
            return self.video_buffer.pop()
        if mediatype == AUDIO:
            return self.audio_buffer.pop()

    def receiveResponse(self):
        while True:
            try:
                response = self.rtsp_socket.recv(MAX_RTSP_BANDWIDTH)
                if response:
                    self.parseResponse(response.decode('utf-8'))
            except:
                if self.teardown_acked:
                    break
                else:
                    continue

    def parseResponse(self, data):
        try:
            my_parser = ResponseParser(data, self.request_sent)
        except:
            return
        current_seq = my_parser.getSeq()
        if current_seq == self.rtsp_seq:
            session_id = my_parser.getSessionId()
            if self.session_id == 0:
                self.session_id = session_id

            if self.session_id == session_id:
                status_code = my_parser.getStatusCode()
                if status_code == 200:
                    if self.request_sent == SETUP:
                        self.handleSetup()
                    if self.request_sent == PLAY:
                        self.handlePlay()
                    if self.request_sent == PAUSE:
                        self.handlePause()
                    if self.request_sent == TEARDOWN:
                        self.handleTeardown()
                    if self.request_sent == DESCRIBE:
                        self.video_framerate, self.audio_samplerate, self.total_frames = my_parser.getAVParameters()
                        print('tf', self.total_frames)
                        self.handleDescribe()

    def handleSetup(self):
        self.state = READY
        self.openRtpPort()
        self.event = threading.Event()
        self.video_control_event = threading.Event()
        self.audio_control_event = threading.Event()
        self.video_consume_semaphore = threading.Semaphore(0)
        self.audio_consume_semaphore = threading.Semaphore(0)
        self.synchronize_semaphore = threading.Semaphore(0)

    def handlePlay(self):
        self.state = PLAYING
        timer = threading.Timer(1, self.activateSliderUpdate)
        timer.start()

    def handlePause(self):
        self.state = READY
        self.event.clear()
        if self.changeSpeed:
            self.changeSpeed = False
            self.video_buffer = LinkList()
            self.audio_buffer = LinkList()
            self.play()
        if self.audio_bias_set:
            self.audio_bias_set = False
            self.video_buffer = LinkList()
            self.audio_buffer = LinkList()
            self.play()
        if self.changeResolution:
            self.changeResolution = False
            self.video_buffer = LinkList()
            self.audio_buffer = LinkList()
            self.play()
        if self.switchSubtitle:
            self.switchSubtitle = False
            self.video_buffer = LinkList()
            self.audio_buffer = LinkList()
            self.play()

    def handleTeardown(self):
        self.state = INIT
        self.teardown_acked = True
        self.rtsp_socket.shutdown(socket.SHUT_RDWR)
        self.rtsp_socket.close()
        self.rtp_socket.close()
        self.event.clear()

    def handleDescribe(self):
        self.channels = 2
        self.sendSetup()
        self.audio_stream = sd.RawOutputStream(
            samplerate=self.audio_samplerate,
            channels=self.channels,
            dtype='float32'
        )
        self.audio_stream.start()

    def sendSetup(self):
        if self.state == INIT:
            self.rtsp_seq += 1
            my_sender = RequestSender(self.rtsp_socket, self.filename, self.rtp_port, self.rtsp_seq, self.session_id)
            self.request_sent = SETUP
            my_sender.sendSetup()

    def sendPlay(self):
        if self.state == READY:
            self.rtsp_seq += 1
            my_sender = RequestSender(
                self.rtsp_socket, self.filename,
                self.rtp_port, self.rtsp_seq,
                self.session_id, step=self.step,
                startPosition=self.current_timestamp,
                audiobias=self.audio_bias,
                lowres=self.low_resolution,
                subtitleRequired=self.subtitleRequired
            )
            self.request_sent = PLAY
            my_sender.sendPlay()

    def sendPause(self):
        if self.state == PLAYING:
            self.rtsp_seq += 1
            my_sender = RequestSender(self.rtsp_socket, self.filename, self.rtp_port, self.rtsp_seq, self.session_id)
            self.request_sent = PAUSE
            my_sender.sendPause()

    def sendTeardown(self):
        if self.state != INIT:
            self.rtsp_seq += 1
            my_sender = RequestSender(self.rtsp_socket, self.filename, self.rtp_port, self.rtsp_seq, self.session_id)
            self.request_sent = TEARDOWN
            my_sender.sendTeardown()

    def sendReposition(self, startPosition):
        if self.state == READY:
            self.rtsp_seq += 1
            my_sender = RequestSender(
                self.rtsp_socket, self.filename,
                self.rtp_port, self.rtsp_seq,
                self.session_id, step=self.step,
                startPosition=startPosition,
                audiobias=self.audio_bias,
                lowres=self.low_resolution,
                subtitleRequired=self.subtitleRequired
            )
            self.request_sent = PLAY
            my_sender.sendPlay()

    def sendDescribe(self):
        my_sender = RequestSender(
            self.rtsp_socket, self.filename,
            self.rtp_port, self.rtsp_seq,
            self.session_id)
        self.request_sent = DESCRIBE
        my_sender.sendDescribe()

    def openRtpPort(self):
        self.rtp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rtp_socket.settimeout(RTP_TIMEOUT)
        try:
            self.rtp_socket.bind(('', self.rtp_port))
        except:
            raise BindError

    def activateSliderUpdate(self):
        if self.state == PLAYING:
            pos = self.current_timestamp * 1000 // self.total_frames
            self.client_ui.updateSlider(pos)
            timer = threading.Timer(1, self.activateSliderUpdate)
            timer.start()

    def double(self):
        if self.step == 1:
            self.step = 2
        else:
            self.step = 1
        if self.state == PLAYING:
            self.changeSpeed = True
            self.sendPause()

    def mute(self):
        self.is_mute = not self.is_mute
        print(self.is_mute)

    def audioBias(self, bias):
        if self.state == PLAYING:
            self.audio_bias_set = True
            self.audio_bias = bias
            self.sendPause()

    def setLowResolution(self, isLowRes):
        self.low_resolution = isLowRes
        if self.state == PLAYING:
            self.changeResolution = True
            self.sendPause()

    def setFullScreen(self, isFullscreen):
        self.fullscreen = isFullscreen

    def showSubtitle(self, isSubtitleRequired):
        self.subtitleRequired = isSubtitleRequired
        if self.state == PLAYING:
            self.switchSubtitle = True
            self.sendPause()

class Client:
    def __init__(self, serveraddr, serverport, rtpport, url):
        self.server_addr = serveraddr
        self.server_port = serverport
        self.rtp_port = int(rtpport)
        self.url = url
        self.filename = self.url
        self.filelist = [
            'eve1.mp4',
            'eve2.mp4',
            'eve3.mp4'
        ]
        self.window = Tk()

    def createController(self):
        self.client_controller = ClientController(self.server_addr,
                                                  self.server_port, self.rtp_port,
                                                  self.filename, self.client_ui,
                                                  self.screen_width, self.screen_height)

    def createUI(self):
        inital_handlers = {
            'selectFile': self.selectFile
        }
        self.client_ui = ClientUI(self.window, self.filelist)
        self.client_ui.setHandlers(inital_handlers)
        self.screen_width, self.screen_height = self.client_ui.width, self.client_ui.height

    def bindHandlers(self):
        self.event_handlers = {
            'setup': self.client_controller.setup,
            'play': self.client_controller.play,
            'pause': self.client_controller.pause,
            'teardown': self.client_controller.teardown,
            'reposition': self.client_controller.reposition,
            'double': self.client_controller.double,
            'mute': self.client_controller.mute,
            'audioBias': self.client_controller.audioBias,
            'selectFile': self.selectFile,
            'setLowres': self.client_controller.setLowResolution,
            'setFullscreen': self.client_controller.setFullScreen,
            'showSubtitle': self.client_controller.showSubtitle
        }
        self.client_ui.setHandlers(self.event_handlers)

    def selectFile(self, filename):
        self.filename = self.url + '/' + filename
        self.createController()
        self.bindHandlers()

    def run(self):
        self.createUI()
        self.window.mainloop()
