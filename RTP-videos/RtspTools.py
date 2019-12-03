from Constants import *
import time
import re
from Exception import *

class ResponseParser:
    def __init__(self, data, request_sent):
        print('\nReceived: ', data)
        self.request_sent = request_sent
        self.cseq = None
        self.parse(data)


    def parse(self, data):
        try:
            lines = str(data).split('\n')
            self.cseq = int(lines[1].split(' ')[1])
            self.session_id = 0
            if self.request_sent in [SETUP, PLAY]:
                self.session_id = lines[3].split(' ')[1]
            elif self.request_sent == PAUSE:
                self.session_id = lines[2].split(' ')[1]
            if self.session_id[-1] == ';':
                self.session_id = self.session_id[:-1]
            self.session_id = int(self.session_id)
            self.status_code = int(lines[0].split(' ')[1])
        except:
            raise ParseError


    def getSeq(self):
        return self.cseq


    def getSessionId(self):
        return self.session_id


    def getStatusCode(self):
        return self.status_code


class RequestSender():
    def __init__(self, socket, filename, port, cseq, session):
        self.socket = socket
        self.filename = filename,
        self.port = port
        self.cseq = cseq
        self.session = session


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
            'Session: %d' % (self.filename, self.cseq, self.session)
        self.send(request)


    def sendPause(self):
        request = 'PAUSE %s RTSP/1.0\n' \
            'CSeq: %d\n' \
            'Session: %d' % (self.filename, self.cseq, self.session)
        self.send(request)


    def sendTeardown(self):
        request = 'PAUSE %s RTSP/1.0\n' \
            'CSeq: %d\n' \
            'Session: %d' % (self.filename, self.cseq, self.session)
        self.send(request)


class ResponseSender:
    def __init__(self, socket, cseq, session_id, url, local_ip, client_rtp_port, client_rtcp_port, server_rtp_port, server_rtcp_port):
        self.socket = socket
        self.cseq = cseq
        self.session_id = session_id
        self.url = url
        self.local_ip = local_ip
        self.client_rtp_port, self.client_rtcp_port = client_rtp_port, client_rtcp_port
        self.server_rtp_port, self.server_rtcp_port = server_rtp_port, server_rtcp_port


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
        sdp = 'v=0\r\n' \
              'o=- 9%d 1 IN IP4 %s\r\n' \
              't=0 0\r\n' \
              'a=control:*\r\n' \
              'm=video 0 RTP/AVP 96\r\n' \
              'a=rtpmap:96 H264/90000\r\n' \
              'a=control:track0\r\n' % (time.time(), self.local_ip)
        response = 'RTSP/1.0 200 OK\r\n' \
                'CSeq: %d\r\n' \
                'Content-Base: %s\r\n' \
                'Content-type: application/sdp\r\n' \
                'Content-length: %d\r\n\r\n' \
                '%s' % (self.cseq, self.url, len(sdp), sdp)
        self.send(response)


class RequestParser:
    def __init__(self, data):
        print('Receive: ', data)
        self.method = None
        self.url = None
        self.version = None
        self.cseq = None
        self.client_rtp_port, self.client_rtcp_port = None, None

        self.parse(data)


    def strToMethod(self, str):
        return METHOD_MAP[str]


    def parse(self, data):
        lines = data.split('\n')
        info = lines[0].split(' ')
        self.method, self.url, self.version = info[0], info[1], info[2]
        self.method = self.strToMethod(self.method)
        self.cseq = int(lines[1][5:])
        if self.method == SETUP:
            match = re.search(r'client_port\s*=\s*(\d+)-(\d+)', lines[2]).groups()
            self.client_rtp_port, self.client_rtcp_port = int(match[0]), int(match[1])


    def getMethod(self):
        return self.method


    def getCseq(self):
        return self.cseq


    def getUrl(self):
        return self.url


    def getClientPorts(self):
        return self.client_rtp_port, self.client_rtcp_port



