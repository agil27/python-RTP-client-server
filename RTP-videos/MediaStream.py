import cv2
import os
import threading

class MediaStream:
    def __init__(self, type, filename, sephamore):
        self.max_frame = 1 << 15
        self.filename = filename
        self.type = type
        if self.type == 'video':
            self.cap = cv2.VideoCapture(self.filename)
        self.frameseq = 0
        self.sephamore = sephamore

    def yieldNextFrame(self):
        threading.Thread(target=self.nextFrame).start()


    def getFrame(self):
        return self.data, self.frameseq


    def nextFrame(self):
        if self.type == 'video':
            res, frame = self.cap.read()
            frame = cv2.resize(frame, (853, 480), interpolation=cv2.INTER_AREA)
            if res:
                self.frameseq += 1
                stashed_img = 'stashed/stashed.jpg'
                cv2.imwrite(stashed_img, frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
                with open(stashed_img, 'rb') as f:
                    self.data = f.read(self.max_frame)
            else:
                self.data = None
            self.sephamore.release()
        else:
            return

