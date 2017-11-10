import logging
FORMAT='%(asctime)s (%(threadName)-2s) %(message)s'
logging.basicConfig(level=logging.DEBUG,format=FORMAT)
LOG = logging.getLogger()

import os,sys,inspect
sys.path.insert(1, os.path.join(sys.path[0], '..'))
from messageProtocol import *
from clientHandler import *
from serverMain import *
from threading import Thread, Lock, currentThread


class sessionClass():
    def __init__(self, sessName, maxClients, Server):
        self.Server = Server
        self.sessName = sessName
        self.clients = []
        self.tableCur = ''.join(map(lambda x: str(x), range(1,10)))*9
        self.tableAns = '' # TODO
        self.maxClients = maxClients
        self.gameRunning = False

        self.tableLock = Lock()
        self.clientsLock = Lock()

    def notify_update(self,msg):
        joined = filter(lambda x: x.session!=None, self.clients)
        map(lambda x: x.send_notification(msg), joined)

    def send_specific_update(self,header,msg):
        joined = filter(lambda x: x.session!=None, self.clients)
        print joined
        map(lambda x: x.send_specific(header,msg), joined)

    def getSessInfo(self):
        return self.sessName+'-'\
               +str(len(self.clients))+'/'\
               +str(self.maxClients)

    def addMe(self, c):
        with self.clientsLock:
            if len(self.clients) < self.maxClients:            
                self.clients.append(c)
                c.session = self
                self.notify_update(c.nickname+' joined game \n Player numbers %d/%d'\
                        %(len(self.clients),self.maxClients))
                self.Server.removeFromLobby(c)
                if len(self.clients) == self.maxClients:
                    self.gameRunning = True
                    self.send_specific_update(REP_TABLE,self.tableCur)
                return True
            return False

    def removeMe(self):
        caller = currentThread()
        caller.session = None
        if caller in self.clients:
            self.clients.remove(caller)
            self.notify_update(caller.nickname+' joined game')
            logging.info('%s left game' % caller.getNickname())

        if (len(self.clients)<2 and self.gameRunning) or len(self.clients)==0:
            self.send_specific_update(REP_SCORES_GAME_OVER,\
				'Winner: %s' %self.findHighScore())
	    #if self in self.Server.getSessions():
            #    sessList = (self.Server.getSessions()).remove(self)
            #MSG = str(map(lambda x: x.getSessInfo(), self.Server.sessionList))
            self.Server.removeSession(self)
            self.Server.addToLobby(self.clients)
            self.clients = []
            #self.Server.removeSession(self)
            logging.info('Session %s closing - too few players' %self.sessName)
            

    def getScoresNicknames(self):
        msg = ", ".join(map(lambda x: x.getScoreNickname(), self.clients))
        return msg

    def findHighScore(self):
        best = None
        score = -99999        
        for c in self.clients:
            if c.score > score:
                best = c.nickname
                score = c.score
        return str(best)+'-'+str(score)+'points'

    def putNumber(self, number, x, y, client):                
        with self.tableLock:
            if False: # if position occupied
                msg = 'Cell full'
            elif False: # if wrong
                msg = 'Wrong'
                client.decScore()
            elif True:  # if correct
                msg = 'Correct'
                client.incScore()
                self.notify_update('Scores: '+self.getScoresNicknames())
                self.send_specific_update(REP_TABLE,self.tableCur)
                if True: # game over
                    self.send_specific_update(REP_SCORES_GAME_OVER,\
				'Winner: %s' %self.findHighScore())
                    #self.notify_update('Available Sessions: %s' \
                    #    %''.join(map(lambda x: '\n  '+\
		    #x.getSessInfo(),self.Server.getSessions())))
                    #sessList = (self.Server.getSessions()).remove(self)
                    #MSG = str(map(lambda x: x.getSessInfo(), sessList))

		    self.Server.removeSession(self)
                    self.Server.addToLobby(self.clients)
                    self.clients = []
            return REP_PUT_NR, msg
