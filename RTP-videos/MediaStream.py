import cv2
import threading
import numpy as np
from RtpPacket import RtpPacket
from utils import Queue
from math import ceil
from moviepy.editor import AudioFileClip

BUF_SIZE = 1
VIDEO_FPS = 30
AUDIO_FPS = 48000
APV = AUDIO_FPS // VIDEO_FPS

class MediaStream:
    def __init__(self, filename, seph1, seph2, event, buf_size=BUF_SIZE):
        self.max_frame = 64000
        self.filename = filename
        self.buf_size = buf_size
        self.cap = cv2.VideoCapture(self.filename)
        self.frameseq = 0
        self.seph1 = seph1
        self.seph2 = seph2
        self.event = event
        self.buf = Queue(self.buf_size)
        self.yield_thread = None


    def packRTP(self, payload, seq, isLast):
        V, P, X, CC, PT, seqNum, M, SSRC = 2, 0, 0, 0, 26, seq, 0, 0
        if isLast:
            M = 1
        rtpPacket = RtpPacket()
        rtpPacket.encode(V, P, X, CC, seqNum, M, PT, SSRC, payload)
        return rtpPacket.getPacket()


    def yieldFrame(self):
        if self.yield_thread is None:
            self.yield_thread = threading.Thread(target=self.getFrame)
            self.yield_thread.setDaemon(True)
            self.yield_thread.start()


    def nextFrame(self):
        if self.buf.isEmpty():
            data = None
        else:
            data = self.buf.pop()
        return data


    def getFrame(self):
        while True:
            self.event.wait()
            if not self.buf.isFull():
                res, frame = self.cap.read()
                if res:
                    frame = cv2.resize(frame, (480, 270), interpolation=cv2.INTER_AREA)
                    stashed = cv2.imencode('.jpg', frame)[1]
                    stashed = np.array(stashed).tobytes()
                    num_slices = ceil(len(stashed) / self.max_frame)
                    for i in range(num_slices):
                        self.seph2.acquire()
                        if i < num_slices - 1:
                            slice = stashed[i * self.max_frame:(i + 1) * self.max_frame]
                        else:
                            slice = stashed[i * self.max_frame:]
                        self.frameseq += 1
                        slice = self.packRTP(slice, self.frameseq, i == num_slices - 1)
                        self.buf.push(slice)
                        self.seph1.release()
                else:
                    break


class AudioStream:
    def __init__(self, filename, seph1, seph2, event, buf_size=BUF_SIZE):
        self.max_frame = 1000
        self.filename = filename
        self.buf_size = buf_size
        self.clip = AudioFileClip(self.filename).iter_frames()
        self.frameseq = 0
        self.seph1 = seph1
        self.seph2 = seph2
        self.event = event
        self.buf = Queue(self.buf_size)
        self.bytesbuf = b''
        self.yield_thread = None


    def packRTP(self, payload, seq, isLast):
        V, P, X, CC, PT, seqNum, M, SSRC = 2, 0, 0, 0, 97, seq, 0, 0
        if isLast:
            M = 1
        rtpPacket = RtpPacket()
        rtpPacket.encode(V, P, X, CC, seqNum, M, PT, SSRC, payload)
        return rtpPacket.getPacket()


    def yieldFrame(self):
        if self.yield_thread is None:
            self.yield_thread = threading.Thread(target=self.getFrame)
            self.yield_thread.setDaemon(True)
            self.yield_thread.start()


    def nextFrame(self):
        if self.buf.isEmpty():
            data = None
        else:
            data = self.buf.pop()
        return data


    def getFrame(self):
        for (i, frame) in enumerate(self.clip):
            self.event.wait()
            if not self.buf.isFull():
                self.bytesbuf = self.bytesbuf + np.array(frame).tobytes()
                if (i + 1) % 1600 == 0:
                    self.seph2.acquire()
                    self.frameseq += 1
                    slice = self.packRTP(self.bytesbuf, self.frameseq, True)
                    self.buf.push(slice)
                    self.seph1.release()
                    self.bytesbuf = b''

