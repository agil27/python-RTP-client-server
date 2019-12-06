import socket, threading
from RtpPacket import RtpPacket
import time
from utils import LinkList
import sounddevice as sd
from Exception import *
from Constants import *
from RtspTools import ResponseParser, RequestSender
from ClientUI import ClientUI
from tkinter import Tk


class ClientController:
    def __init__(self, serveraddr, serverport, rtpport, url):
        self.server_addr = serveraddr
        self.server_port = serverport
        self.rtp_port = int(rtpport)
        self.url = url
        self.filename = url
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

        self.filelist = [
            'eve1.mp4',
            'eve2.mp4',
            'eve3.mp4'
        ]

        self.window = Tk()

    def run(self):
        self.connect()
        self.createUI()
        self.window.mainloop()

    def createUI(self):
        event_handlers = {
            'setup': self.setup,
            'play': self.play,
            'pause': self.pause,
            'teardown': self.teardown,
            'reposition': self.reposition,
            'double': self.double,
            'mute': self.mute,
            'audioBias': self.audioBias,
            'selectFile': self.selectFile
        }
        self.client_ui = ClientUI(self.window, event_handlers, self.filelist)

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
        if self.filename == self.url:
            return
        else:
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
                self.event.wait()
                self.video_consume_semaphore.acquire()
                current_frame, self.current_timestamp = self.retrieveFrame(mediatype=VIDEO)
                self.client_ui.updateMovie(current_frame)
                self.video_control_event.wait(TIME_ELAPSED)
            except:
                continue

    def playAudio(self):
        while self.video_buffer.len() < 20:
            pass
        while True:
            try:
                self.event.wait()
                self.audio_consume_semaphore.acquire()
                if not self.is_mute:
                    self.audio_stream.write(self.retrieveFrame(mediatype=AUDIO))
            except:
                continue

    def listenForRtp(self):
        print('\nListening...')
        while True:
            self.event.wait()
            try:
                data = self.rtp_socket.recv(MAX_UDP_BANDWIDTH)
            except:
                continue

            if data:
                packet = RtpPacket()
                packet.decode(data)
                current_frame_seq = packet.seqNum()
                marker = packet.getMarker()
                media_type = packet.getType()
                self.receiveIncomingPacket(packet, current_frame_seq, marker, media_type)

            if self.teardown_acked:
                self.rtp_socket.shudown(socket.SHUT_RDWR)
                self.rtp_socket.close()
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
            response = self.rtsp_socket.recv(MAX_RTSP_BANDWIDTH)
            if response:
                self.parseResponse(response.decode('utf-8'))
            if self.request_sent == TEARDOWN:
                self.rtsp_socket.shutdown(socket.SHUT_RDWR)
                self.rtsp_socket.close()
                break

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

    def handleTeardown(self):
        self.state = INIT
        self.teardown_acked = True

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
            my_sender.sendSetup()
            self.request_sent = SETUP

    def sendPlay(self):
        if self.state == READY:
            self.rtsp_seq += 1
            my_sender = RequestSender(
                self.rtsp_socket, self.filename,
                self.rtp_port, self.rtsp_seq,
                self.session_id, step=self.step,
                startPosition=self.current_timestamp,
                audiobias=self.audio_bias
            )
            my_sender.sendPlay()
            self.request_sent = PLAY

    def sendPause(self):
        if self.state == PLAYING:
            self.rtsp_seq += 1
            my_sender = RequestSender(self.rtsp_socket, self.filename, self.rtp_port, self.rtsp_seq, self.session_id)
            my_sender.sendPause()
            self.request_sent = PAUSE

    def sendTeardown(self):
        if self.state != INIT:
            self.rtsp_seq += 1
            my_sender = RequestSender(self.rtsp_socket, self.filename, self.rtp_port, self.rtsp_seq, self.session_id)
            my_sender.sendTeardown()
            self.request_sent = TEARDOWN

    def sendReposition(self, startPosition):
        if self.state == READY:
            self.rtsp_seq += 1
            my_sender = RequestSender(
                self.rtsp_socket, self.filename,
                self.rtp_port, self.rtsp_seq,
                self.session_id, step=self.step,
                startPosition=startPosition, audiobias=self.audio_bias)
            my_sender.sendPlay()
            self.request_sent = PLAY

    def sendDescribe(self):
        my_sender = RequestSender(
            self.rtsp_socket, self.filename,
            self.rtp_port, self.rtsp_seq,
            self.session_id)
        my_sender.sendDescribe()
        self.request_sent = DESCRIBE

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

    def selectFile(self, filename):
        self.filename = self.url + '/' + filename
