#!/usr/bin/env python
import pika
from sudoku import *

class Room:
    def __init__(self, game_name, room_size):
        self.name = game_name
        self.size = room_size
        self.players = []
        self.scores = []
        self.started = False
        self.finished = False
        self.game = Sudoku(2)


class Server:
    def __init__(self, server_name):
        self.server_name = server_name
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
        self.ch = self.connection.channel()

        self.ch.queue_declare(queue=server_name+'rpc_queue', exclusive=True)
        self.ch.exchange_declare(exchange=server_name+'direct_notify', exchange_type='direct')
        self.ch.exchange_declare(exchange=server_name+'direct_rpc', exchange_type='direct')

        self.ch.queue_bind(exchange=server_name+'direct_rpc', queue=server_name+'rpc_queue', routing_key='rpc_queue')
        self.ch.basic_consume(self.on_request, queue=server_name+'rpc_queue')

        self.clients = []
        self.rooms = {}

        self.ch.queue_declare(queue='servers_online')
        self.ch.basic_publish(exchange='', routing_key='servers_online',
                              body=self.server_name+'-up',properties=pika.BasicProperties( delivery_mode=2,  # make message persistent
                                                                                            ))

    def loop(self):
        print 'Start consuming...'
        self.ch.start_consuming()

    def stop(self):
        if len(self.clients) != 0:
            self.notify_clients('Stopping', 'Stopping')
        self.ch.basic_publish(exchange='', routing_key='servers_online',
                              body=self.server_name + '-down',
                              properties=pika.BasicProperties(delivery_mode=2,  # make message persistent
                                                              ))
        self.ch.stop_consuming()
        print 'Stop consuming...'

    def on_request(self, ch, method, props, body):
        print 'REQUEST: ' + body
        if body.startswith('request_name:'):
            resp = self.request_name(body.split(':')[1])
        elif body.startswith('leave_room:'):
            _, name, room = body.split(':')
            self.remove_me_from(name, room)
            resp = 'True'
        elif body.startswith('join_room:'):
            _, name, room = body.split(':')
            self.add_me_to(name, room)
            resp = 'True'
        elif body.startswith('create_room:'):
            _, chat_name, room_size = body.split(':')
            resp = 'True' if self.create_room(chat_name, int(room_size)) else 'False'
        elif body.startswith('send_msg:'):
            _, frm, to, msg = body.split(':')
            self.send_msg(frm, to, msg)
            resp = 'True'
        elif body.startswith('leave:'):
            name = body.split(':')[1]
            self.remove_me(name)
            resp = 'True'
        elif body.startswith('move:'):
            _, room, player, move = body.split(':')
            self.check_move(player, room, move)
            resp = 'True'

        else:
            print 'Faulty request [%s]' % body
            resp = 'False'
        self.ch.basic_publish(exchange='direct_rpc', routing_key=props.reply_to,
                              properties=pika.BasicProperties(correlation_id=props.correlation_id), body=resp)
        print 'REGUEST response:', resp
        self.ch.basic_ack(delivery_tag=method.delivery_tag)

    def notify_clients(self, header, msg, routing='all_clients'):
        msg = header + ':' + msg
        print 'NOTIFY - key [%s] - msg [%s]' % (routing, msg)
        self.ch.basic_publish(exchange=self.server_name+'direct_notify', routing_key=routing, body=msg, )

    # def notify_named_clients(self, header, msg, client_names):
    #     msg = header + ':' + msg
    #     for c in client_names:
    #         print 'NOTIFY - key [%s] - msg [%s]' % (c, msg)
    #         self.ch.basic_publish(exchange=self.server_name+'direct_notify', routing_key=c, body=msg, )

    def request_name(self, name):
        if name in self.rooms or name in self.clients:
            print 'Name [%s] not available' % name
            return 'False'
        self.clients.append(name)
        print 'Added name [%s]' % name
        self.notify_clients('notify_new_client', name)
        available_rooms = self.rooms
        print available_rooms
        return 'True:' + ','.join(available_rooms) + ':' + ','.join(self.clients)

    def remove_me(self, name):
        if name != 'None':
            if name in self.clients:
                self.clients.remove(name)
            rooms = filter(lambda x: name in self.rooms[x].players, self.rooms)
            map(lambda x: self.remove_me_from(name, x), rooms)
            self.notify_clients('notify_client_left', name)

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

    def add_me_to(self, name, room):
        if room in self.clients:
            return
        elif room in self.rooms and name not in self.rooms[room].players:
            self.rooms[room].players.append(name)
            self.rooms[room].scores.append(0)
            self.notify_clients('notify_joined_room', name + ':' + room, room)
            print 'Added [%s] to room [%s]' % (name, room)

            if (len(self.rooms[room].players) >= self.rooms[room].size) and (not self.rooms[room].started):  # remove empty room
                self.notify_clients('notify_game_start', "", room)
                self.rooms[room].started = True
                self.send_game_state(room)

            elif(self.rooms[room].started):
                self.send_game_state(room)
            else:
                self.send_start_screen(room)

    def create_room(self, game_name, room_size):
        if game_name in self.rooms or game_name in self.clients:
            print 'Game name %s not valid' % game_name
            return False
        print 'Creating game [%s]' % game_name
        self.rooms[game_name] = Room(game_name, room_size)
        self.notify_clients('notify_new_room', game_name)
        print 'Clients have been notified'
        print 'State of rooms:', str(self.rooms)
        return True

    # TODO Start new game when the last one finishes OR kick all players when finished
    def send_game_state(self,room):
        self.notify_clients('notify_game_state', ','.join(self.rooms[room].players) +\
                            ':' + ','.join(str(x) for x in self.rooms[room].scores) +\
                            ':' + self.rooms[room].game.sudoku_to_string_without_table(), room)

    def send_start_screen(self,room):
        self.notify_clients('notify_game_state', ','.join(self.rooms[room].players) +\
                            ':' + ','.join(str(x) for x in self.rooms[room].scores) +\
                            ':' + self.rooms[room].game.splash_screen_without_table(), room)

    def check_move(self,player,room,move):
        rsp = self.rooms[room].game.set_nr(list(move))
        if rsp==2:
            self.notify_clients('notify_winner', room + ':' + self.rooms[room].players[self.rooms[room].scores.index(max(self.rooms[room].scores))])
            self.rooms[room].finished = True
        self.rooms[room].scores[(self.rooms[room].players.index(player))] += rsp
        self.send_game_state(room)

server_name = ''
server = Server(server_name)

try:
    server.loop()
except KeyboardInterrupt:
    print 'CTRL-C pressed...'
finally:
    server.stop()
print 'Terminating...'


