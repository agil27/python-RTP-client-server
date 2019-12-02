MAX_UDP_BANDWIDTH = 65535
MAX_RTSP_BANDWIDTH = 1024
TIME_ELAPSED = 0.025

INIT, READY, PLAYING = 0, 1, 2
NULLREQ, SETUP, PLAY, PAUSE, TEARDOWN = -1, 0, 1, 2, 3
VIDEO, AUDIO = 0, 1

HEADER_SIZE = 12
RTP_TIMEOUT = 0.5
RTSP_TIMEOUT = 0.5

MIN_BUFFERING = 20