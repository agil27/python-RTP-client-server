import socket
import threading
from MediaStream import VideoStream, AudioStream
from Constants import *
import random
from RtspTools import ResponseSender, RequestParser
from Exception import *


class ServerWorker:
    '''处理单个客户端连接'''

    def __init__(self, rtsp_socket, client_addr, filename=DEFAULT_FILENAME):
        self.server_rtp_port = SERVER_RTP_PORT
        self.server_rtcp_port = SERVER_RTCP_PORT
        self.rtsp_socket = rtsp_socket
        self.client_addr = client_addr[0]
        self.media = filename

        self.client_rtcp_port = 0
        self.client_rtp_port = 0
        self.local_ip = self.rtsp_socket.getsockname()[0]
        self.session_id = self.generateRandomSessionId()
        self.cseq = 0
        self.url = None
        self.audio_bias = 0

        self.event = threading.Event()
        self.state = INIT
        self.listen_thread = None
        self.video_thread = None
        self.audio_thread = None

        self.rtp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.video_yield_semaphore = threading.Semaphore(1)
        self.video_consume_semaphore = threading.Semaphore(0)
        self.audio_yield_semaphore = threading.Semaphore(1)
        self.audio_consume_semaphore = threading.Semaphore(0)
        self.synchronize_semaphore = threading.Semaphore(0)

        self.video_stream = None
        self.audio_stream = None
        self.total_frames = 0
        self.video_framerate = 0
        self.audio_samplerate = 0
        self.client_teardown = False

    def playVideo(self):
        while True:
            self.event.wait()
            self.video_consume_semaphore.acquire()
            frame = self.video_stream.nextFrame()
            if frame is not None:
                self.rtp_socket.sendto(frame, (self.client_addr, self.client_rtp_port))
                self.video_yield_semaphore.release()
                self.synchronize_semaphore.release()
                # self.event.wait(TIME_ELAPSED)
            else:
                break

    def playAudio(self):
        while True:
            # self.event.wait(TIME_ELAPSED)
            self.event.wait()
            self.audio_consume_semaphore.acquire()
            for i in range(4):
                self.synchronize_semaphore.acquire()
            frame = self.audio_stream.nextFrame()
            if frame is not None:
                self.rtp_socket.sendto(frame, (self.client_addr, self.client_rtp_port))
                self.audio_yield_semaphore.release()
            else:
                break

    def createThreads(self):
        if self.video_thread is None:
            self.video_thread = threading.Thread(target=self.playVideo)
            self.video_thread.setDaemon(True)
            self.video_thread.start()
        if self.audio_thread is None:
            self.audio_thread = threading.Thread(target=self.playAudio)
            self.audio_thread.setDaemon(True)
            self.audio_thread.start()

    def handleSetup(self):
        self.sender.sendSetup()
        if self.state == INIT:
            self.state = READY

    def handlePlay(self):
        self.sender.sendPlay()
        if self.state == READY:
            self.state = PLAYING
            self.createThreads()
            if self.start_position > 0:
                self.event.clear()
                self.video_stream.setPosition(self.start_position)
                self.audio_stream.setPosition(self.start_position)
            if self.audio_bias != 0:
                self.event.clear()
                self.audio_stream.setBias(self.audio_bias)
            self.video_stream.setStep(self.step)
            self.audio_stream.setStep(self.step)
            self.event.set()
            self.video_stream.yieldFrame()
            self.audio_stream.yieldFrame()

    def handlePause(self):
        self.sender.sendPause()
        if self.state == PLAYING:
            self.state = READY
            self.event.clear()

    def handleTeardown(self):
        self.sender.sendTeardown()
        self.event.clear()
        self.state = INIT
        self.client_teardown = True

    def handleDescribe(self):
        self.video_stream = VideoStream(self.media, self.video_consume_semaphore, self.video_yield_semaphore,
                                        self.event)
        self.audio_stream = AudioStream(self.media, self.audio_consume_semaphore, self.audio_yield_semaphore,
                                        self.event)
        self.total_frames = self.video_stream.getTotalFrames()
        self.video_framerate = self.video_stream.getFramerate()
        self.audio_samplerate = self.audio_stream.getSamplerate()
        self.sender.setAVParameters(self.video_framerate, self.audio_samplerate, self.total_frames)
        self.sender.sendDescribe()

    def handleRtspRequest(self, request):
        my_parser = RequestParser(request)
        method = my_parser.getMethod()
        self.url = my_parser.getUrl()
        self.cseq = my_parser.getCseq()
        self.media = FILENAME_PREFIX + '/' + my_parser.getFilename()
        if method == PLAY:
            self.start_position = my_parser.getStartPosition()
            self.step = my_parser.getStep()
            self.audio_bias = my_parser.getAudioBias()
        if method == SETUP:
            self.client_rtp_port, self.client_rtcp_port = my_parser.getClientPorts()
        self.sender = ResponseSender(
            self.rtsp_socket, self.cseq, self.session_id,
            self.url, self.local_ip,
            self.client_rtp_port, self.client_rtcp_port,
            self.server_rtp_port, self.server_rtcp_port,
            self.video_framerate, self.audio_samplerate, self.total_frames
        )
        if method == SETUP:
            self.handleSetup()
        if method == PLAY:
            self.handlePlay()
        if method == TEARDOWN:
            self.handleTeardown()
        if method == PAUSE:
            self.handlePause()
        if method == DESCRIBE:
            self.handleDescribe()

    def generateRandomSessionId(self):
        return random.randint(MIN_SESSION, MAX_SESSION)

    def listen(self):
        while True:
            try:
                data = self.rtsp_socket.recv(MAX_RTSP_BANDWIDTH)
                if data:
                    self.handleRtspRequest(data.decode('utf-8'))
                else:
                    break
            except:
                if self.client_teardown:
                    break
        self.rtsp_socket.close()

    def run(self):
        self.listen_thread = threading.Thread(target=self.listen)
        self.listen_thread.setDaemon(True)
        self.listen_thread.start()


class Server:
    def __init__(self, port=SERVER_RTSP_PORT):
        self.port = port
        self.listen_socket = None

    def run(self, max_connections=MAX_CONNECTIONS):
        self.listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listen_socket.bind(('0.0.0.0', self.port))
        self.listen_socket.listen(max_connections)

        while True:
            try:
                rtsp_socket, client_addr = self.listen_socket.accept()
                new_worker = ServerWorker(rtsp_socket, client_addr)
                new_worker.run()
            except:
                raise SocketError


def main():
    my_server = Server()
    my_server.run()


if __name__ == '__main__':
    main()
