import pika
from time import sleep, time

connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))

channel = connection.channel()
channel.exchange_declare(exchange='direct_logs', exchange_type='direct')

result = channel.queue_declare(exclusive=True)
queue_name = result.method.queue

channel.queue_bind(exchange='direct_logs', queue=queue_name, routing_key='server_names')

# When RabbitMQ quits or crashes it will forget the queues and messages unless you tell it not to.
# Two things are required to make sure that messages
# aren't lost: we need to mark both the queue and messages as durable.

servers_up = dict()
def callback(ch, method, properties, body):
    print(" [x] Received %r" % body)
    nimi, last_update = body.split('#')
    if last_update == 'dead':
        servers_up[nimi] = 0
    else:
        servers_up[nimi] = int(last_update)/10
    print len(servers_up)

    print filter(lambda x: servers_up[x] >= time() - 3, servers_up)

channel.basic_consume(callback, queue=queue_name)

for i in range(1000):
    connection.process_data_events()
    sleep(0.1)
print 'Up servers', servers_up

connection.close()