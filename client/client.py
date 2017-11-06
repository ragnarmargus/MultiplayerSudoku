import logging
FORMAT='%(asctime)s (%(threadName)-2s) %(message)s'
logging.basicConfig(level=logging.DEBUG,format=FORMAT)
LOG = logging.getLogger()
from threading import Thread, Lock, currentThread
from socket import AF_INET, SOCK_STREAM, socket
from socket import error as soc_err

server_address = ('127.0.0.1',7777)
s = socket(AF_INET, SOCK_STREAM)
s.connect(server_address)

def socket_rcv_print(s):
    msg = ''
    while 1:
        msg += s.recv(1)
        if msg[-1] == '#':
            print msg
            msg = ''

t_listener = Thread(target = socket_rcv_print, args = (s,))
t_listener.start()
while 1:
    msg = raw_input('\nFull msg: ')
    s.sendall(msg)

s.close()
