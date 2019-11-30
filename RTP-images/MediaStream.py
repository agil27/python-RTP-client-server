class MediaStream:
    def __init__(self, type, filename):
        self.max_frame = 1 << 14
        self.filename = filename
        self.type = type
        if self.type == 'pictures':
            self.num_frame = len(filename)
        print('num_frame: ', self.num_frame)
        self.frameseq = 0


    def nextFrame(self):
        if self.type == 'pictures':
            if self.frameseq == self.num_frame:
                return
            else:
                with open(self.filename[self.frameseq], 'rb') as file:
                    data = file.read(self.max_frame)
                self.frameseq += 1
                return data, self.frameseq

