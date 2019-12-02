import socket, threading
from RtpPacket import RtpPacket
import time
from utils import LinkList
import sounddevice as sd
from Exception import *
from Constants import *
from RTSPTool import ResponseParser, RequestSender
from ClientUI import ClientUI
from tkinter import Tk

class ClientController:
    def __init__(self, serveraddr, serverport, rtpport, filename):
        self.server_addr = serveraddr
        self.server_port = serverport
        self.rtp_port = int(rtpport)
        self.filename = filename
        self.rtsp_seq = 0
        self.session_id = 0
        self.teardown_acked = False
        self.state = INIT
        self.request_sent = NULLREQ

        self.rtp_socket = None
        self.rtsp_socket = None

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
            'teardown': self.teardown
        }
        self.client_ui = ClientUI(self.window, event_handlers)


    def connect(self):
        self.rtsp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print(self.rtsp_socket, self.server_addr, self.server_port)
        try:
            self.rtsp_socket.connect((self.server_addr, self.server_port))
        except:
            raise ConnectionError


    def setup(self):
        if self.state == INIT:
            self.sendSetup()
        self.samplerate = 44100
        self.channels = 2
        self.audio_stream = sd.RawOutputStream(
            samplerate=self.samplerate,
            channels=self.channels,
            dtype='float32'
        )
        self.audio_stream.start()


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
            self.event.wait()
            self.video_consume_semaphore.acquire()
            self.client_ui.updateMovie(self.retrieveFrame(mediatype=VIDEO))


    def playAudio(self):
        while self.video_buffer.len() < 20:
            pass
        while True:
            self.event.wait()
            self.audio_consume_semaphore.acquire()
            self.audio_stream.write(self.retrieveFrame(mediatype=AUDIO))
            time.sleep(TIME_ELAPSED)


    def listenForRtp(self):
        print('\nListening...')
        while True:
            self.event.wait()
            try:
                data = self.rtp_socket.recv(MAX_UDP_BANDWIDTH)
                if data:
                    packet = RtpPacket()
                    packet.decode(data)
                    current_frame_seq = packet.seqNum()
                    marker = packet.getMarker()
                    media_type = packet.getType()
                    self.receiveIncomingPacket(packet, current_frame_seq, marker, media_type)
            except:
                raise SocketError
            if self.teardown_acked:
                self.rtp_socket.shudown(socket.SHUT_RDWR)
                self.rtp_socket.close()
                break


    def receiveIncomingPacket(self, packet, seq, marker, media_type):
        if media_type == VIDEO:
            if seq > self.video_frame_seq:
                self.video_frame_seq = seq
                payload = packet.getPayload()
                self.restoreFrame(payload, marker, VIDEO)
        if media_type == AUDIO:
            if seq > self.audio_frame_seq:
                self.audio_frame_seq = seq
                payload = packet.getPayload()
                self.restoreFrame(payload, marker, AUDIO)


    def restoreFrame(self, payload, marker, mediatype):
        if mediatype == VIDEO:
            self.frame_buffer += payload
            if marker:
                self.video_buffer.push(self.frame_buffer)
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
        my_parser = ResponseParser(data, self.request_sent)
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


    def handleSetup(self):
        self.state = READY
        self.openRtpPort()
        self.event = threading.Event()
        self.video_consume_semaphore = threading.Semaphore(0)
        self.audio_consume_semaphore = threading.Semaphore(0)


    def handlePlay(self):
        self.state = PLAYING


    def handlePause(self):
        self.state = READY
        self.event.clear()


    def handleTeardown(self):
        self.state = INIT
        self.teardown_acked = True


    def sendSetup(self):
        if self.state == INIT:
            self.receive_thread = threading.Thread(target=self.receiveResponse)
            self.receive_thread.setDaemon(True)
            self.receive_thread.start()
            self.rtsp_seq += 1
            my_sender = RequestSender(self.rtsp_socket, self.filename, self.rtp_port, self.rtsp_seq, self.session_id)
            my_sender.sendSetup()
            self.request_sent = SETUP


    def sendPlay(self):
        if self.state == READY:
            self.rtsp_seq += 1
            my_sender = RequestSender(self.rtsp_socket, self.filename, self.rtp_port, self.rtsp_seq, self.session_id)
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


    def openRtpPort(self):
        self.rtp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.rtp_socket.settimeout(RTP_TIMEOUT)
        try:
            self.rtp_socket.bind(('', self.rtp_port))
        except:
            raise BindError