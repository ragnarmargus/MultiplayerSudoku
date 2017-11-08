import logging
FORMAT='%(asctime)s (%(threadName)-2s) %(message)s'
logging.basicConfig(level=logging.DEBUG,format=FORMAT)
LOG = logging.getLogger()

from threading import Thread, Lock, currentThread
from clientIO import *

from socket import AF_INET, SOCK_STREAM, socket, SHUT_RD
from socket import error as soc_err

import os,sys,inspect
sys.path.insert(1, os.path.join(sys.path[0], '..'))
from messageProtocol import *

class Client():

    __gm_states = enum(
        NEED_NAME = 0,
        NOTCONNECTED = 1,
        NEED_NAME_VERIFICATION = 2,
        NEED_SESSION = 3,
        WAIT_FOR_PLAYERS = 4,
        NEED_PUTNUMBER = 5
    )

    __gm_ui_input_prompts = {
        __gm_states.NEED_NAME : 'Please input user name!',
        __gm_states.NEED_SESSION : 'Join or create new session!',
        __gm_states.WAIT_FOR_PLAYERS : 'Waiting for players!'
        __gm_states.NEED_PUTNUMBER : 'Enter x, y, number for Sudoku!'
    }

    def __init__(self,io):
        # Network related
        self.__send_lock = Lock()   # Only one entity can send out at a time

        # Here we collect the received responses and notify the waiting
        # entities
        self.__rcv_sync_msgs_lock = Condition()  # To wait/notify on received
        self.__rcv_sync_msgs = [] # To collect the received responses
        self.__rcv_async_msgs_lock = Condition()
        self.__rcv_async_msgs = [] # To collect the received notifications

        self.__io = io  # User interface IO

        # Current state of the game client
        self.__gm_state_lock = Lock()
        self.__gm_state = self.__gm_states.NEED_NAME
        self.__my_name = None
        self.__client_sudoku_copy = ''

    def __state_change(self,newstate):
        '''Set the new state of the game'''
        with self.__gm_state_lock:
            self.__gm_state = newstate
            logging.debug('Games state changed to [%d]' % newstate)
            self.__io.output_sync(self.__gm_ui_input_prompts[newstate])

    def set_my_name(self,name):
        '''Setup player name before we can join the game'''
        payload = serialize(name)
        logging.debug(\
            'Requesting the server to set player\'s name to %s ...' % name)
        rsp = self.__sync_request(REQ_GM_SET_NAME, payload)
        if rsp != None:
            head,payload = rsp
            if head == RSP_GM_SET_NAME:
                if payload[0] == '1':
                    logging.debug('Server confirmed player\'s name')
                    self.__my_name = name
                    self.__io.output_sync('Joined the game!')
                    return True
                else:
                    logging.debug('Server rejected player\'s name')
                    self.__io.output_sync('Select different name!')
                    return False
            else:
                logging.warn('Protocol error, unexpected control code!')
                logging.warn(\
                    'Expected [%s] received [%s]' % (RSP_GM_SET_NAME,head))


##    def set_new_word_to_guess(self,word):
##        '''Propose the new word to guess'''
##        payload = serialize(word)
##        logging.debug(\
##            'Requesting the server to the new word to guess: %s ...' % word)
##        rsp = self.__sync_request(REQ_GM_SET_WORD, payload)
##        if rsp != None:
##            head,payload = rsp
##            if head == RSP_GM_SET_WORD:
##                if payload[0] == '1':
##                    logging.debug('Server confirmed new word: %s' % word)
##                    self.__io.output_sync('Let others guess: [%s]' % word)
##                    return True
##                else:
##                    logging.debug('Server rejected player\'s word %' % word)
##                    logging.debug('Someone was faster in setting word!')
##                    return False
##            else:
##                logging.warn('Protocol error, unexpected control code!')
##                logging.warn(\
##                    'Expected [%s] received [%s]' % (RSP_GM_SET_WORD,head))

##    def guess_letter(self,l):
##        '''Guess the letter'''
##        l = l[0]
##        if l in self.__tried_letters:
##            self.__io.output_sync(\
##                'Letter %s already tried and is wrong, try another one!' % l)
##            return False
##        if l in self.__current_progress:
##            self.__io.output_sync(\
##                'Letter %s already guessed, try another one!' % l)
##            return False
##        logging.debug(\
##            'Requesting the server to guess letter: [%s] ...' % l)
##        rsp = self.__sync_request(REQ_GM_GUESS, l)
##        if rsp != None:
##            head,payload = rsp
##            if head == RSP_GM_GUESS:
##                if payload[0] == '1':
##                    logging.debug('Server confirmed letter: %s' % l)
##                    return True
##                else:
##                    logging.debug('Server rejected letter %s' % l)
##                    self.__io.output_sync('Wrong letter %s' % l)
##                    self.__tried_letters += l
##                    self.get_current_progress()
##                    return False
##            else:
##                logging.warn('Protocol error, unexpected control code!')
##                logging.warn(\
##                    'Expected [%s] received [%s]' % (RSP_GM_GUESS,head))

##    def get_current_progress(self):
##        '''Get current progress of word guessing'''
##        logging.debug(\
##            'Requesting the current state ...')
##        rsp = self.__sync_request(REQ_GM_GET_STATE)
##        if rsp != None:
##            head,payload = rsp
##            if head == RSP_GM_STATE:
##                uncovered_word = deserialize(payload)
##                self.__current_progress = uncovered_word
##                if len(uncovered_word) > 0:
##                    logging.debug('Current uncovered word [%s] received'\
##                              '' % uncovered_word)
##                    self.__io.output_sync('Current progress: [%s]' %
##                                            uncovered_word)
##                    self.__io.output_sync('You tried letters: [%s]' %
##                                          self.__tried_letters)
##                    self.__state_change(self.__gm_states.NEED_LETTER)
##                else:
##                    if self.__gm_state != self.__gm_states.NEED_WORD:
##                        self.__state_change(self.__gm_states.NEED_WORD)
##                        self.__tried_letters = ''
##            else:
##                logging.warn('Protocol error, unexpected control code!')
##                logging.warn(\
##                    'Expected [%s] received [%s]' % (RSP_GM_STATE,head))

    def stop(self):
        '''Stop the game client'''
        try:
            self.__s.shutdown(SHUT_RD)
        except soc_err:
            logging.warn('Was not connected anyway ..')
        finally:
            self.__s.close()
        self.__sync_response('DIE!')
        self.__async_notification('DIE!')

    def connect(self,srv_addr):
        '''Connect to server, start game session'''
        self.__s = socket(AF_INET,SOCK_STREAM)
        try:
            self.__s.connect(srv_addr)
            logging.info('Connected to Game server at %s:%d' % srv_addr)
            self.__state_change(self.__gm_states.NEED_NAME)
            return True
        except soc_err as e:
            logging.error('Can not connect to Game server at %s:%d'\
                      ' %s ' % (srv_addr+(str(e),)))
            self.__io.output_sync('Can\'t connect to server!')
        return False

    def __sync_request(self,header,payload=''):
        '''Send request and wait for response'''
        with self.__send_lock:
            req = header + MSG_FIELD_SEP + payload
            if self.__session_send(req):
                with self.__rcv_sync_msgs_lock:
                    while len(self.__rcv_sync_msgs) <= 0:
                        self.__rcv_sync_msgs_lock.wait()
                    rsp = self.__rcv_sync_msgs.pop()
                if rsp != 'DIE!':
                    return rsp.split(MSG_FIELD_SEP)
            return None

    def __sync_response(self,rsp):
        '''Collect the received response, notify waiting threads'''
        with self.__rcv_sync_msgs_lock:
            was_empty = len(self.__rcv_sync_msgs) <= 0
            self.__rcv_sync_msgs.append(rsp)
            if was_empty:
                self.__rcv_sync_msgs_lock.notifyAll()

    def __async_notification(self,msg):
        '''Collect the received server notifications, notify waiting threads'''
        with self.__rcv_async_msgs_lock:
            was_empty = len(self.__rcv_async_msgs) <= 0
            self.__rcv_async_msgs.append(msg)
            if was_empty:
                self.__rcv_async_msgs_lock.notifyAll()

    def __session_rcv(self):
        '''Receive the block of data till next block separator'''
        m,b = '',''
        try:
            b = self.__s.recv(DEFAULT_RCV_BUFSIZE)
            m += b
            while len(b) > 0 and not (b.endswith(MSG_SEP)):
                b = self.__s.recv(DEFAULT_RCV_BUFSIZE)
                m += b
            if len(b) <= 0:
                logging.debug( 'Socket receive interrupted'  )
                self.__s.close()
                m = ''
            m = m[:-1]
        except KeyboardInterrupt:
            self.__s.close()
            logging.info( 'Ctrl+C issued, terminating ...' )
            m = ''
        except soc_err as e:
            if e.errno == 107:
                logging.warn( 'Server closed connection, terminating ...' )
            else:
                logging.error( 'Connection error: %s' % str(e) )
            self.__s.close()
            logging.info( 'Disconnected' )
            m = ''
        return m

    def __session_send(self,msg):
        '''Just wrap the data, append the block separator and send out'''
        m = msg + MSG_SEP

        r = False
        try:
            self.__s.sendall(m)
            r = True
        except KeyboardInterrupt:
            self.__s.close()
            logging.info( 'Ctrl+C issued, terminating ...' )
        except soc_err as e:
            if e.errno == 107:
                logging.warn( 'Server closed connection, terminating ...' )
            else:
                logging.error( 'Connection error: %s' % str(e) )
            self.__s.close()
            logging.info( 'Disconnected' )
        return r

    def __protocol_rcv(self,message):
        '''Processe received message:
        server notifications and request/responses separately'''
        logging.debug('Received [%d bytes] in total' % len(message))
        if len(message) < 2:
            logging.debug('Not enough data received from %s ' % message)
            return
        logging.debug('Response control code [%s]' % message[0])
        if message.startswith(RSP_GM_NOTIFY + MSG_FIELD_SEP):
            payload = message[2:]
            notification = deserialize(payload)
            logging.debug('Server notification received: %s' % notification)
            self.__async_notification(notification)
        elif message[:2] in map(lambda x: x+MSG_FIELD_SEP,  [RSP_GM_GUESS,
                                                             RSP_GM_SET_WORD,
                                                             RSP_GM_SET_NAME,
                                                             RSP_GM_STATE]):
            self.__sync_response(message)
        else:
            logging.debug('Unknown control message received: %s ' % message)
            return RSP_UNKNCONTROL

    def __get_user_input(self):
        '''Gather user input'''
        try:
            msg = self.__io.input_sync()
            logging.debug('User entered: %s' % msg)
            return msg
        except InputClosedException:
            return None

    def game_loop(self):
        '''Main game loop (assuming network-loop and notifications-loop are
        running already'''
        
        self.__io.output_sync('Press Enter to initiate input, ')
        self.__io.output_sync(\
            'Type in your message (or Q to quit), hit Enter to submit')
        while 1:
            user_input = self.__get_user_input()
            if user_input == 'Q':
                break
            if self.__gm_state == self.__gm_states.NEED_NAME:
                self.set_my_name(user_input)
            elif self.__gm_state == self.__gm_states.NEED_WORD:
                self.set_new_word_to_guess(user_input)
            elif self.__gm_state == self.__gm_states.NEED_LETTER:
                self.guess_letter(user_input)
        self.__io.output_sync('Q entered, disconnecting ...')

    def notifications_loop(self):
        '''Iterate over received notifications, show them to user, wait if
        no notifications'''

        logging.info('Falling to notifier loop ...')
        while 1:
            with self.__rcv_async_msgs_lock:
                if len(self.__rcv_async_msgs) <= 0:
                    self.__rcv_async_msgs_lock.wait()
                msg = self.__rcv_async_msgs.pop(0)
                if msg == 'DIE!':
                    return
            self.__io.output_sync('Server Notification: %s' % msg)
            self.get_current_progress()

    def network_loop(self):
        '''Network Receiver/Message Processor loop'''
        logging.info('Falling to receiver loop ...')
        while 1:
            m = self.__session_rcv()
            print m
            if len(m) <= 0:
                break
            self.__protocol_rcv(m)

if __name__ == '__main__':
    srv_addr = ('127.0.0.1',7777)

    print 'Application start ...'

    sync_io = SyncConsoleAppenderRawInputReader()
    client = Client(sync_io)
    if client.connect(srv_addr):

        network_thread = Thread(name='NetworkThread',target=client.network_loop)
        notifications_thread =\
             Thread(name='NotificationsThread',target=client.notifications_loop)
        network_thread.start()
        notifications_thread.start()

        try:
            client.game_loop()
        except KeyboardInterrupt:
            logging.warn('Ctrl+C issued, terminating ...')
        finally:
            client.stop()

        network_thread.join()
        notifications_thread.join()

    logging.info('Terminating')
