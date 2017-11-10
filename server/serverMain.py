import logging
FORMAT='%(asctime)s (%(threadName)-2s) %(message)s'
logging.basicConfig(level=logging.DEBUG,format=FORMAT)
LOG = logging.getLogger()

import os,sys,inspect
sys.path.insert(1, os.path.join(sys.path[0], '..'))
from messageProtocol import *
from sessionClass import *
from clientHandler import *
from threading import Thread, Lock, currentThread

from socket import AF_INET, SOCK_STREAM, socket
from socket import error as soc_err

class serverClass(object):
    def __init__(self):
        self.lobbyList = []
        self.lobbyListLock = Lock()
        
        self.clientListLock = Lock()
        self.clientList = []

        self.sessionListLock = Lock()
        self.sessionList = []

    def lobbyThread(self):
        with self.sessionListLock:
            self.sessionList = filter(lambda x: len(x.clients)!=0, self.sessionList)
            map(lambda x: x.send_notification(msg), joined)

    def removeMe(self):
        caller = currentThread()
        if caller.session != None:
            caller.session.removeMe()
        if caller in self.clientList:
            self.clientList.remove(caller)
            logging.info('%s left game' % caller.getNickname())
        if caller in self.lobbyList:
            self.lobbyList.remove(caller)
            logging.info('%s left lobby' % caller.getNickname())

    def removeFromLobby(self,c):
        with self.lobbyListLock:
            if c in self.lobbyList:
                self.lobbyList.remove(c)

    def addToLobby(self,c_list):
        for c in c_list:
            c.session=None
            c.send_notification('Available Sessions: %s'
                        %''.join(map(lambda x: '\n  ' +
                        x.getSessInfo(),self.getSessions())))
        with self.lobbyListLock:
            self.lobbyList += c_list

    def getSessions(self):
        with self.sessionListLock:
            return self.sessionList

    def getSessNames(self):
        lst = list()
        for s in self.sessionList:
            lst.append(s.sessName)
        return lst

    def getUsedNicknames(self):
        return map(lambda x: x.nickname, self.clientList)

    def addSession(self,session):
        with self.sessionListLock:
            if session not in self.sessionList:
                self.sessionList.append(session)
                return True
            return False
         
    def removeSession(self,sess):
        with self.sessionListLock:
            if sess in self.sessionList:
                self.sessionList.remove(sess)

    def addClient(self,client):
        with self.clientListLock:
            if client not in self.clientList:
                self.clientList.append(client)
                return True
            return False

    def listen(self,sock_addr):
        self.sock_addr = sock_addr
        self.s = socket(AF_INET, SOCK_STREAM)
        self.s.bind(self.sock_addr)
        self.s.listen(1)
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
                c = clientHandler(client_socket, self)
                self.clientList.append(c)
                self.addToLobby([c])
                c.start()
        except KeyboardInterrupt:
            LOG.warn( 'Ctrl+C issued closing server ...' )
        finally:
            if client_socket != None:
                client_socket.close()
            self.s.close()
        map(lambda x: x.join(), clients)

if __name__ == '__main__':
    server = serverClass()
    server.listen(('127.0.0.1',7777))
    server.loop()
    LOG.info('Terminating ...')
