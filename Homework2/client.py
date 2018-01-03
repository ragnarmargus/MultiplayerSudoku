#!/usr/bin/env python
from Tkinter import *
from sys import exit
import tkSimpleDialog
from ScrolledText import ScrolledText
import pika
from uuid import uuid4
from threading import Thread, Event
import tkMessageBox
from dialog2 import MyDialog
from time import time, sleep

import logging
logging.basicConfig(level=logging.DEBUG,\
                    format='%(asctime)s (%(threadName)-2s) %(message)s',)
logging.getLogger("pika").setLevel(logging.WARNING)

# KeyRelease events seem to be device specific. for Samsung rf511 numpad it was necessary to bind these release events:
KB_map = {1: 'KP_End', 2: 'KP_Down', 3: 'KP_Next', 4: 'KP_Left',
          5: 'KP_Begin', 6: 'KP_Right', 7: 'KP_Home', 8: 'KP_Up', 9: 'KP_Prior'}


# This class handles server finding. It listens for server broadcast messages, which are sent every second.
# If no broadcast is heard from a server in 3 seconds, it is thought to be killed. Servers also send 'dead' messages
# when they die, so they can be removed from the GUI list.
# The information is shown in a graphical list. If a server is chosen, the class object will be killed and client will
# connect. If no server is chosen, client application will be killed
class ServerFinder:
    def __init__(self):
        # setup pika connection for listening broadcasts
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
        self.channel = self.connection.channel()
        result = self.channel.queue_declare(exclusive=True)
        self.queue_name = result.method.queue
        self.channel.queue_bind(exchange='online_servers', queue=self.queue_name, routing_key='server_names')
        self.channel.basic_qos(prefetch_count=10)
        self.channel.basic_consume(self.pika_callback, queue=self.queue_name)

        # setup TKinter
        self.master = Tk()
        self.master.title('Search')

        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.srv_frame = Frame(self.master)
        self.srv_list = Listbox(self.srv_frame, exportselection=0)
        self.srv_scroll = Scrollbar(self.srv_frame, orient="vertical")
        self.srv_label = Label(self.srv_frame, text='Available servers:')
        self.srv_label.pack(fill='y')
        self.srv_list.pack(side="left", fill="y")
        self.srv_scroll.pack(side="right", fill="y")
        self.srv_list.config(yscrollcommand=self.srv_scroll.set)
        self.srv_scroll.config(command=self.srv_list.yview)
        self.srv_list.bind("<<ListboxSelect>>", self.get_server)
        self.srv_frame.grid()

        self.server = None
        self.server_names = dict()

        # start looping
        self.is_closing = Event()
        self.install_find_server_callback()
        try:
            self.is_closing.clear()
            self.master.mainloop()
        except KeyboardInterrupt:
            self.server = None

    # consumes messages from pika exchange 'online_servers' with routing key 'server_names'
    # updates server_names dict with last heard times based on the message
    def pika_callback(self, ch, method, properties, body):
        try:
            name, last_update = body.split('#')
            self.server_names[name] = 0 if last_update == 'dead' else int(last_update)/10
        except:
            pass

    # Sets TK to periodically check for pika messages.
    # Avoids using threads (TK doesn't like being interacted with out of the main thread)
    def install_find_server_callback(self):
        def find_event():
            try:
                for i in range(100): self.connection.process_data_events()
                self.srv_list.delete(0, END)
                map(lambda x: self.srv_list.insert(END, x),
                    filter(lambda x: self.server_names[x] >= time() - 3, self.server_names))
                if not self.is_closing.is_set():
                    self.master.after(1000 // 100, find_event)
                else:
                    self.master.destroy()
                    self.connection.close()
            except:
                self.master.destroy()  # channel closed
        if not self.is_closing.is_set():
            self.master.after(1000 // 100, find_event)
        else:
            self.master.destroy()
            self.connection.close()

    # Returns self.server, which contains user chosen server name or None
    def return_server_name(self):
        return self.server

    # updates self.server based on mouse click. Initiates ServerFinder object closing
    def get_server(self, evt):
        # selecting session from session list calls this
        w = evt.widget
        if len(w.curselection()) != 0:
            self.server = self.srv_list.get(w.curselection()[0])
            self.on_closing()

    # Sets is_closing flag. This forbids install_find_server_callback to install new callbacks
    def on_closing(self):
        self.is_closing.set()


# Main GUI which allows creating and leaving from sessions,
# allows to play Sudoku, displays notifications and scores.
# Class functions are divided into:
#   1. server notification calls - allows the server to show available sessions, scores, notifications...
#   2. server interactions - based on client's interactions, interacts with the server (like insert a Sudoku number)
class ClientQUI:
    def __init__(self, master):
        self.master = master
        self.master.resizable(False, False)
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.master.title('Sudoku')
        self.current_session = None  ## used for warning, when changing sess, while in a session

        ## Create buttons for creating and leaving sessions
        self.create_session_button = Button(master, text="New game")
        self.create_session_button.bind("<Button-1>", self.create_session)
        self.leave_button = Button(master, text="Leave")
        self.leave_button.bind("<Button-1>", self.leave_session)

        ## Display notifications here
        self.notifybox = ScrolledText(master, state='disabled', height=5, width=43)

        ## Create sessions list
        self.session_frame = Frame(master)
        self.session_list = Listbox(self.session_frame, exportselection=0)
        self.session_scroll = Scrollbar(self.session_frame, orient="vertical")
        self.session_label = Label(self.session_frame, text='Available sessions:')
        self.session_label.pack(fill='y')
        self.session_list.pack(side="left", fill="y")
        self.session_scroll.pack(side="right", fill="y")
        self.session_list.config(yscrollcommand=self.session_scroll.set)
        self.session_scroll.config(command=self.session_list.yview)
        self.session_list.bind("<<ListboxSelect>>", self.set_active_session)

        ## Create Sudoku scoreboard and grid
        self.sudoku_and_score = Frame(master)
        ## Create sudoku grid
        self.sudoku = Frame(self.sudoku_and_score)
        self.s_tiles = [[None for i in range(9)] for j in range(9)]
        vcmd = (master.register(self.is_num), '%d', '%i', '%P', '%s', '%S', '%v', '%V', '%W')
        for x in range(9):
            for y in range(9):
                self.s_tiles[x][y] = Entry(self.sudoku, width=2, name=str(x)+str(y), state='disabled',
                                           justify=CENTER, validate='key', validatecommand=vcmd)
                for k in range(1, 10):
                    self.s_tiles[x][y].bind("<KeyRelease-%d>" % k, self.act_upon_sudoku_insert)
                    self.s_tiles[x][y].bind("<KeyRelease-KP_%d>" % k, self.act_upon_sudoku_insert)
                    self.s_tiles[x][y].bind("<KeyRelease-%s>" % KB_map[k], self.act_upon_sudoku_insert)
                self.s_tiles[x][y].grid(row=x, column=y, rowspan=1, columnspan=1, sticky=W + E + S + N)
        self.sudoku.grid(row=0, column=0)
        ## Create scoreboard
        self.score_frame = Frame(self.sudoku_and_score)
        self.score_label = Label(self.score_frame, text='Scores:')
        self.score_label.pack(fill='y')
        self.score_list = ScrolledText(self.score_frame, state='disabled', height=11, width=15)
        self.score_list.pack(fill='y')
        self.score_frame.grid(row=0, column=10)

        ## Place all into main window
        self.create_session_button.grid(row=0, column=0, rowspan=1, columnspan=1, sticky=W + E + S + N)
        self.leave_button.grid(         row=0, column=1, rowspan=1, columnspan=1, sticky=W + E + S + N)
        self.session_frame.grid(        row=1, column=0, rowspan=8, columnspan=2, sticky=W + E + S + N)
        self.notifybox.grid(            row=0, column=3, rowspan=3, columnspan=5, sticky=W + E + S + N)
        self.sudoku_and_score.grid(     row=4, column=3, rowspan=3, columnspan=5, sticky=W + E + S + N)

        # self.clients = []

    ## The following functions are called by server notifications ##
    # Inserts a text into notification list. Scrolls to the end of the list
    def insert_notification(self, msg):  # other GUI interactions may call this also
        self.notifybox.configure(state='normal')
        self.notifybox.insert(END, msg + '\n')
        self.notifybox.see(END)
        self.notifybox.configure(state='disabled')

    # Allows to insert and notify about a new game session
    def insert_new_session(self, sess_name):
        if sess_name not in self.session_list.get(0, END):
            self.session_list.insert(END, sess_name)
            self.insert_notification("New session '%s' available" % sess_name)

    # Removes a closing session. If client is in the session, sest current_session to None
    def remove_session(self, sess_name):
        # Server notification calls this
        if sess_name in self.session_list.get(0, END):
            self.session_list.delete(self.session_list.get(0, END).index(sess_name))
            self.insert_notification("Room '%s' closed" % sess_name)
        if self.current_session == sess_name:
            self.master.title('Sudoku')
            self.current_session = None
            self.disable_sudoku('Session has ended')

    # Shows session scores. Scores are cleared, when not in an active session
    def insert_scores(self, lst=""):
        if self.current_session is None:
            lst = ""
        self.score_list.configure(state='normal')
        self.score_list.delete('1.0', END)
        self.score_list.insert(END, '\n'.join(lst))
        self.score_list.configure(state='disabled')

    # Updates the Sudoku 9x9 grid
    def insert_sudoku_state(self, string):
        insertions = string.split(',')
        for i in range(len(insertions)):
            x, y = i // 9, i % 9
            value, how = insertions[i][0], insertions[i][1]
            self.insert_sudoku_cell(value, how, x, y)

    # Manipulates with a single Sudoku cell. Correct entries are set disabled,
    # so they cannot be changed
    def insert_sudoku_cell(self, value, how, x, y):
        self.s_tiles[x][y].config(state='normal')
        self.s_tiles[x][y].delete(0, END)
        if value != '0':
            self.s_tiles[x][y].insert(0, value)
        if how == 'f':
            self.s_tiles[x][y].config(state='disabled')

    # Called when client is in a room, which's game has ended
    def leave_finished_session(self):
        if self.current_session is None:
            return
        self.outcon.leave_room(self.current_session)
        self.current_session = None
        self.master.title('Sudoku')
        self.disable_sudoku()

    # Called when the server has stopped
    def close_ungracefully(self):
        self.master.withdraw()
        tkMessageBox.showerror('Terminating', 'Server shut down')
        logging.info('Window closing')
        self.master.destroy()

    # Called once when client joins the server. Updates currently available session list
    def add_all_rooms_clients(self, rooms, clients):
        self.clients = clients
        map(lambda x: self.session_list.insert(END, x), rooms)

    ## The following functions are bound to GUI events ##
    # Validates Sudoku grid entry. Checks if its a number
    def is_num(self, action, index, value_if_allowed, prior_value, text, validation_type, trigger_type, widget_name):
        # validating Sudoku entries, only allows numbers 1...9
        if action == '1':  # action=1 -> insert
            if prior_value == value_if_allowed[-1]:
                return False
            if len(prior_value) >= 2:  # allow 2 numbers in cell, older will be deleted
                return False
            if text in '123456789':  # allow only 1...9 in cell
                return True
            return False
        return True  # enable deleting

    # Called when numkey released.
    # Calls server to insert a number into Sudoku
    def act_upon_sudoku_insert(self, event):
        w = event.widget
        if len(w.get()) == 0:
            return
        value = w.get()[-1]
        w.delete(0, END)
        w.insert(0, value)
        x,y = list(str(w)[-2:])
        if self.s_tiles[int(x)][int(y)]['state'] == 'disabled':
            return
        com.send_move(self.current_session, str(w)[-2:][::-1]+str(value))

    # Called when 'Create' button is pressed.
    # If in a active room, ask client to leave it. Then asks server to create a room
    # and waits for a fail/success reply
    def create_session(self, evt):
        if not self.leave_session(None):
            return
        result = MyDialog(self.master).result
        if result is None:
            return
        sess_name, player_count = result[0], result[1]
        success = self.outcon.create_room(sess_name, player_count)
        if success:
            self.insert_notification("Created game '%s' for %d" % (sess_name, player_count))
            self.insert_new_session(sess_name)  # testing - delete it
            self.join_session(sess_name)
        else:
            self.insert_notification("Failed to create '%s' for %d" % (sess_name, player_count))

    # Called when 'Leave' button is pressed or when window closes or when changing session
    def leave_session(self, evt):
        if self.current_session is None:
            return True
        if not tkMessageBox.askyesno('Are you sure?', 'About to leave active session...'):
            return False
        self.outcon.leave_room(self.current_session)  # notifies server about leaving session
        self.insert_notification("Left room %s" %(self.current_session))
        self.current_session = None
        self.master.title('Sudoku')
        self.disable_sudoku('Join or create a Sudoku session')
        gui.insert_scores("  ")
        return True

    # Selecting session from session list calls this. Initiates joining a session
    def set_active_session(self, evt):
        w = evt.widget
        value = None
        if len(w.curselection()) != 0:
            value = self.session_list.get(w.curselection()[0])
        if value == self.current_session:
            return
        self.join_session(value)

    # Disables Sudoku grid, when it's not in use
    def disable_sudoku(self, notify_msg=''):
        if notify_msg != '':
            self.insert_notification(notify_msg)
        for i in range(81):
            self.s_tiles[i//9][i%9].config(state='disabled')

    # Asks the server to join a game
    def join_session(self, sess_name):
        if self.leave_session(None):
            self.disable_sudoku('Joining session...')
            self.outcon.join_room(sess_name)
            result, state = True, 'Waiting for players'
            if result:
                self.current_session = sess_name
                self.master.title('Playing in %s' % sess_name)
            else:
                self.master.title('Sudoku')
            self.disable_sudoku()

    # Called when client wanted to close the application.
    # Tells the server it's about to leave
    def on_closing(self, notify_server=True):
        if self.leave_session(None):
            self.master.destroy()
            logging.info('Window closing')
            self.outcon.stop(notify_server)

    ##Varia##
    # Return whether tk has been killed or not
    def is_running(self):
        try:
            self.master.state()
            return True
        except TclError:
            return False

    # gives GUI a handle for communicating with the server
    def register_con(self, outcon):
        self.outcon = outcon


# Sets up a thread which listens for server notifications.
# Listens on /*server_name*/direct_notify exchange, with routing key 'all_clients'.
# Additional keys are binded, when client connects to a session. (unbinded on leave)
# These server calls in turn call GUI functions
class Notifications(Thread):
    def __init__(self, gui, server_name):
        self.server_name = server_name
        self.gui = gui
        Thread.__init__(self)
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
        self.ch = self.connection.channel()
        self.setDaemon(daemonic=True)
        result = self.ch.queue_declare(exclusive=True)
        self.notification_queue = result.method.queue
        self.ch.queue_bind(exchange=self.server_name + 'direct_notify',
                           queue=self.notification_queue, routing_key='all_clients')
        self.ch.basic_qos(prefetch_count=10)
        self.ch.basic_consume(self.on_receive, no_ack=True, queue=self.notification_queue)
        self.loop = Event()  # used to kill the thread

    def run(self):
        self.loop.set()
        while self.loop.is_set():
            sleep(0.05)
            self.connection.process_data_events()
        self.connection.close()
        logging.debug('Notifications thread terminating...')

    def stop(self):
        self.loop.clear()

    def bind_queue(self, bind_to):
        self.ch.queue_bind(exchange=self.server_name + 'direct_notify',
                           queue=self.notification_queue, routing_key=bind_to)

    def unbind_queue(self, unbind):
        self.ch.queue_unbind(exchange=self.server_name + 'direct_notify',
                             queue=self.notification_queue, routing_key=unbind)

    def on_receive(self, ch, method, props, body):
        if not self.gui.is_running(): return
        logging.debug('NOTIFICATION: ' + body)
        # if body.startswith('receive_msg_from:'):
        #     _, who, room, msg = body.split(':')
        #     self.gui.insertchattext(room, who, msg)
        if body.startswith('receive_notification:'):  # misc notification message from the server
            self.gui.insert_notification("Server notification: " + body.split(':')[1])

        elif body.startswith('notify_new_client:'):  # a client joined the server
            self.gui.insert_notification("'%s' has joined server" % body.split(':')[1])

        elif body.startswith('notify_client_left:'):  # a client left the server
            self.gui.insert_notification("Client '%s' left server" % body.split(':')[1])

        elif body.startswith('notify_joined_room:'):  # a client joined the current Sudoku session
            _, name, room = body.split(':')
            self.gui.insert_notification("'%s' joined session '%s'" % (name, room))

        elif body.startswith('notify_left_room:'):  # a client left the current Sudoku session
            _, name, room = body.split(':')
            self.gui.insert_notification("'%s' left session '%s'" % (name, room))

        elif body.startswith('notify_new_room:'):  # a client has created a new room
            self.gui.insert_new_session(body.split(':')[1])
            self.gui.insert_notification("Room '%s' has been opened" % body.split(':')[1])

        elif body.startswith('notify_room_closed:'):  # room closes, when it's player count <= 1
            self.gui.remove_session(body.split(':')[1])

        elif body.startswith('notify_game_start:'):  # game starts, enough players joined
            self.gui.insert_notification("Game has Started")

        elif body.startswith('notify_game_state:'):  # updates Sudoku grid
            _, players, points, sudoku_board = body.split(':')
            #  check if game has ended and not still at splash screen (waiting other players)
            if ' ' not in sudoku_board and not (sudoku_board.count('0')==28 and sudoku_board.count('8')==53):
                self.gui.leave_finished_session()

            players = players.split(',')
            points = points.split(',')
            scores = []
            for i in range(len(players)):
                scores.append(players[i]+" "+points[i])

            self.gui.insert_scores(scores)
            self.gui.insert_sudoku_state(sudoku_board)

        elif body.startswith('notify_winner:'):  # session has ended, winner declared
            _, room, names = body.split(':')
            self.gui.insert_notification("Winner(s) in room %s: %s" % (room, names))
            self.gui.leave_finished_session()

        elif body.startswith('Stopping:'):  # server says it is shutting down
            self.stop()
            self.gui.close_ungracefully()
        else:
            logging.debug('Faulty request [%s]' % body)


# Client uses these RPC functions to communicate with server
# based on https://www.rabbitmq.com/tutorials/tutorial-six-python.html
# Setup of the RPC in pika & RabbitMQ:
#   1. server creates an exclusive /*server_name*/rpc_queue, which is bound to /*server_name*/direct_notify exchange
#   2. client creates it's own queue, where it receives the RPC replies
# When client does a RPC, the call includes a correlationID for reply identification
# and also where the it expects the response. Then it waits until it has received the response or gets a timeout error.
class Communication(object):
    def __init__(self, gui, server_name):
        self.server_name = server_name
        self.name = 'None'

        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
        self.ch = self.connection.channel()

        result = self.ch.queue_declare(exclusive=True)
        self.callback_queue = result.method.queue  # expect RPC replies here
        self.ch.queue_bind(exchange=self.server_name + 'direct_rpc', queue=self.callback_queue)
        self.ch.basic_qos(prefetch_count=10)
        self.ch.basic_consume(self.on_response, no_ack=True, queue=self.callback_queue)

        self.gui = gui
        self.receive_notifications = None
        gui.register_con(self)  # give GUI handler for calling communication functions

    # Stops the notification thread and tells the server, it has left
    def stop(self, notify_server=True):
        if self.receive_notifications is not None:
            self.receive_notifications.stop()
            self.receive_notifications.join()
        logging.debug('Requesting leave from server...')
        if notify_server:
            self.call('leave:' + self.name)
        logging.debug('Stopped communication...')

    # Checks for correct RPC response correlation ID.
    # If it matches, we have a response from the server
    def on_response(self, ch, method, props, body):
        if self.corr_id == props.correlation_id:
            self.response = body

    # Initiates a RPC call. Waits for the reply or gets timeout
    def call(self, body):
        self.response = None
        self.corr_id = str(uuid4())
        self.ch.basic_publish(exchange=self.server_name + 'direct_rpc', routing_key='rpc_queue',
                              properties=pika.BasicProperties(reply_to = self.callback_queue,
                                                              correlation_id = self.corr_id, ),
                              body=body)
        logging.debug('Waiting RPC response for [%s]... ' % body)
        tries = 5
        while self.response is None:
            self.connection.process_data_events(1)
            tries -= 1
            if tries == 0:
                logging.debug('Server reply timeout (5s)')
                self.gui.on_closing(notify_server=False)
                return 'False-err'
        logging.debug('RPC response: [%s]' % self.response)
        return self.response

    # Asks if the server accepts the name.
    # If server accepted, starts notification thread
    def request_name_ok(self, name):
        self.name = name
        logging.debug('Requesting name [%s]' % name)
        response = self.call('request_name:' + name)
        if response.startswith('False-err'):
            return None
        if response.startswith('False'):
            return False
        _, rooms, clients = response.split(':')
        clients = clients.split(',')
        rooms = [] if '' in rooms.split(',') else rooms.split(',')
        clients.remove(name)
        self.gui.add_all_rooms_clients(rooms, clients)
        self.gui.insert_notification('Successfully joined server with name %s' % name)
        # start receiving notifications
        self.receive_notifications = Notifications(self.gui, self.server_name)
        self.receive_notifications.bind_queue(name)
        self.receive_notifications.start()
        return True

    def leave_room(self, chat_name):  # Tell the server about leaving a room
        self.call('leave_room' + ':' + self.name + ':' + chat_name)
        self.receive_notifications.unbind_queue(chat_name)

    def join_room(self, chat_name):  # Tell the server about joining a room
        self.receive_notifications.bind_queue(chat_name)
        self.call('join_room' + ':' + self.name + ':' + chat_name)

    # Ask the server to create a room. The server checks if the room name is available
    def create_room(self, chat_name, room_size):
        body = 'create_room' + ':' + chat_name + ':' + str(room_size)
        return True if self.call(body) == 'True' else False

    # Ask the server to put a number to a Sudoku grid
    def send_move(self, sess_name, move):
        self.call('move' + ':' + sess_name + ':' + self.name + ':' + move)


# Start looking for servers
server_finder = ServerFinder()
server_name = server_finder.return_server_name()
if server_name is None:  # client didn't select a server
    exit()

# Start GUI
root = Tk()
root.withdraw()  # hide TK for name confirmation period
gui = ClientQUI(root)

try:
    com = Communication(gui, server_name)

    info_text = "Connecting..."
    while True:  # loop till we get an acceptable name
        MY_NAME = tkSimpleDialog.askstring(info_text, "Enter your name")
        if MY_NAME == '' or MY_NAME is None:  # don't start application, client specified no name or closed the app
            gui.on_closing(notify_server=False)
            break
        info_text = 'Name refused'
        if not all(c.isalnum() for c in MY_NAME) or len(MY_NAME) < 2:  # improper name
            continue
        result = com.request_name_ok(MY_NAME)
        if result is None:  # server timeout
            break
        if result == True:  # server agreed name
            root.deiconify()  # show TK again
            try:
                root.mainloop()
            except KeyboardInterrupt:
                logging.debug('CTRL-C pressed...')
                gui.on_closing()
            break
except pika.exceptions.ChannelClosed:
    logging.info('No server found...')

logging.info('Terminating application...')
