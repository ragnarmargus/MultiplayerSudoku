import pika
from time import sleep, time
from random import randint
from threading import Thread, Lock

connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))

channel = connection.channel()
channel.exchange_declare(exchange='direct_logs', exchange_type='direct')

l = Lock()

def fn(channel):
    arv = randint(0, 100)
    for i in range(1000):
        age = int(time()*10)
        with l:
            msg = 'name%d#%d' % (arv, age)
            print msg
            channel.basic_publish(exchange='direct_logs',
                                  routing_key='server_names',
                                  body=msg,)
        sleep(1)
tts = []
for i in range(10):
    t = Thread(target=fn, args=(channel,))
    t.start()
    tts.append(t)

for t in tts:
    t.join()

connection.close()