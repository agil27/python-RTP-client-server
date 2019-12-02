import socket
import threading
import re
from MediaStream import MediaStream, AudioStream


MAX_BUF_LEN = 1024
SERVER_PORT = 8554
SERVER_RTP_PORT = 55532
SERVER_RTCP_PORT = 55533
FILENAME = 'videos/eve.mp4'
TIME_ELAPSED = 0.033
BUF_SIZE = 1


class RTPCon:
    '''
    处理单个客户类端连接的类
    '''


    def __init__(self, con, addr, filename=FILENAME, buf_size=BUF_SIZE):
        '''
        :param con: 通信套接字
        :param addr: 客户端地址
        '''
        self.server_rtp_port = SERVER_RTP_PORT
        self.server_rtcp_port = SERVER_RTCP_PORT
        self.con = con
        self.addr = addr
        self.client_rtcp_port = 0
        self.client_rtp_port = 0
        self.client_audio_port = 0
        self.local_ip = con.getsockname()[0]
        self.session_id = 66334873
        self.media = filename
        self.rtp_socket = None
        self.event = None
        self.buf_size = buf_size
        self.state = 'READY'
        self.client_thread = None
        self.play_thread = None
        self.audio_thread = None


    def play(self):
        while True:
            self.event.wait()
            self.seph1.acquire()
            frame = self.stream.nextFrame()
            if frame is not None:
                self.rtp_socket.sendto(frame, (self.addr[0], self.client_rtp_port))
                #time.sleep(TIME_ELAPSED)
                self.seph2.release()
            else:
                break


    def audioPlay(self):
        while True:
            self.event.wait()
            self.aseph1.acquire()
            frame = self.astream.nextFrame()
            if frame is not None:
                self.audio_socket.sendto(frame, (self.addr[0], self.client_audio_port))
                #time.sleep(TIME_ELAPSED)
                self.aseph2.release()
            else:
                break


    def handleOptions(self, cseq):
        resp = 'RTSP/1.0 200 OK\r\nCSeq: %d\r\nPublic: OPTIONS, DESCRIBE, SETUP, PLAY\r\n\r\n' % cseq
        self.con.send(resp.encode('utf-8'))

    '''
    def handleDescribe(self, cseq, url):
        sdp = 'v=0\r\n' \
            'o=- 9%d 1 IN IP4 %s\r\n' \
            'o=- 9%ld 1 IN IP4 %s\r\n' \
            't=0 0\r\n' \
            'a=control:*\r\n' \
            'm=video 0 RTP/AVP 96\r\n' \
            'a=rtpmap:96 H264/90000\r\n' \
            'a=control:track0\r\n' % (time.time(), self.local_ip)
        resp = 'RTSP/1.0 200 OK\r\n' \
            'CSeq: %d\r\n' \
            'Content-Base: %s\r\n' \
            'Content-type: application/sdp\r\n' \
            'Content-length: %d\r\n\r\n' \
            '%s' % (cseq, url, len(sdp), sdp)
        self.con.send(resp.encode('utf-8'))
    '''

    def handleSetup(self, cseq):
        resp = 'RTSP/1.0 200 OK\r\n' \
            'CSeq: %d\r\n' \
            'Transport: RTP/AVP;unicast;client_port=%d-%d;server_port=%d-%d\r\n' \
            'Session: %d\r\n' \
            '\r\n' % (cseq, self.client_rtp_port, self.client_rtcp_port, self.server_rtp_port, self.server_rtcp_port, self.session_id)
        self.con.send(resp.encode('utf-8'))
        if self.state == 'READY':
            self.state = 'SETUP'
            self.rtp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.audio_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.seph1 = threading.Semaphore(0)
            self.seph2 = threading.Semaphore(self.buf_size)
            self.aseph1 = threading.Semaphore(0)
            self.aseph2 = threading.Semaphore(self.buf_size)
            self.event = threading.Event()
            self.stream = MediaStream(self.media, self.seph1, self.seph2, self.event, self.buf_size)
            self.astream = AudioStream(self.media, self.aseph1, self.aseph2, self.event, self.buf_size)


    def handlePlay(self, cseq):
        resp = 'RTSP/1.0 200 OK\r\n' \
            'CSeq: %d\r\n' \
            'Range: npt=0.000-\r\n' \
            'Session: %d; timeout=60\r\n\r\n' % (cseq, self.session_id)
        self.con.send(resp.encode('utf-8'))
        if self.state == 'SETUP' or 'PAUSE':
            self.state = 'PLAY'
            self.event.set()
            self.stream.yieldFrame()
            self.astream.yieldFrame()
            if self.play_thread is None:
                self.play_thread = threading.Thread(target=self.play)
                self.play_thread.setDaemon(True)
                self.play_thread.start()
            if self.audio_thread is None:
                self.audio_thread = threading.Thread(target=self.audioPlay)
                self.audio_thread.setDaemon(True)
                self.audio_thread.start()


    def handlePause(self, cseq):
        print('\nPaused...')
        self.event.clear()
        resp = 'RTSP/1.0 200 OK\r\nCSeq: %d\r\nSession: %d\r\n\r\n' % (cseq, self.session_id)
        self.con.send(resp.encode('utf-8'))


    def handleTeardown(self, cseq):
        resp = 'RTSP/1.0 200 OK\r\nCSeq: %d\r\nSession: %d\r\n\r\n' % (cseq, self.session_id)
        self.event.clear()
        self.con.send(resp.encode('utf-8'))
        self.state = 'READY'


    def parseRTSPCommand(self, cmd):
        print('Received: ', cmd)
        lines = cmd.split('\n')
        match = lines[0].split(' ')
        method, url, version = match[0], match[1], match[2]
        cseq = int(lines[1][5:])
        if method == 'SETUP':
            match = re.search(r'client_port\s*=\s*(\d+)-(\d+)', lines[2]).groups()
            self.client_rtp_port, self.client_rtcp_port = int(match[0]), int(match[1])
            self.client_audio_port = self.client_rtp_port + 2
            self.handleSetup(cseq)
        if method == 'OPTIONS':
            self.handleOptions(cseq)
        #if method == 'DESCRIBE':
        #    self.handleDescribe(cseq, url)
        if method == 'PLAY':
            self.handlePlay(cseq)
        if method == 'TEARDOWN':
            self.handleTeardown(cseq)
        if method == 'PAUSE':
            self.handlePause(cseq)


    def process(self):
        while True:
            data = self.con.recv(MAX_BUF_LEN)
            if data:
                data = data.decode('utf-8')
                self.parseRTSPCommand(data)
            else:
                break
        self.con.close()


    def run(self):
        '''
        :param con: 传输信道
        :param addr: ip地址
        :return: None
        处理一个客户端的连接
        '''
        self.client_thread = threading.Thread(target=self.process)
        self.client_thread.setDaemon(True)
        self.client_thread.start()


class RTPServer:
    def __init__(self, port=SERVER_PORT):
        self.port = port
        self.rtsp_sock = None


    def run(self, max_con=5):
        '''
        :param max_con: 最大连接数量
        :return: None
        建立监听，如果有客户端连接那么开新线程处理
        '''
        self.rtsp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.rtsp_sock.bind(('0.0.0.0', self.port))
        self.rtsp_sock.listen(max_con)

        while True:
            con, addr = self.rtsp_sock.accept()
            new_con = RTPCon(con, addr)
            # self.client_cons.push(new_con)
            new_con.run()


def main():
    my_server = RTPServer()
    my_server.run()


if __name__ == '__main__':
    main()