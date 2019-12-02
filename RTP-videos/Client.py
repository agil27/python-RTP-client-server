from tkinter import *
import tkinter.messagebox as tkMessageBox
from PIL import Image, ImageTk
import socket, threading
from io import BytesIO
from RtpPacket import RtpPacket
import time
from utils import LinkList
import sounddevice as sd

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"
MAX_UDP = 65535
TIME_ELAPSED = 0.033
MAX_FRAMES = 25

class Client:
	INIT = 0
	READY = 1
	PLAYING = 2
	state = INIT
	
	SETUP = 0
	PLAY = 1
	PAUSE = 2
	TEARDOWN = 3
	
	# Initiation..
	def __init__(self, master, serveraddr, serverport, rtpport, filename):
		self.master = master
		self.master.protocol("WM_DELETE_WINDOW", self.handler)
		self.createWidgets()
		self.serverAddr = serveraddr
		self.serverPort = int(serverport)
		self.rtpPort = int(rtpport)
		self.fileName = filename
		self.rtspSeq = 0
		self.sessionId = 0
		self.requestSent = -1
		self.teardownAcked = 0
		self.connectToServer()
		self.vframeNbr = 0
		self.aframeNbr = 0
		self.frameBuf = b''
		self.videoBuf = LinkList()
		self.audioBuf = LinkList()
		self.play_thread = None
		self.update_thread = None
		self.audio_thread = None

	def createWidgets(self):
		"""Build GUI."""
		# Create Setup button
		self.setup = Button(self.master, width=20, padx=3, pady=3)
		self.setup["text"] = "Setup"
		self.setup["command"] = self.setupMovie
		self.setup.grid(row=1, column=0, padx=2, pady=2)
		
		# Create Play button		
		self.start = Button(self.master, width=20, padx=3, pady=3)
		self.start["text"] = "Play"
		self.start["command"] = self.playMovie
		self.start.grid(row=1, column=1, padx=2, pady=2)
		
		# Create Pause button			
		self.pause = Button(self.master, width=20, padx=3, pady=3)
		self.pause["text"] = "Pause"
		self.pause["command"] = self.pauseMovie
		self.pause.grid(row=1, column=2, padx=2, pady=2)
		
		# Create Teardown button
		self.teardown = Button(self.master, width=20, padx=3, pady=3)
		self.teardown["text"] = "Teardown"
		self.teardown["command"] =  self.exitClient
		self.teardown.grid(row=1, column=3, padx=2, pady=2)
		
		# Create a label to display the movie
		self.label = Label(self.master, height=19)
		self.label.grid(row=0, column=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5) 
	
	def setupMovie(self):
		"""Setup button handler."""
		if self.state == self.INIT:
			self.sendRtspRequest(self.SETUP)
		self.samplerate = 44100
		self.channels = 2
		self.audioStream = sd.RawOutputStream(
			samplerate=self.samplerate,
			channels=self.channels,
			dtype='float32'
		)
		self.audioStream.start()

	def exitClient(self):
		"""Teardown button handler."""
		self.sendRtspRequest(self.TEARDOWN)		
		self.master.destroy() # Close the gui window
		#os.remove(CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT) # Delete the cache image from video

	def pauseMovie(self):
		"""Pause button handler."""
		if self.state == self.PLAYING:
			self.sendRtspRequest(self.PAUSE)

	def playMovie(self):
		"""Play button handler."""
		if self.state == self.READY:
			self.playEvent.set()
			self.sendRtspRequest(self.PLAY)
			if self.play_thread is None:
				self.play_thread = threading.Thread(target=self.listenRtp)
				self.play_thread.setDaemon(True)
				self.play_thread.start()
			if self.update_thread is None:
				self.update_thread = threading.Thread(target=self.updateMovie)
				self.update_thread.setDaemon(True)
				self.update_thread.start()
			if self.audio_thread is None:
				self.audio_thread = threading.Thread(target=self.updateAudio)
				self.audio_thread.setDaemon(True)
				self.audio_thread.start()

	def listenRtp(self):		
		"""Listen for RTP packets."""
		print('\nListening...')
		while True:
			self.playEvent.wait()
			try:
				data = self.rtpSocket.recv(MAX_UDP)
				if data:
					rtpPacket = RtpPacket()
					rtpPacket.decode(data)
					currFrameNbr = rtpPacket.seqNum()
					marker = rtpPacket.getMarker()
					mediatype = rtpPacket.getType()
					if mediatype == 'video':
						if currFrameNbr > self.vframeNbr:
							self.vframeNbr = currFrameNbr
							payload = rtpPacket.getPayload()
							self.restoreFrame(payload, marker, 'video')
					elif mediatype == 'audio':
						if currFrameNbr > self.aframeNbr:
							self.aframeNbr = currFrameNbr
							payload = rtpPacket.getPayload()
							self.restoreFrame(payload, marker, 'audio')
			except:
				if self.teardownAcked == 1:
					self.rtpSocket.shutdown(socket.SHUT_RDWR)
					self.rtpSocket.close()
					break

	def restoreFrame(self, payload, marker, mediatype):
		if mediatype == 'video':
			self.frameBuf += payload
			if marker:
				self.videoBuf.push(self.frameBuf)
				self.seph.release()
				self.frameBuf = b''
		elif mediatype == 'audio':
			self.audioBuf.push(payload)
			self.aseph.release()

	def updateMovie(self):
		while self.videoBuf.len() < 20:
			pass
		while True:
			try:
				# 播放视频
				self.playEvent.wait()
				self.seph.acquire()
				frame = self.videoBuf.pop()
				image_tk = Image.open(BytesIO(frame))
				photo = ImageTk.PhotoImage(image_tk)
				self.label.configure(image=photo, height=360)
				self.label.image = photo
				#time.sleep(TIME_ELAPSED)
			except:
				print('Error displaying video stream')

	def updateAudio(self):
		while self.videoBuf.len() < 20:
			pass
		while True:
			try:
				# 播放音频
				self.playEvent.wait()
				self.aseph.acquire()
				clip = self.audioBuf.pop()
				self.audioStream.write(clip)
				time.sleep(TIME_ELAPSED)
			except:
				print('Error displaying audio stream')

	def connectToServer(self):
		"""Connect to the Server. Start a new RTSP/TCP session."""
		self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		try:
			self.rtspSocket.connect((self.serverAddr, self.serverPort))
		except:
			tkMessageBox.showwarning('Connection Failed', 'Connection to \'%s\' failed.' %self.serverAddr)
	
	def sendRtspRequest(self, requestCode):
		"""Send RTSP request to the server."""
		
		# Setup request
		if requestCode == self.SETUP and self.state == self.INIT:
			threading.Thread(target=self.recvRtspReply).start()
			# Update RTSP sequence number.
			self.rtspSeq += 1
			
			# Write the RTSP request to be sent.
			request = 'SETUP ' + self.fileName + ' RTSP/1.0\nCSeq: ' + str(self.rtspSeq) + '\nTransport: RTP/UDP; client_port=' + str(self.rtpPort) + '-' + str(self.rtpPort + 1)
			
			# Keep track of the sent request.
			self.requestSent = self.SETUP 
		
		# Play request
		elif requestCode == self.PLAY and self.state == self.READY:
			self.rtspSeq += 1
			request = 'PLAY ' + self.fileName + ' RTSP/1.0\nCSeq: ' + str(self.rtspSeq) + '\nSession: ' + str(self.sessionId)
			self.requestSent = self.PLAY
		
		# Pause request
		elif requestCode == self.PAUSE and self.state == self.PLAYING:
			self.rtspSeq += 1
			request = 'PAUSE ' + self.fileName + ' RTSP/1.0\nCSeq: ' + str(self.rtspSeq) + '\nSession: ' + str(self.sessionId)
			self.requestSent = self.PAUSE
			
		# Teardown request
		elif requestCode == self.TEARDOWN and not self.state == self.INIT:
			self.rtspSeq += 1
			request = 'TEARDOWN ' + self.fileName + ' RTSP/1.0\nCSeq: ' + str(self.rtspSeq) + '\nSession: ' + str(self.sessionId) 
			self.requestSent = self.TEARDOWN
		else:
			return
		
		# Send the RTSP request using rtspSocket.
		self.rtspSocket.send(request.encode())
		
		print('\nData sent:\n' + request)
	
	def recvRtspReply(self):
		"""Receive RTSP reply from the server."""
		while True:
			reply = self.rtspSocket.recv(1024)
			
			if reply: 
				self.parseRtspReply(reply.decode("utf-8"))
			
			# Close the RTSP socket upon requesting Teardown
			if self.requestSent == self.TEARDOWN:
				self.rtspSocket.shutdown(socket.SHUT_RDWR)
				self.rtspSocket.close()
				break
	
	def parseRtspReply(self, data):
		"""Parse the RTSP reply from the server."""
		print('\nReceived: ', data)
		lines = str(data).split('\n')
		seqNum = int(lines[1].split(' ')[1])
		
		# Process only if the server reply's sequence number is the same as the request's
		if seqNum == self.rtspSeq:
			session = 0
			if self.requestSent in [self.SETUP, self.PLAY, self.PAUSE, self.TEARDOWN]:
				if self.requestSent in [self.SETUP, self.PLAY]:
					session = lines[3].split(' ')[1]
				else:
					session = lines[2].split(' ')[1]
				if session[-1] == ';':
					session = session[:-1]
				session = int(session)
			# New RTSP session ID
			if self.sessionId == 0:
				self.sessionId = session
			
			# Process only if the session ID is the same
			if self.sessionId == session:
				if int(lines[0].split(' ')[1]) == 200: 
					if self.requestSent == self.SETUP:
						# Update RTSP state.
						self.state = self.READY
						# Open RTP port.
						self.openRtpPort()
						self.playEvent = threading.Event()
						self.seph = threading.Semaphore(0)
						self.aseph = threading.Semaphore(0)
					elif self.requestSent == self.PLAY:
						self.state = self.PLAYING
					elif self.requestSent == self.PAUSE:
						self.state = self.READY
						self.playEvent.clear()
					elif self.requestSent == self.TEARDOWN:
						self.state = self.INIT
						# Flag the teardownAcked to close the socket.
						self.teardownAcked = 1

	def openRtpPort(self):
		"""Open RTP socket binded to a specified port."""
		# Create a new datagram socket to receive RTP packets from the server
		self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

		# Set the timeout value of the socket to 0.5sec
		self.rtpSocket.settimeout(0.5)
		
		try:
			# Bind the socket to the address using the RTP port given by the client user
			self.rtpSocket.bind(("", self.rtpPort))
			print('rtp port: ', self.rtpPort)
		except:
			tkMessageBox.showwarning('Unable to Bind', 'Unable to bind PORT=%d' %self.rtpPort)

	def handler(self):
		"""Handler on explicitly closing the GUI window."""
		self.pauseMovie()
		if tkMessageBox.askokcancel("Quit?", "Are you sure you want to quit?"):
			self.exitClient()
		else: # When the user presses cancel, resume playing.
			self.playMovie()

