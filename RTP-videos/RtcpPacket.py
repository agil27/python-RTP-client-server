RTCP_HEADER_SIZE = 8
RTCP_SENDER_INFO_SIZE = 20
REPORT_BLOCK_SIZE = 24


def fillword(target, integer, index):
    '''
    填充4个字节
    :param target: 被填充的字节流
    :param integer: 被填入的整数
    :param index: 起始地址
    :return:
    '''
    target[index] = integer >> 24
    target[index + 1] = (integer >> 16) & 255
    target[index + 2] = (integer >> 8) & 255
    target[index + 3] = integer & 255


def getWord(target, index):
    '''
    取出4个字节
    :param target: 被填充的字节流
    :param index: 起始地址
    :return: 得到的4个字节组成的整数
    '''
    return (target[index] << 24) | (target[index + 1] << 16) | (target[index + 2] << 8) | target[index + 3]


class ReportBlock:
    def __init__(self):
        self.block = bytearray(REPORT_BLOCK_SIZE)

    def encode(self, ssrc, frac, cumulative, seq, jitter, lsr, dlsr):
        fillword(self.block, ssrc, 0)
        fillword(self.block, (frac << 24) | cumulative, 4)
        fillword(self.block, seq, 8)
        fillword(self.block, jitter, 12)
        fillword(self.block, lsr, 16)
        fillword(self.block, dlsr, 20)

    def decode(self, blockStream):
        self.block = blockStream

    def getBlock(self):
        return self.block

    def ssrc(self):
        return getWord(self.block, 0)

    def frac(self):
        return self.block[4]

    def cumulative(self):
        return (self.block[5] << 16) | (self.block[6] << 8) | (self.block[7])

    def seq(self):
        return getWord(self.block, 8)

    def jitter(self):
        return getWord(self.block, 12)

    def lsr(self):
        return getWord(self.block, 16)

    def dlsr(self):
        return getWord(self.block, 20)


class RtcpPacket:
    def __init__(self):
        pass

    def encode(self, version, padding, rc, pt, l, ssrc, ntptimestamp, rtptimestamp, pc, oc, blocks, ext, isSender):
        '''
        根据所给的参数编码RTCP包
        :param version: 协议版本
        :param padding: 填充
        :param rc: 报告块（Report Block)的数量
        :param pt: 包类型（Packet Type）
        :param l: 包长度
        :param ssrc: 同步源标识符
        :param ntptimestamp: NTP时间戳（64位）
        :param rtptimestamp: RTP时间戳（32位）
        :param pc: 发送的报文数
        :param oc: 发送的字节数
        :param blocks: 报告块的列表
        :param ext: 附加信息
        :param isSender: 是否为发送者包
        :return: None
        '''
        self.isSender = isSender
        self.header = bytearray(RTCP_HEADER_SIZE)
        self.header[0] = (version << 6) | (padding << 5) | rc
        self.header[1] = pt
        self.header[2] = l >> 8
        self.header[3] = l & 255
        fillword(self.header, ssrc, 4)

        self.senderInfo = bytearray(RTCP_SENDER_INFO_SIZE)
        ntpmsw, ntplsw = ntptimestamp >> 32, ntptimestamp & (1 << 32 - 1)
        fillword(self.senderInfo, ntpmsw, 0)
        fillword(self.senderInfo, ntplsw, 4)
        fillword(self.senderInfo, rtptimestamp, 8)
        fillword(self.senderInfo, pc, 12)
        fillword(self.senderInfo, oc, 16)
        self.blocks = blocks
        self.extensions = ext

    def decode(self, byteStream):
        '''
        根据RTCP字节流解码出信息
        :param byteStream: RTCP字节流
        :return:
        '''
        self.header = bytearray(byteStream[:RTCP_HEADER_SIZE])
        self.senderInfo = byteStream[RTCP_HEADER_SIZE:RTCP_HEADER_SIZE + RTCP_SENDER_INFO_SIZE]
        blockStart = RTCP_HEADER_SIZE + RTCP_SENDER_INFO_SIZE
        blockNumber = self.countOfReportBlocks()
        self.blocks = []
        for i in range(blockNumber):
            blockStream = byteStream[blockStart + i * REPORT_BLOCK_SIZE:blockStart + (i + 1) * REPORT_BLOCK_SIZE]
            block = ReportBlock()
            block.decode(blockStream)
            self.blocks.append(block)
        self.extensions = byteStream[blockStart + blockNumber * REPORT_BLOCK_SIZE:]

    def version(self):
        return int(self.header[0] >> 6)

    def countOfReportBlocks(self):
        return self.header[0] & 31

    def lengthOfPacket(self):
        return self.header[2] << 8 + self.header[3]

    def getBlockByIndex(self, index):
        return self.blocks[index]

    def ssrc(self):
        return getWord(self.header, 4)

    def ntpTimestamp(self):
        return (getWord(self.senderInfo, 0) << 32) | (getWord(self.senderInfo, 4))

    def rtpTimestamp(self):
        return getWord(self.senderInfo, 8)

    def getPacket(self):
        '''
        :return: 可以直接发送RTCP包（字节流)
        '''
        packet = self.header
        if self.isSender:
            packet = packet + self.senderInfo
        for b in self.blocks:
            packet = packet + b.getBlock()
        packet = packet + self.extensions
        return packet
