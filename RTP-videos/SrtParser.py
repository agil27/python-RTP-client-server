import srt


class SubEntry:
    def __init__(self, content, start_timedelta, end_timedelta, framerate):
        self._content = content
        self._start_frame = int((start_timedelta.seconds + start_timedelta.microseconds / 1000000) * framerate)
        self._end_frame = int((end_timedelta.seconds + end_timedelta.microseconds / 1000000) * framerate)

    def content(self):
        return self._content

    def start(self):
        return self._start_frame

    def end(self):
        return self._end_frame


class SrtParser:
    def __init__(self, filename, framerate, totalframes, encoding='utf-8'):
        self.filename = filename
        self.framerate = framerate
        self.totalframes = totalframes
        self.encoding = encoding
        self.position = 0
        self.process()
        self.createReader()

    def process(self):
        raw = ''
        with open(self.filename, 'r', encoding=self.encoding) as f:
            raw = f.read()
        subs = list(srt.parse(raw))
        self.subs = [SubEntry(s.content, s.start, s.end, self.framerate) for s in subs]
        self.num_subs = len(self.subs)

    def createReader(self):
        currentIndex = 0
        self.reader = ['' for i in range(self.totalframes)]
        for i in range(self.totalframes):
            if self.subs[currentIndex].end() < i:
                currentIndex += 1
            if currentIndex < self.num_subs:
                if self.subs[currentIndex].start() <= i and self.subs[currentIndex].end() >= i:
                    self.reader[i] = self.subs[currentIndex].content()
            else:
                break

    def next(self):
        data = self.reader[self.position]
        self.position += 1
        return data

    def set(self, pos):
        self.position = pos