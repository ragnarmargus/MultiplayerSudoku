# This class handles the board states

from clientClass import *

class sessionClass(object):
    def __init__(self, sessName, maxClients):
        self.sessName = sessName
        self.clients = []
        self.tableCur = '' # TODO
        self.tableAns = '' # TODO
        self.maxClients = maxClients

    def getScoresNicknames(self):
        msgList = []
        for c in self.clients:
            msgList.append(c.getScoreNickname())
        return msgList

    def getTable(self):
        msg = ''
        #TODO: mgs += pos...
        return msg

    def getSessAvailable(self):
        return

    #def send
