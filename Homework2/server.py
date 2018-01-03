#!/usr/bin/env python
import pika
from sudoku import *
from threading import Event
from time import time


# The class holds a Sudoku instance, the rooms players and scores
class Room:
    def __init__(self, game_name, room_size):
        self.name = game_name
        self.size = room_size
        self.players = []
        self.scores = []
        self.started = False
        self.finished = False
        self.game = Sudoku(2)


# Gets a unique name for the server (in the form of Server#, where # is a number)
# Sets up queue for RPC and exchanges for RPC and notifications.
#
# RPC is based on https://www.rabbitmq.com/tutorials/tutorial-six-python.html. It works as follows:
#   1. server creates an exclusive /*server_name*/rpc_queue, which is bound to /*server_name*/direct_notify exchange
#   2. client creates it's own queue, where it receives the RPC replies
# When client does a RPC, the call includes a correlationID for reply identification
# and also where the it expects the response.
#
# In case many clients need the response a notification message will be sent. The routing key determines who will
# receive the message. Two routing keys are used: 'all_clients' - everyone listening gets the message and
# '/*room name*/' - only clients in the room will get the message
#
# Periodically sends broadcasts with its name, so clients can connect
class Server:
    def __init__(self):
        i = 0
        while True:  # Loop untill a exclusive access to a queue is got (this means, server name is available)
            try:
                self.server_name = 'Server' + str(i)
                self.connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
                self.ch = self.connection.channel()
                self.ch.queue_declare(queue=self.server_name + 'rpc_queue', exclusive=True)
                print 'Server shall use name [%s] ' % self.server_name
                break
            except pika.exceptions.ChannelClosed as e:
                i += 1
        # Declare exhanges for notifications and RPCs
        self.ch.exchange_declare(exchange=self.server_name+'direct_notify', exchange_type='direct')
        self.ch.exchange_declare(exchange=self.server_name+'direct_rpc', exchange_type='direct')
        # Start consuming on direct_rpc queue
        self.ch.queue_bind(exchange=self.server_name+'direct_rpc', queue=self.server_name+'rpc_queue', routing_key='rpc_queue')
        self.ch.basic_consume(self.on_request, queue=self.server_name+'rpc_queue')

        self.clients = []  # stores clients on the server
        self.rooms = {}  # stores game sessions

        # Broadcast its name to queue servers_online so clients know where to connect
        self.ch.queue_declare(queue='servers_online')
        self.ch.exchange_declare(exchange='online_servers', exchange_type='direct')

        self.looping = Event()  # allows the loop to be stopped

    # Periodically broadcasts its name. Otherwise check for incoming RPC requests
    def loop(self):
        self.looping.set()
        print 'Start consuming...'
        last_notification_at = 0
        while self.looping.is_set():
            self.connection.process_data_events()
            if last_notification_at + 1 < time():
                last_notification_at = time()
                self.ch.basic_publish(exchange='online_servers', routing_key='server_names',
                                      body=self.server_name + '#' + str(int(time()*10)),
                                      properties=pika.BasicProperties())

    # Stops looping. Broadcasts 'dead' message and notifies clients the server is going down, so clients can close
    def stop(self):
        self.looping.clear()
        self.ch.basic_publish(exchange='online_servers', routing_key='server_names',
                              body=self.server_name + '#dead', properties=pika.BasicProperties())
        if len(self.clients) != 0:
            self.notify_clients('Stopping', 'Stopping')
        print 'Stop consuming...'

    # Differentiates RPC based on message header.
    # Sends back RPC response with correct correlationID and into the correct client queue
    def on_request(self, ch, method, props, body):
        print 'REQUEST: ' + body
        if body.startswith('request_name:'):  # client asks if it's name is OK
            resp = self.request_name(body.split(':')[1])
        elif body.startswith('leave_room:'):  # clients want's to be removed from session
            _, name, room = body.split(':')
            self.remove_me_from(name, room)
            resp = 'True'
        elif body.startswith('join_room:'):  # client want's to join session. If enough players, start game
            _, name, room = body.split(':')
            self.add_me_to(name, room)
            resp = 'True'
        elif body.startswith('create_room:'):  # client want's to create session. If name available create it
            _, chat_name, room_size = body.split(':')
            resp = 'True' if self.create_room(chat_name, int(room_size)) else 'False'
        elif body.startswith('leave:'):  # client want's to leave the server
            name = body.split(':')[1]
            self.remove_me(name)
            resp = 'True'
        elif body.startswith('move:'):  # client wants to interact with the Sudoku
            _, room, player, move = body.split(':')
            self.check_move(player, room, move)
            resp = 'True'
        else:
            print 'Faulty request [%s]' % body
            resp = 'False'
        # Send back RPC response with correct correlationID and into the correct client queue
        self.ch.basic_publish(exchange=self.server_name + 'direct_rpc', routing_key=props.reply_to,
                              properties=pika.BasicProperties(correlation_id=props.correlation_id), body=resp)
        print 'REGUEST response:', resp
        self.ch.basic_ack(delivery_tag=method.delivery_tag)

    # Sends notification message with a specified header.
    # Routing allows to notify either all clients or clients in a specific session
    def notify_clients(self, header, msg, routing='all_clients'):
        msg = header + ':' + msg
        print 'NOTIFY - key [%s] - msg [%s]' % (routing, msg)
        self.ch.basic_publish(exchange=self.server_name+'direct_notify', routing_key=routing, body=msg, )

    # If client requested name is ok, reply with available sessions. Otherwise return False
    def request_name(self, name):
        if name in self.rooms or name in self.clients:
            print 'Name [%s] not available' % name
            return 'False'
        self.clients.append(name)
        print 'Added name [%s]' % name
        self.notify_clients('notify_new_client', name)
        available_rooms = self.rooms
        return 'True:' + ','.join(available_rooms) + ':' + ','.join(self.clients)

    # Client leaves the server. Notifies other clients about it
    def remove_me(self, name):
        if name != 'None':
            if name in self.clients:
                self.clients.remove(name)
            rooms = filter(lambda x: name in self.rooms[x].players, self.rooms)
            map(lambda x: self.remove_me_from(name, x), rooms)
            self.notify_clients('notify_client_left', name)

    # Client wants to leave a session.
    # If only one player left, declare the last one winner and close the session
    def remove_me_from(self, name, room):
        if room in self.clients:
            return
        elif room in self.rooms and name in self.rooms[room].players:
            self.rooms[room].scores.pop(self.rooms[room].players.index(name))
            self.rooms[room].players.remove(name)
            self.notify_clients('notify_left_room', name + ':' + room, room)
            self.send_game_state(room)
            print 'Removed [%s] from room [%s]' % (name, room)

            if (len(self.rooms[room].players) == 1) and not (self.rooms[room].finished) and (self.rooms[room].started):
                self.notify_clients('notify_winner', room + ':' + self.rooms[room].players[0])
                self.rooms[room].finished = True

            elif len(self.rooms[room].players) == 0:  # remove empty room
                self.notify_clients('notify_room_closed', room)
                self.rooms.pop(room)
        print 'State of rooms:', str(self.rooms)

    # Client wants to join a session.
    # If enough players have joined the room, starts the game
    def add_me_to(self, name, room):
        if room in self.clients:
            return
        elif room in self.rooms and name not in self.rooms[room].players:
            self.rooms[room].players.append(name)
            self.rooms[room].scores.append(0)
            self.notify_clients('notify_joined_room', name + ':' + room, room)
            print 'Added [%s] to room [%s]' % (name, room)

            if (len(self.rooms[room].players) >= self.rooms[room].size) and (not self.rooms[room].started):
                self.notify_clients('notify_game_start', "", room)
                self.rooms[room].started = True
                self.send_game_state(room)

            elif self.rooms[room].started:
                self.send_game_state(room)
            else:
                self.send_start_screen(room)

    # Creates a new room, if the name is available. Notifies others if created
    def create_room(self, game_name, room_size):
        if game_name in self.rooms or game_name in self.clients:
            print 'Game name %s not valid' % game_name
            return False
        print 'Creating game [%s]' % game_name
        self.rooms[game_name] = Room(game_name, room_size)
        self.notify_clients('notify_new_room', game_name)
        print 'Clients have been notified'
        return True

    # Sends a Sudoku board
    def send_game_state(self, room):
        self.notify_clients('notify_game_state', ','.join(self.rooms[room].players) +
                            ':' + ','.join(str(x) for x in self.rooms[room].scores) +
                            ':' + self.rooms[room].game.sudoku_to_string_without_table(), room)

    # Sends a Sudoku boards, that doens't allow interaction. Wait for players to join
    def send_start_screen(self, room):
        self.notify_clients('notify_game_state', ','.join(self.rooms[room].players) +
                            ':' + ','.join(str(x) for x in self.rooms[room].scores) +
                            ':' + self.rooms[room].game.splash_screen_without_table(), room)

    # Client wants to put a number into the Sudoku board
    # if the Sudoku has been correctly solved, Declare the winner and close the session
    def check_move(self, player, room, move):
        rsp = self.rooms[room].game.set_nr(list(move))
        self.rooms[room].scores[(self.rooms[room].players.index(player))] += rsp
        if rsp == 2:
            self.rooms[room].scores[(self.rooms[room].players.index(player))] -= 1
            names = []
            for i in range(len(self.rooms[room].players)):
                if self.rooms[room].scores[i] == max(self.rooms[room].scores):
                    names.append(self.rooms[room].players[i])
            self.notify_clients('notify_winner', room + ':' + ', '.join(names))
            self.rooms[room].finished = True
        self.send_game_state(room)


server = Server()
try:
    server.loop()
except KeyboardInterrupt:
    print 'CTRL-C pressed...'
finally:
    server.stop()
print 'Terminating...'


