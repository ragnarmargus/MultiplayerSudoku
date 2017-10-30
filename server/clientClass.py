from sessionClass import *

class clientClass(object):
    def __init__(self, socket, nickname, session):
        self.socket = socket # tuple (IP, port)
        self.score = 0
        self.nickname = nickname
        self.session = session
        
    def getScoreNickname(self):
        return self.nickname+FIELD_SEP+str(self.score)
    
    def incScore(self)
        self.score += 1
        return self.score
    
    def decScore(self):
        self.score -= 1
        return self.score
    
    def sendScores(self):
        msg = REP_CURRENT_PLAYERS+HEADER_SEP+\
              str(self.session.getScoresNicknames())+MSG_TERMCHR
        self.socket.send(msg)
        
    def sendTable(self, moveInfo):
        msg = moveInfo+HEADER_SEP+self.session.getTable()
        self.socket.send(msg)
        
    def sendError(self, errorMsg='None'):
        msg = REP_NOT_OK+HEADER_SEP+errorMsg+MSG_TERMCHR
        self.socket.send(msg)

    def requestPutNumber(self):
        ans = self.session.getNumberOk(xyz)
        if ans == REP_TABLE_SUCCESS:
            self.incScore()
        elif ans == REP_TABLE_FULL:
            pass
        elif ans == REP_TABLE_WRONG:
            self.decScore()
        elif ans == REP_GAME_OVER:
            #TODO: game over
            pass
        self.sendTable(ans)
        

    # TODO: RECV from client
            

    def closeSocket(self):
        #TODO: shutdown and how stuff
        self.socket.close()
