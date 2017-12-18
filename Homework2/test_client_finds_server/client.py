import pika
from time import sleep

connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))

channel = connection.channel()
channel.queue_declare(queue='servers_online') # maybe durable=True flag
print(' [*] Waiting for messages. To exit press CTRL+C')

# When RabbitMQ quits or crashes it will forget the queues and messages unless you tell it not to.
# Two things are required to make sure that messages
# aren't lost: we need to mark both the queue and messages as durable.

servers_up = set()
def callback(ch, method, properties, body):
    print(" [x] Received %r" % body)
    name, status = body.split('-')
    if status == 'up':
        servers_up.add(name)
    else:
        if name in servers_up:
            servers_up.remove(name)

channel.basic_consume(callback, queue='servers_online')


connection.process_data_events()
print 'Up servers', servers_up

connection.close()