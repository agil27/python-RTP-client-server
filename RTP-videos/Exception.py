class Error(Exception):
    pass

class ConError(Error):
    def __init__(self):
        pass
    def text(self):
        return '连接到服务器错误'

class SocketError(Error):
    def __init__(self):
        pass
    def text(self):
        return '套接字读取错误'

class BindError(Error):
    def __init__(self):
        pass
    def text(self):
        return '套接字绑定错误'