#!/usr/bin/env python
from Tkinter import *
import tkMessageBox
import logging
import tkSimpleDialog
from ScrolledText import ScrolledText
import pika
from uuid import uuid4
from dialog2 import MyDialog
from threading import Thread, Event

import logging
logging.basicConfig(level=logging.DEBUG,\
                    format='%(asctime)s (%(threadName)-2s) %(message)s',)
logging.getLogger("pika").setLevel(logging.WARNING)


class ChatQUI:
    def __init__(self, master):
        self.master = master
        master.resizable(False, False)
        master.title("Chat")

        self.chattext = {None: ''}

        self.clients = []

        self.createroom_button = Button(master, text="New chat")
        self.createroom_button.bind("<Button-1>", self.createroom)

        self.leave_button = Button(master, text="Leave chat")
        self.leave_button.bind("<Button-1>", self.leave)

        self.activeframe = Frame(master)
        self.activelist = Listbox(self.activeframe, exportselection=0)
        self.activescroll = Scrollbar(self.activeframe, orient="vertical")
        self.activelabel = Label(self.activeframe, text='Active rooms & clients:')
        self.activelabel.pack(fill='y')
        self.activelist.pack(side="left", fill="y")
        self.activescroll.pack(side="right", fill="y")
        self.activelist.config(yscrollcommand=self.activescroll.set)
        self.activescroll.config(command=self.activelist.yview)
        self.activelist.bind("<<ListboxSelect>>", self.setactive)

        self.inactiveframe = Frame(master)
        self.inactivelist = Listbox(self.inactiveframe, exportselection=0)
        self.inactivescroll = Scrollbar(self.inactiveframe, orient="vertical")
        self.inactivelabel = Label(self.inactiveframe, text='Available rooms:')
        self.inactivelabel.pack( fill='y')
        self.inactivelist.pack(side="left", fill="y")
        self.inactivescroll.pack(side="right", fill="y")
        self.inactivelist.config(yscrollcommand=self.inactivescroll.set)
        self.inactivescroll.config(command=self.inactivelist.yview)
        self.inactivelist.bind("<<ListboxSelect>>", self.connectroom)
        
        self.textbox = ScrolledText(master, state='disabled')
        self.notifybox = ScrolledText(master, state='disabled', height=3)

        self.input_user = StringVar()
        self.entry = Entry(master, text=self.input_user)
        self.entry.bind('<Return>', self.onenter)

        self.createroom_button.grid(row=0,column=0,rowspan=1,columnspan=1,sticky=W+E+S+N)
        self.leave_button.grid(     row=0,column=1,rowspan=1,columnspan=1,sticky=W+E+S+N)
        self.activeframe.grid(      row=1,column=0,rowspan=5,columnspan=2,sticky=W+E+S+N)
        self.inactiveframe.grid(    row=6,column=0,rowspan=4,columnspan=2,sticky=W+E+S+N)
        self.notifybox.grid(        row=0,column=3,rowspan=3,columnspan=5,sticky=W+E+S+N)
        self.textbox.grid(          row=3,column=3,rowspan=4,columnspan=5,sticky=W+E+S+N)
        self.entry.grid(            row=8,column=3,rowspan=3,columnspan=5,sticky=W+E+S+N)

        master.protocol("WM_DELETE_WINDOW", self.on_closing)

    def is_running(self):
        try:
            self.master.state()
            return True
        except TclError:
            return False

    def register_con(self, outcon):
        self.outcon = outcon

    def insert_notification(self, msg):
        self.notifybox.configure(state='normal')
        self.notifybox.insert(END, msg + '\n')
        self.notifybox.see(END)
        self.notifybox.configure(state='disabled')

    def stop(self):
        self.master.destroy()
        logging.info('Window closing')

    def on_closing(self, notify_server=True):
        self.master.withdraw()
        self.outcon.stop(notify_server)
        self.stop()

    def createroom(self, evt):
        r = MyDialog(self.master)
        if r is None: return
        logging.debug( 'Asking for [%s] creation - %s' % (r.result[0], str(r.result[1])))
        if len(r.result[1]) != 0 and self.outcon.name not in r.result[1]:
            members = r.result[1] + [self.outcon.name]
        else:
            members = []
        tf = 'success' if self.outcon.create_room(r.result[0], members) else 'failed'
        logging.debug('Creating room['+r.result[0]+'] - ' + tf)
        self.notifybox.insert(END, 'Creating room['+r.result[0]+'] - ' + tf)

    def leave(self, evt):
        value = self.activelist.get(ACTIVE)
        if len(value) == 0 or value in self.clients: return
        if value in self.chattext: self.chattext.pop(value)
        self.inactivelist.insert(END, value)
        self.activelist.delete(ACTIVE)
        self.setactivetext(None)
        self.outcon.leave_room(value)

    def setactive(self, evt):
        w=evt.widget
        value = None
        if len(w.curselection()) != 0:
            value = self.activelist.get(w.curselection()[0])
        self.setactivetext(value)
        if value in self.clients:
            self.leave_button.grid_remove()
        else:
            self.leave_button.grid()

    def insertchattext(self, to_where, who_sent, text):
        msg = who_sent + ': ' + text
        if to_where == self.outcon.name:
            to_where = who_sent
        if to_where in self.chattext:
            self.chattext[to_where] += msg + '\n'
        if to_where not in self.activelist.get(0, END):
            self.activelist.insert(END, to_where)
            self.inactivelist.delete(self.inactivelist.get(0, END).index(to_where))
        self.setactivetext(self.activelist.get(ACTIVE))
        logging.debug('Updating chat [%s] text [%s]' % (to_where, msg))

    def insertchatnotification(self, chat_name, text):
        if chat_name in self.chattext:
            self.chattext[chat_name] += text + '\n'
        self.setactivetext(self.activelist.get(ACTIVE))

    def connectroom(self, evt):
        w=evt.widget
        if len(w.curselection()) == 0: return
        value = self.inactivelist.get(w.curselection()[0])
        if len(value) == 0: return
        self.activelist.insert(END, value)     
        if value not in self.chattext:
            self.chattext[value] = ''
        self.inactivelist.delete(w.curselection())
        self.outcon.join_room(value)

    def setactivetext(self, chatname):
        if chatname == None:
            self.master.title("Chat")
        else:
            if chatname in self.clients:
                self.master.title("Chatting with %s" % chatname)
            else:
                self.master.title("Chatting in room %s" % chatname)
        if chatname not in self.chattext: return
        logging.debug('Setting chat [%s] active: text len %d' % (str(chatname), len(self.chattext[chatname])))
        self.textbox.configure(state='normal')
        self.textbox.delete('1.0', END)
        self.textbox.insert(END, self.chattext[chatname]+'\n')
        self.textbox.see(END)
        self.textbox.configure(state='disabled')

    def remove_room(self, room):
        if room in self.activelist.get(0, END):
            self.activelist.delete(self.activelist.get(0, END).index(room))
        if room in self.inactivelist.get(0, END):
            self.inactivelist.delete(self.inactivelist.get(0, END).index(room))
        if room in self.clients:
            self.clients.remove(room)
        if room in self.chattext:
            self.chattext.pop(room)

    def add_client(self, client):
        if client not in self.clients:
            self.clients.append(client)
            self.activelist.insert(END, client)
            self.insert_notification("%s joined server" % client)
            self.chattext[client] = ''

    def add_room(self, room):
        if room not in self.inactivelist.get(0, END):
            self.inactivelist.insert(END, room)
            self.insert_notification("New chat room '%s' available" % room)

    def add_all_rooms_clients(self, rooms, clients):
        self.clients = clients
        for c in clients: self.chattext[c] = ''
        map(lambda x: self.activelist.insert(END, x), clients)
        map(lambda x: self.inactivelist.insert(END, x), rooms)

    def onenter(self, evt):
        text = self.input_user.get()
        self.input_user.set('')
        if text == '':
            return
        logging.debug('Enter pressed, active chat [%s]' % self.activelist.get(ACTIVE))
        if self.activelist.get(ACTIVE) == '':
            return
        self.outcon.send_msg(self.activelist.get(ACTIVE), text.replace(':', ';'))


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
            self.gui.remove_room(body.split(':')[1])
            self.gui.insert_notification("Client '%s' left server" % body.split(':')[1])

        elif body.startswith('notify_joined_room:'):
            _, name, room = body.split(':')
            self.gui.insertchatnotification(room, '%s joined' % name)
            self.gui.insert_notification("'%s' joined chat '%s'" % (name, room))

        elif body.startswith('notify_left_room:'):
            _, name, room = body.split(':')
            self.gui.insertchatnotification(room, '%s left' % name)
            self.gui.insert_notification("'%s' left chat '%s'" % (name, room))

        elif body.startswith('notify_new_room:'):
            self.gui.add_room(body.split(':')[1])

        elif body.startswith('notify_room_closed:'):
            self.gui.remove_room(body.split(':')[1])
            self.gui.insert_notification("Room '%s' has closed, because it's last member left" % body.split(':')[1])

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

    def create_room(self, chat_name, private_list):
        body = 'create_room' + ':' + chat_name + ':' + ','.join(private_list)
        return True if self.call(body) == 'True' else False

    def send_msg(self, to, msg):
        self.call('send_msg' + ':' + self.name + ':' + to + ':' + msg)


root = Tk()
root.withdraw()  # hide TK for name confirmation period
my_gui = ChatQUI(root)
try:
    com = Communication(my_gui)

    info_text = "Connecting..."
    while True:
        MY_NAME = tkSimpleDialog.askstring(info_text, "Enter your name")
        info_text = 'Name refused'
        if MY_NAME == '' or MY_NAME is None:  # don't start application
            my_gui.on_closing()
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
                my_gui.on_closing()
            break

except pika.exceptions.ChannelClosed:
    logging.info('No server found...')

logging.info('Terminating application...')

