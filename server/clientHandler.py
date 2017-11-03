from sessionClass import *
#TODO: imports

class clientHandler(Thread):
    def __init__(self, socket, Server):
        self.socket = socket # tuple (IP, port)
        self.score = 0
        self.nickname = None
        self.session = None
        self.exists = True
        self.Server = Server
        #self.__send_lock = Lock()

    def getNickname(self):
        return self.nickname
        
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
        

    def rcvMessage(self):
        m,b = '',''
        try:
            b = self.socket.recv(1)
            m += b
            while len(b) > 0 and not (b.endswith(MSG_TERMCHR)):
                b = self.socket.recv(1)
                m += b
            if len(b) <= 0:
                self.socket.close()
                LOG.info( 'Client %s:%d disconnected' % self.socket.getsocketname() )
                m = ''
            m = m[:-1]
        except KeyboardInterrupt:
            self.socket.close()
            LOG.info( 'Ctrl+C issued, disconnecting client %s:%d' % self.socket.getsocketname() )
            m = ''
        except soc_err as e:
            if e.errno == 107:
                LOG.warn( 'Client %s:%d left before server could handle it'\
                '' %  self.socket.getsocketname() )
            else:
                LOG.error( 'Error: %s' % str(e) )
            self.socket.close()
            LOG.info( 'Client %s:%d disconnected' % self.socket.getsocketname() )
            m = ''
        return m

    def joinSession(self, sessName):
        for sess in self.Server.sessionList:
            if sessName == sess.sessName:
                if sess.addMe(self):
                    self.session = sess
                    return "OK"
                return "session full"
        return "No such session"
    
    def createSession(self, sessName, maxPlayerCount):
        if sessName in self.Server.getSessNames():
            return "Session name in use"
        sess = sessionClass(sessName, maxPlayerCount)
        self.Server.sessionList.append(sess)
        self.session = sess
        if sess.addMe(self):
            self.session = sess
            return "OK"
        return "session full"
    
    def rcvProtocolMessage(self,message):
        REP, MSG = 'OK', ''
        
        LOG.debug('Received request [%d bytes] in total' % len(message))
        if len(message) < 2:
            LOG.degug('Not enough data received from %s ' % message)
            return REP_NOT_OK
        payload = message[2:]
        
        if message.startswith(REQ_NICKNAME + HEADER_SEP):
            if payload not in self.Server.getUsedNicknames():
                self.nickName = payload
                LOG.debug('Client %s:%d will use name '\
                    '%s' % (self.socket.getsocketname()+(self.nickName,)))
                REP = REP_CURRENT_SESSIONS,\
                MSG = str(map(lambda x: x.getSessInfo(), self.Server.getSessions())
            else:
                REP, MSG = REP_NOT_OK, "Name in use"
            
        elif message.startswith(REQ_JOIN_EXIST_SESS + HEADER_SEP):
            msg = self.joinSession(payload)
            if msg == "OK":
                LOG.debug('Client %s:%d joined session '\
                    '%s' % (self.socket.getsocketname()+(payload,)))
                REP, MSG = REP_NOT_OK, msg # TODO: what to return? only field or field with scores?
                
            else:
                LOG.debug('Client %s:%d failed to join session: '\
                    '%s' % (self.socket.getsocketname()+(msg,)))
                REP, MSG = REP_NOT_OK, msg
            
        elif message.startswith(REQ_JOIN_NEW_SESS + HEADER_SEP):
            sessname, playercount = payload.split(FIELD_SEP)
            try:
                playercount = int(playercount)
                msg = self.createSession(sessname, playercount)
                if msg == "OK":  
                    LOG.debug('Client %s:%d created session '\
                        '%s' % (self.socket.getsocketname()+(payload,)))
                else:
                    LOG.debug('Client %s:%d failed to create and join session: '\
                    '%s' % (self.socket.getsocketname()+(msg,)))
                    REP, MSG = REP_NOT_OK, msg # TODO: what to return? only field?
                    
            except ValueError:
                REP, MSG = REP_NOT_OK, "Unable to parse integer"           
            
        elif message.startswith(REQ_PUT_NR + HEADER_SEP):
            LOG.debug('Client %s:%d wants to write to sudoku: %s'\
                '' % (self.socket.getsocketname()+(payload,)))
            try:
                ints = list(payload)
                number, x, y = int(inst[0]),int(inst[1]),int(inst[2])
                if number in range(1,10) and x in range(1,10) and y in range(1,10):
                    REP, MSG = self.session.putNumber(number, x, y)# TODO: Returns field and scores
                else:
                    REP, MSG = REP_NOT_OK, "Number not in 1...9"                     
            except ValueError:
                REP, MSG = REP_NOT_OK, "Unable to parse integer" 
            
        else:
            LOG.debug('Unknown control message received: %s ' % message)
            REP, MSG = REP_NOT_OK, "Unknown control message"  
            
        return REP, MSG

    def __session_send(self,msg): #TODO: not incorporated
        m = msg + MSG_SEP
        with self.__send_lock:
            r = False
            try:
                self.__s.sendall(m)
                r = True
            except KeyboardInterrupt:
                self.__s.close()
                LOG.info( 'Ctrl+C issued, disconnecting client %s:%d'\
                          '' % self.__addr )
            except soc_err as e:
                if e.errno == 107:
                    LOG.warn( 'Client %s:%d left before server could handle it'\
                    '' %  self.__addr )
                else:
                    LOG.error( 'Error: %s' % str(e) )
                self.__s.close()
                LOG.info( 'Client %s:%d disconnected' % self.__addr )
            return r

    def run(self): #TODO: not incorporated
        while 1:
            m = self.__session_rcv()
            if len(m) <= 0:
                break
            rsp = self.__protocol_rcv(m)
            if rsp == RSP_BADFORMAT:
                break
            if not self.__session_send(rsp):
                break
        self.exists = False
        self.session.removeMe()

    def closeSocket(self):
        #TODO: shutdown and how stuff
        self.socket.close()
