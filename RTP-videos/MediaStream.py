import cv2
import threading
import numpy as np
from RtpPacket import RtpPacket
from utils import LinkList
from math import ceil
from moviepy.editor import AudioFileClip


VIDEO_FPS = 29.7
AUDIO_FPS = 48000
APV = int(AUDIO_FPS / VIDEO_FPS)


class VideoStream:
    def __init__(self, filename, consume_semaphore, yield_semaphore, event):
        self.max_frame = 64000
        self.filename = filename
        self.cap = cv2.VideoCapture(self.filename)
        #print(self.cap.get(5))
        self.frameseq = 0
        self.consume_semaphore = consume_semaphore
        self.yield_semaphore = yield_semaphore
        self.event = event
        self.buf = LinkList()
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
        data = self.buf.pop()
        return data


    def getFrame(self):
        while True:
            self.event.wait()
            res, frame = self.cap.read()
            if res:
                frame = cv2.resize(frame, (480, 270), interpolation=cv2.INTER_AREA)
                stashed = cv2.imencode('.jpg', frame)[1]
                stashed = np.array(stashed).tobytes()
                num_slices = ceil(len(stashed) / self.max_frame)
                for i in range(num_slices):
                    self.yield_semaphore.acquire()
                    if i < num_slices - 1:
                        slice = stashed[i * self.max_frame:(i + 1) * self.max_frame]
                    else:
                        slice = stashed[i * self.max_frame:]
                    self.frameseq += 1
                    slice = self.packRTP(slice, self.frameseq, i == num_slices - 1)
                    self.buf.push(slice)
                    self.consume_semaphore.release()
            else:
                break


class AudioStream:
    def __init__(self, filename, consume_semaphore, yield_semaphore, event):
        self.max_frame = 64000
        self.filename = filename
        self.clip = AudioFileClip(self.filename).iter_frames()
        self.frameseq = 0
        self.consume_semaphore = consume_semaphore
        self.yield_semaphore = yield_semaphore
        self.event = event
        self.buf = LinkList()
        self.arrbuf = np.zeros((APV, 2), dtype=np.float32)
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
        data = self.buf.pop()
        return data


    def getFrame(self):
        for (i, frame) in enumerate(self.clip):
            self.event.wait()
            self.arrbuf[i % APV][0] = frame[0]
            self.arrbuf[i % APV][1] = frame[1]
            if (i + 1) % APV == 0:
                self.yield_semaphore.acquire()
                self.frameseq += 1
                slice = self.arrbuf.tobytes()
                slice = self.packRTP(slice, self.frameseq, True)
                self.buf.push(slice)
                self.consume_semaphore.release()

