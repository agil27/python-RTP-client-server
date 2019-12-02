from Constants import *

class ResponseParser:
    def __init__(self, data, request_sent):
        print('\nReceived: ', data)
        self.request_sent = request_sent
        self.cseq = None
        self.parse(data)


    def parse(self, data):
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