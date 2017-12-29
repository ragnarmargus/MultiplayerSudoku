#!/usr/bin/env python
from Tkinter import *
import tkMessageBox
import logging
import tkSimpleDialog
from ScrolledText import ScrolledText
import pika
from uuid import uuid4
from threading import Thread, Event
import tkMessageBox
from dialog2 import MyDialog

import logging
logging.basicConfig(level=logging.DEBUG,\
                    format='%(asctime)s (%(threadName)-2s) %(message)s',)
logging.getLogger("pika").setLevel(logging.WARNING)

# Somewhy KeyRelease event doesn't recognise keys with KP_number events
KB_map = {1: 'KP_End', 2: 'KP_Down', 3: 'KP_Next', 4: 'KP_Left',
          5: 'KP_Begin', 6: 'KP_Right', 7: 'KP_Home', 8: 'KP_Up', 9: 'KP_Prior'}





class ClientQUI:
    def __init__(self, master):
        self.master = master
        self.master.resizable(False, False)
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.master.title('Sudoku')
        self.current_session = None  ## maybe use for warning, when changing sess, while in a session

        ## Create buttons for creating and leaving sessions
        self.create_session_button = Button(master, text="New game")
        self.create_session_button.bind("<Button-1>", self.create_session)
        self.leave_button = Button(master, text="Leave")
        self.leave_button.bind("<Button-1>", self.leave_session)

        ## Display notifications here
        self.notifybox = ScrolledText(master, state='disabled', height=3, width=43)

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

        self.insert_scores(['Mina 1p', 'Sina 2p'])  ## delete it
        self.clients = []

    ## Server notification calls:
    def insert_notification(self, msg):
        # Server notification or GUI calls this
        self.notifybox.configure(state='normal')
        self.notifybox.insert(END, msg + '\n')
        self.notifybox.see(END)
        self.notifybox.configure(state='disabled')

    def insert_new_session(self, sess_name):
        # Server notification calls this
        if sess_name not in self.session_list.get(0, END):
            self.session_list.insert(END, sess_name)
            self.insert_notification("New session '%s' available" % sess_name)

    def remove_session(self, sess_name):
        # Server notification calls this
        if sess_name in self.session_list.get(0, END):
            self.session_list.delete(self.session_list.get(0, END).index(sess_name))
            self.insert_notification("Session '%s' closed" % sess_name)
        if self.current_session == sess_name:
            self.master.title('Sudoku')
            self.current_session = None
            self.disable_sudoku('Game ended with scores: %s' % self.score_list.get('1.0', END))  ## maybe find max score....

    def insert_scores(self, lst):
        # Server notification calls this
        self.score_list.configure(state='normal')
        self.score_list.delete('1.0', END)
        self.score_list.insert(END, '\n'.join(lst))
        self.score_list.configure(state='disabled')

    def insert_sudoku_start(self, string):
        # server notification should call it, game starts
        insertions = string.split(',')
        for i in range(len(insertions)):  # if len == 81 ?????
            x, y = i // 9, i % 9
            value, how = insertions[i][0], insertions[i][1]
            self.insert_sudoku_cell(value, how, x, y)
        self.insert_notification('Start!')

    def insert_sudoku_cell(self, value, how, x, y):
        # Manipulating single Sudoku cell
        self.s_tiles[x][y].config(state='normal')
        self.s_tiles[x][y].delete(0, END)
        if value != '0':
            self.s_tiles[x][y].insert(0, value)
        if how == 'f':
            self.s_tiles[x][y].config(state='disabled')

    ## Bound to GUI events:
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
        return True  # disable deleting

    def act_upon_sudoku_insert(self, event):
        # acting upon correct Sudoku entry number_keyRelease event
        w = event.widget
        if len(w.get()) == 0:
            return
        value = w.get()[-1]
        w.delete(0, END)
        w.insert(0, value)
        print 'Inserted %s into %s' % (value, str(w)[-2:])
        # fn call to server...

    def create_session(self, evt):
        # Called when 'Create' button is pressed
        result = MyDialog(self.master).result
        if result is None:
            return
        sess_name, player_count = result[0], result[1]
        # success = call server for session creation
        success = self.outcon.create_room(sess_name, player_count)
        #success = 'succeeded' if  else 'failed'

        if success:
            self.insert_notification("Created game '%s' for %d" % (sess_name, player_count))
            self.insert_new_session(sess_name)  # testing - delete it
            self.join_session(sess_name)
        else:
            self.insert_notification("Failed to create '%s' for %d" % (sess_name, player_count))

    def leave_session(self, evt):
        # Called when 'Leave' button is pressed or when window closes or when changing session
        if self.current_session is None:
            return True
        if not tkMessageBox.askyesno('Are you sure?', 'About to leave active session...'):
            return False
        # ask server to leave session
        self.outcon.leave_room(self.current_session)
        self.insert_notification("Left room %s" %(self.current_session))
        self.current_session = None
        self.master.title('Sudoku')
        self.disable_sudoku('Join or create a Sudoku session')
        return True

    def set_active_session(self, evt):
        # selecting session from session list calls this
        w = evt.widget
        value = None
        if len(w.curselection()) != 0:
            value = self.session_list.get(w.curselection()[0])
        if value == self.current_session:
            return
        self.join_session(value)

    def disable_sudoku(self, notify_msg=''):
        if notify_msg != '':
            self.insert_notification(notify_msg)
        for i in range(81):
            self.s_tiles[i//9][i%9].config(state='disabled')

    def join_session(self, sess_name):
        if self.leave_session(None):
            self.disable_sudoku('Joining session...')
            # result, state = ask server join room. False:msg = why failed... True:'wait' // paneme notify msg abil m2ngu k2ima
            self.outcon.join_room(sess_name)
            result, state = True, 'Waiting for players'
            if result:
                self.current_session = sess_name
                self.master.title('Playing in %s' % sess_name)
            else:
                self.master.title('Sudoku')
            self.disable_sudoku(state)
            #if result:  # delete next lines - for testing only
                #self.insert_sudoku_start(
                #    '1f,2f,3f,4f,5f,6f,7f,8f,9f,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_')

    def on_closing(self):
        if self.leave_session(None):
            self.master.destroy()
            logging.info('Window closing')
            # notify server about leaving



    #####################
    def is_running(self):
        try:
            self.master.state()
            return True
        except TclError:
            return False

    def register_con(self, outcon):
        self.outcon = outcon

    def add_all_rooms_clients(self, rooms, clients):
        self.clients = clients
        #for c in clients: self.chattext[c] = ''
        #map(lambda x: self.activelist.insert(END, x), clients)
        map(lambda x: self.session_list.insert(END, x), rooms)

    def add_client(self, client):
        print 'add_client ',client
        if client not in self.clients:
            self.clients.append(client)
            #self.activelist.insert(END, client)
            self.insert_notification("%s joined server" % client)
            #self.chattext[client] = ''


class Notifications(Thread):
    # Server calls these RPC functions to notify client
    def __init__(self, gui):
        self.gui = gui
        Thread.__init__(self)
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
        self.ch = self.connection.channel()
        self.setDaemon(daemonic=True)
        result = self.ch.queue_declare(exclusive=True)
        self.notification_queue = result.method.queue
        self.ch.queue_bind(exchange='direct_notify', queue=self.notification_queue, routing_key='all_clients')
        self.ch.basic_consume(self.on_receive, no_ack=True, queue=self.notification_queue)
        self.loop = Event()

    def run(self):
        self.loop.set()
        while self.loop.is_set():
                self.connection.process_data_events()
        self.connection.close()
        logging.debug('Notifications thread terminating...')

    def stop(self):
        self.loop.clear()

    def bind_queue(self, bind_to):
        self.ch.queue_bind(exchange='direct_notify', queue=self.notification_queue, routing_key=bind_to)

    def unbind_queue(self, unbind):
        self.ch.queue_unbind(exchange='direct_notify', queue=self.notification_queue, routing_key=unbind)

    def on_receive(self, ch, method, props, body):
        if not self.gui.is_running(): return
        logging.debug('NOTIFICATION: ' + body)
        if body.startswith('receive_msg_from:'):
            _, who, room, msg = body.split(':')
            self.gui.insertchattext(room, who, msg)

        elif body.startswith('receive_notification:'):
            self.gui.insert_notification("Server notification: " + body.split(':')[1])

        elif body.startswith('notify_new_client:'):
            self.gui.add_client(body.split(':')[1])

        elif body.startswith('notify_client_left:'):
            #self.gui.remove_room(body.split(':')[1])
            #TODO Remove client
            self.gui.insert_notification("Client '%s' left server" % body.split(':')[1])

        elif body.startswith('notify_joined_room:'):
            _, name, room = body.split(':')
           # self.gui.insertchatnotification(room, '%s joined' % name)
            self.gui.insert_notification("'%s' joined chat '%s'" % (name, room))

        elif body.startswith('notify_left_room:'):
            _, name, room = body.split(':')
            #self.gui.insertchatnotification(room, '%s left' % name)
            self.gui.insert_notification("'%s' left chat '%s'" % (name, room))

        elif body.startswith('notify_new_room:'):
            #self.gui.create_session(body.split(':')[1])
            self.gui.insert_new_session(body.split(':')[1])
            self.gui.insert_notification("Room '%s' has been opened" % body.split(':')[1])

        elif body.startswith('notify_room_closed:'):
            self.gui.remove_session(body.split(':')[1])
            self.gui.insert_notification("Room '%s' has closed, because it's last member left" % body.split(':')[1])

        elif body.startswith('notify_game_state:'):
            print(body)
            _, players, points, sudoku_board = body.split(':')
            players = players.split(',')
            points = points.split(',')
            scores = []
            for i in range(len(players)):
                scores.append(players[i]+" "+points[i])

            self.gui.insert_scores(scores)
            self.gui.insert_sudoku_start(sudoku_board)
            #self.gui.insert_notification("Room '%s' has closed, because it's last member left" % body.split(':')[1])

        elif body.startswith('Stopping:'):
            self.stop()
            tkMessageBox.showerror('Server shut down', 'Terminating')
            self.gui.stop()
        else:
            logging.debug('Faulty request [%s]' % body)



class Communication(object):
    # Client uses these RPC functions to communicate with server
    def __init__(self, gui):
        self.name = 'None'

        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
        self.ch = self.connection.channel()

        result = self.ch.queue_declare(exclusive=True)
        self.callback_queue = result.method.queue
        self.ch.queue_bind(exchange='direct_rpc', queue=self.callback_queue)
        self.ch.basic_consume(self.on_response, no_ack=True, queue=self.callback_queue)

        self.gui = gui
        self.receive_notifications = None
        gui.register_con(self)  # give GUI handler for calling communication functions

    def stop(self, notify_server=True):
        if self.receive_notifications is not None:
            self.receive_notifications.stop()
            self.receive_notifications.join()
        logging.debug('Requesting leave from server...')
        if notify_server:
            self.call('leave:' + self.name)
        logging.debug('Stopped communication...')

    def on_response(self, ch, method, props, body):
        if self.corr_id == props.correlation_id:
            self.response = body

    def call(self, body):
        self.response = None
        self.corr_id = str(uuid4())
        self.ch.basic_publish(exchange='direct_rpc', routing_key='rpc_queue',
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
        self.receive_notifications = Notifications(self.gui)
        self.receive_notifications.bind_queue(name)
        self.receive_notifications.start()
        return True

    def leave_room(self, chat_name):
        self.call('leave_room' + ':' + self.name + ':' + chat_name)
        self.receive_notifications.unbind_queue(chat_name)

    def join_room(self, chat_name):
        self.call('join_room' + ':' + self.name + ':' + chat_name)
        self.receive_notifications.bind_queue(chat_name)

    def create_room(self, chat_name, room_size):
        logging.debug("Creating room mofo!")
        body = 'create_room' + ':' + chat_name + ':' + str(room_size)
        return True if self.call(body) == 'True' else False

    def send_msg(self, to, msg):
        self.call('send_msg' + ':' + self.name + ':' + to + ':' + msg)


root = Tk()
gui = ClientQUI(root)
#root.mainloop()
try:
    com = Communication(gui)

    info_text = "Connecting..."
    while True:
        MY_NAME = tkSimpleDialog.askstring(info_text, "Enter your name")
        #TODO CHECK INPUT FORMAT
        info_text = 'Name refused'
        if MY_NAME == '' or MY_NAME is None:  # don't start application
            gui.on_closing()
            break
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