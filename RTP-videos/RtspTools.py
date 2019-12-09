from Constants import *
import time
import re
from Exception import *


class ResponseParser:
    def __init__(self, data, request_sent):
        print('\nReceived: ', data)
        self.request_sent = request_sent
        self.cseq = None
        self.video_framerate, self.audio_samplerate, self.totalframes = 0, 0, 0
        self.parse(data)

    def parse(self, data):
        try:
            lines = str(data).split('\n')
            self.cseq = int(lines[1].split(' ')[1])
            self.session_id = 0
            if self.request_sent in [SETUP, PLAY]:
                self.session_id = lines[3].split(' ')[1]
            elif self.request_sent in [PAUSE, DESCRIBE, TEARDOWN]:
                self.session_id = lines[2].split(' ')[1]
            if self.session_id[-1] == ';':
                self.session_id = self.session_id[:-1]
            self.session_id = int(self.session_id)
            self.status_code = int(lines[0].split(' ')[1])
            if self.request_sent == DESCRIBE:
                self.video_framerate = float(lines[9][12:])
                self.audio_samplerate = int(lines[10][13:])
                self.totalframes = int(lines[11][14:])
        except:
            raise ParseError

    def getSeq(self):
        return self.cseq

    def getSessionId(self):
        return self.session_id

    def getStatusCode(self):
        return self.status_code

    def getAVParameters(self):
        return self.video_framerate, self.audio_samplerate, self.totalframes


class RequestSender():
    def __init__(
            self,
            socket, filename,
            port, cseq, session,
            startPosition=0, step=1,
            audiobias=0,
            lowres=False,
            subtitleRequired=False
    ):
        self.socket = socket
        self.filename = filename
        self.port = port
        self.cseq = cseq
        self.session = session
        self.start_position = startPosition
        self.step = step
        self.audio_bias = audiobias
        self.subtitleRequired = 'True' if subtitleRequired else 'False'
        if lowres:
            self.resolution = 'low'
        else:
            self.resolution = 'high'

    def send(self, request):
        print('\nSend: ', request)
        self.socket.send(request.encode())

    def sendSetup(self):
        request = 'SETUP %s RTSP/1.0\n' \
                  'CSeq: %d\n' \
                  'Transport: RTP/UDP; client_port=%d-%d' % (self.filename, self.cseq, self.port, self.port + 1)
        self.send(request)

    def sendPlay(self):
        request = 'PLAY %s RTSP/1.0\n' \
                  'CSeq: %d\n' \
                  'Session: %d\n' \
                  'Range: npt=%d-\n' \
                  'Step: %d\n' \
                  'AudioBias: %d\n' \
                  'Resolution: %s\n' \
                  'Subtitles: %s' % (self.filename, self.cseq,
                                     self.session, self.start_position,
                                     self.step, self.audio_bias, self.resolution, self.subtitleRequired)
        self.send(request)

    def sendPause(self):
        request = 'PAUSE %s RTSP/1.0\n' \
                  'CSeq: %d\n' \
                  'Session: %d' % (self.filename, self.cseq, self.session)
        self.send(request)

    def sendTeardown(self):
        request = 'TEARDOWN %s RTSP/1.0\n' \
                  'CSeq: %d\n' \
                  'Session: %d' % (self.filename, self.cseq, self.session)
        self.send(request)

    def sendDescribe(self):
        request = 'DESCRIBE %s RTSP/1.0\n' \
                  'CSeq: %d\n' \
                  'Session: %d' % (self.filename, self.cseq, self.session)
        self.send(request)


class ResponseSender:
    def __init__(
            self, socket,
            cseq, session_id, url, local_ip,
            client_rtp_port, client_rtcp_port,
            server_rtp_port, server_rtcp_port,
            video_framerate, audio_samplerate, total_frames
    ):
        self.socket = socket
        self.cseq = cseq
        self.session_id = session_id
        self.url = url
        self.local_ip = local_ip
        self.client_rtp_port, self.client_rtcp_port = client_rtp_port, client_rtcp_port
        self.server_rtp_port, self.server_rtcp_port = server_rtp_port, server_rtcp_port
        self.video_framerate, self.audio_samplerate, self.total_frames = video_framerate, audio_samplerate, total_frames

    def send(self, response):
        print('Send: ', response)
        self.socket.send(response.encode('utf-8'))

    def sendSetup(self):
        response = 'RTSP/1.0 200 OK\r\n' \
                   'CSeq: %d\r\n' \
                   'Transport: RTP/AVP;unicast;client_port=%d-%d;server_port=%d-%d\r\n' \
                   'Session: %d\r\n' \
                   '\r\n' % (self.cseq,
                             self.client_rtp_port, self.client_rtcp_port,
                             self.server_rtp_port, self.server_rtcp_port,
                             self.session_id)
        self.send(response)

    def sendPlay(self):
        response = 'RTSP/1.0 200 OK\r\n' \
                   'CSeq: %d\r\n' \
                   'Range: npt=0.000-\r\n' \
                   'Session: %d; timeout=60\r\n' \
                   '\r\n' % (self.cseq, self.session_id)
        self.send(response)

    def sendPause(self):
        response = 'RTSP/1.0 200 OK\r\n' \
                   'CSeq: %d\r\n' \
                   'Session: %d\r\n' \
                   '\r\n' % (self.cseq, self.session_id)
        self.send(response)

    def sendTeardown(self):
        response = 'RTSP/1.0 200 OK\r\n' \
                   'CSeq: %d\r\n' \
                   'Session: %d\r\n' \
                   '\r\n' % (self.cseq, self.session_id)
        self.send(response)

    def sendDescribe(self):
        sdp = 'm=video %d RTP/AVP 26\r\n' \
              'm=audio %d RTP/AVP 97\r\n' \
              'a=rtpmap:26 H264/90000\r\n' \
              'a=framerate:%f\r\n' \
              'a=samplerate:%d\r\n' \
              'a=totalframes:%d\r\n' \
              'c=IN IP4 %s\r\n' % (
                  self.client_rtp_port, self.client_rtp_port, self.video_framerate, self.audio_samplerate,
                  self.total_frames, self.local_ip)
        response = 'RTSP/1.0 200 OK\r\n' \
                   'CSeq: %d\r\n' \
                   'Session: %d\r\n' \
                   'Content-Base: %s\r\n' \
                   'Content-type: application/sdp\r\n' \
                   'Content-length: %d\r\n' \
                   '%s\r\n' \
                   '\r\n' % (self.cseq, self.session_id, self.url, len(sdp), sdp)
        self.send(response)

    def setAVParameters(self, framerate, samplerate, totalframes):
        self.video_framerate = framerate
        self.audio_samplerate = samplerate
        self.total_frames = totalframes


class RequestParser:
    def __init__(self, data):
        print('Receive: ', data)
        self.method = None
        self.url = None
        self.version = None
        self.cseq = None
        self.client_rtp_port, self.client_rtcp_port = None, None
        self.start_position = None
        self.subtitleRequired = False
        self.audio_bias = 0
        self.parse(data)

    def strToMethod(self, str):
        return METHOD_MAP[str]

    def parse(self, data):
        lines = data.split('\n')
        info = lines[0].split(' ')
        self.method, self.url, self.version = info[0], info[1], info[2]
        self.filename = re.search(r'rtp://\d{3}.\d+.\d+.\d+:\d+/(\S+)', self.url).groups()[0]
        self.method = self.strToMethod(self.method)
        self.cseq = int(lines[1][5:])
        if self.method == SETUP:
            match = re.search(r'client_port\s*=\s*(\d+)-(\d+)', lines[2]).groups()
            self.client_rtp_port, self.client_rtcp_port = int(match[0]), int(match[1])
        if self.method == PLAY:
            self.start_position = int(lines[3][11:-1])
            self.step = int(lines[4][6:])
            self.audio_bias = int(lines[5][11:])
            self.resolution = lines[6][12:]
            self.subtitleRequired = (lines[7][11:] == 'True')
            if self.resolution == 'high':
                self.lowres = False
            else:
                self.lowres = True

    def getMethod(self):
        return self.method

    def getCseq(self):
        return self.cseq

    def getUrl(self):
        return self.url

    def getClientPorts(self):
        return self.client_rtp_port, self.client_rtcp_port

    def getStartPosition(self):
        return self.start_position

    def getStep(self):
        return self.step

    def getAudioBias(self):
        return self.audio_bias

    def getFilename(self):
        return self.filename

    def isLowResolution(self):
        return self.lowres

    def isSubtitleRequired(self):
        return self.subtitleRequired
