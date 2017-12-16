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

# Somewhi KeyRelease event doesn't recognise keys with KP_number events
KB_map = {1:'KP_End', 2:'KP_Down', 3:'KP_Next', 4:'KP_Left',
        5:'KP_Begin', 6:'KP_Right', 7:'KP_Home', 8:'KP_Up', 9:'KP_Prior'}

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

        self.insert_scores(['Mina 1p', 'Sina 2p']) ## delete it

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
        for i in range(len(insertions)):
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
        # validating Sudoku entries
        if action == '1':  # action=1 -> insert
            if prior_value == value_if_allowed[-1]:
                return False
            if len(prior_value) >= 2:  # allow 2 numbers in cell, older will be deleted
                return False
            if text in '123456789':  # allow only 1...9 in cell
                return True
            return False
        return True  # allow deleting

    def act_upon_sudoku_insert(self, event):
        # acting upon correct Sudoku entry number_keyRelease
        w = event.widget
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
        success = True
        success = 'succeeded' if success else 'failed'
        self.insert_notification("Created game '%s' for %d %s" % (sess_name, player_count, success))

        self.insert_new_session(sess_name)  # testing - delete it

    def leave_session(self, evt):
        # Called when 'Leave' button is pressed or when window closes or when changing session
        if self.current_session is None:
            return True
        if not tkMessageBox.askyesno('Are you sure?', 'About to leave active session...'):
            return False
        # ask server to leave session
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
            #result, state = ask server join room. False:msg = why failed... True:'wait' // paneme notify msg abil m2ngu k2ima
            result, state = True, 'Waiting for players'
            if result:
                self.current_session = sess_name
                self.master.title('Playing in %s' % sess_name)
            else:
                self.master.title('Sudoku')
            self.disable_sudoku(state)
            if result:# delete next lines - for testing only
                self.insert_sudoku_start(
                    '1f,2f,3f,4f,5f,6f,7f,8f,9f,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_,0_')

    def on_closing(self):
        if self.leave_session(None):
            self.master.destroy()
            logging.info('Window closing')
            # notify server about leaving


root = Tk()
gui = ClientQUI(root)
root.mainloop()