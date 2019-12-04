import cv2
import threading
import numpy as np
from RtpPacket import RtpPacket
from utils import LinkList
from math import ceil
from moviepy.editor import AudioFileClip

VIDEO_FPS = 29.7
AUDIO_FPS = 44100
APV = 4 * int(AUDIO_FPS / VIDEO_FPS)


class VideoStream:
    def __init__(self, filename, consume_semaphore, yield_semaphore, event, step=1):
        self.max_frame = 64000
        self.filename = filename
        self.cap = cv2.VideoCapture(self.filename)
        self.framerate = self.cap.get(5)
        print(self.framerate)
        self.totalframes = self.cap.get(7)
        self.frameseq = 0
        self.current_frame = 0
        self.step = step
        self.consume_semaphore = consume_semaphore
        self.yield_semaphore = yield_semaphore
        self.event = event
        self.buf = LinkList()
        self.yield_thread = None

    def packRTP(self, payload, seq, current_frame, isLast):
        V, P, X, CC, PT, seqNum, M, SSRC, timestamp = 2, 0, 0, 0, 26, seq, 0, 0, current_frame
        if isLast:
            M = 1
        rtpPacket = RtpPacket()
        rtpPacket.encode(V, P, X, CC, seqNum, M, PT, SSRC, payload, current_frame)
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
            res, frame = None, None
            for i in range(self.step):
                res, frame = self.cap.read()
            if res:
                self.current_frame += self.step
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
                    slice = self.packRTP(slice, self.frameseq, self.current_frame, i == num_slices - 1)
                    self.buf.push(slice)
                    self.consume_semaphore.release()
            else:
                break

    def getTotalFrames(self):
        return self.totalframes

    def getFramerate(self):
        return self.framerate

    def setPosition(self, pos):
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, pos)
        self.current_frame = pos


class AudioStream:
    def __init__(self, filename, consume_semaphore, yield_semaphore, event, step=1):
        self.max_frame = 64000
        self.filename = filename
        self.clip = AudioFileClip(self.filename)
        self.samplerate = self.clip.fps
        self.frameseq = 0
        self.current_clip = 0.0
        self.step = step
        self.consume_semaphore = consume_semaphore
        self.yield_semaphore = yield_semaphore
        self.event = event
        self.buf = LinkList()
        self.arrbuf = np.zeros((APV, 2), dtype=np.float32)
        self.yield_thread = None

    def packRTP(self, payload, seq, isLast):
        V, P, X, CC, PT, seqNum, M, SSRC, timestamp = 2, 0, 0, 0, 97, seq, 0, 0, 0
        if isLast:
            M = 1
        rtpPacket = RtpPacket()
        rtpPacket.encode(V, P, X, CC, seqNum, M, PT, SSRC, payload, timestamp)
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
            subclip = self.clip.subclip(self.current_clip * APV / self.samplerate,
                                        (self.current_clip + 1) * APV / self.samplerate)
            for (i, frame) in enumerate(subclip.iter_frames()):
                self.arrbuf[i % APV][0] = frame[0]
                self.arrbuf[i % APV][1] = frame[1]
            self.yield_semaphore.acquire()
            self.frameseq += 1
            slice = self.arrbuf.tobytes()
            slice = self.packRTP(slice, self.frameseq, True)
            self.buf.push(slice)
            self.consume_semaphore.release()
            self.current_clip += self.step

    def getSamplerate(self):
        return self.samplerate

    def setPosition(self, pos):
        self.current_clip = (pos - 2) // 4
