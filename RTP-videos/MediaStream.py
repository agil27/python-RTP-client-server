import cv2
import threading
import numpy as np
from RtpPacket import RtpPacket
from utils import LinkList
from math import ceil
from moviepy.editor import AudioFileClip
from Constants import *
from SrtParser import SrtParser
import os

class VideoStream:
    def __init__(self, filename, consume_semaphore, yield_semaphore, event, step=1, lowres=False):
        self.max_frame = 64000
        self.filename = filename
        self.cap = cv2.VideoCapture(self.filename)
        self.framerate = self.cap.get(5)
        self.low_res = lowres
        self.totalframes = int(self.cap.get(7))
        self.frameseq = 0
        self.current_frame = 0
        self.step = step
        self.consume_semaphore = consume_semaphore
        self.yield_semaphore = yield_semaphore
        self.event = event
        self.buf = LinkList()
        self.yield_thread = None
        self.subtitle_required = False
        self.subs = None
        self.createSubReader()

    def createSubReader(self):
        self.subname = self.filename.split('.')[0] + '.srt'
        if os.path.exists(self.subname):
            self.subs = SrtParser(self.subname, self.framerate, self.totalframes)

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
                photo_size = (480, 270) if not self.low_res else (320, 180)
                frame = cv2.resize(frame, photo_size, interpolation=cv2.INTER_AREA)
                if self.subs is not None:
                    text = self.subs.next()
                    if self.subtitle_required and text is not None:
                        cv2.putText(frame, text[1:], (50, 50), cv2.FONT_HERSHEY_COMPLEX, 0.5, (255, 255, 255))
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
        if self.subs is not None:
            self.subs.set(pos)
        self.current_frame = pos

    def setStep(self, step):
        self.step = step

    def setLowResolution(self, lowres):
        self.low_res = lowres

    def setSubtitles(self, subtitleRequired):
        if subtitleRequired:
            if self.subs is not None:
                self.subtitle_required = True
        else:
            self.subtitle_required = False


class AudioStream:
    def __init__(self, filename, consume_semaphore, yield_semaphore, event, step=1, vfps=DEFAULT_VIDEO_FRAMERATE):
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
        self.vfps = vfps
        self.setAPV(self.vfps)
        self.arrbuf = np.zeros((self.apv, 2), dtype=np.float32)
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
            subclip = self.clip.subclip(self.current_clip * self.apv / self.samplerate,
                                        (self.current_clip + 1) * self.apv / self.samplerate)
            for (i, frame) in enumerate(subclip.iter_frames()):
                self.arrbuf[i % self.apv][0] = frame[0]
                self.arrbuf[i % self.apv][1] = frame[1]
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

    def setStep(self, step):
        self.step = step

    def setBias(self, bias):
        self.current_clip += bias

    def setAPV(self, vfps):
        self.apv = 4 * int(self.samplerate / vfps)
