# This class handles the board states

from clientClass import *

class sessionClass(object):
    def __init__(self, sessName, maxClients):
        self.sessName = sessName
        self.clients = []
        self.tableCur = '' # TODO
        self.tableAns = '' # TODO
        self.maxClients = maxClients

        self.tableLock = Condition() # mb can use Lock
        self.clientsLock = Lock()

    def getSessInfo(self):
        return self.sessName+'-'\
               +str(len(self.clients))+'/'+\
               +str(self.maxCLients)

    def addMe(self, c):
        with self.clientsLock:
            self.clients.append(c)
            if len(clients) < maxClients:            
                self.clients.append(c)
                return True
            return False

    def removeMe(self):
        caller = currentThread()
        if caller in self.clients:
            self.clients.remove(caller)
            logging.info('%s left game' % caller.getNickname())

    def getScoresNicknames(self):
        msgList = []
        for c in self.clients:
            msgList.append(c.getScoreNickname())
        return msgList

    def getTable(self):
        msg = ''
        #TODO: mgs += pos...
        return msg

    def putNumber(number, x, y):
        with self.tableLock:
            # if position occupied
            rep = REP_TABLE_FULL
            # if wrong
            rep = REP_TABLE_WRONG
            # if correct
            rep = REP_TABLE_SUCCESS
            # if correct and game over
            rep = REP_GAME_OVER
            return rep, self.getTable()
