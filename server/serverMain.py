
class serverClass(object):
    def init(self):
        self.clientListLock = Lock()
        self.clientList = []

        self.sessionListLock = Lock()
        self.sessionList = []

    def getSessions(self):
        with self.sessionListLock:
            return self.sessionList

    def getSessNames(self):
        lst = list()
        for s in self.sessionList:
            lst.append(s.sessName)
        return lst

    def getUsedNicknames(self):
        s = set()
        for c in self.clientList:
            s.add(c.getNickname())
        return s

    def addSession(self,session):
        with self.sessionListLock:
            if session not in self.sessionList:
                self.sessionList.append(session)
                return True
            return False

    def addClient(self,client):
        with self.clientListLock:
            if client not in self.clientList:
                self.clientList.append(client)
                return True
            return False

    def listen(self,sock_addr):
        self.sock_addr = sock_addr
        #self.backlog = backlog
        self.s = socket(AF_INET, SOCK_STREAM)
        self.s.bind(self.sock_addr)
        self.s.listen(self.backlog)
        LOG.debug( 'Socket %s:%d is in listening state'\
                       '' % self.s.getsockname() )
    def loop(self):
        LOG.info( 'Falling to serving loop, press Ctrl+C to terminate ...' )
        clients = []

        try:
            while 1:
                client_socket = None
                LOG.info( 'Awaiting new clients ...' )
                client_socket,client_addr = self.s.accept()
                c = clientHandler(client_socket,self)                
                self.clientList.append(c)
                c.start()
        except KeyboardInterrupt:
            LOG.warn( 'Ctrl+C issued closing server ...' )
        finally:
            if client_socket != None:
                client_socket.close()
            self.s.close()
        map(lambda x: x.join(),clients)

if __name__ == '__main__':
    server = serverClass()
    server.listen(('127.0.0.1',7777))
    server.loop()
    LOG.info('Terminating ...')
