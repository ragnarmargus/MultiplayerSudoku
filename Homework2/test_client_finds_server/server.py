import pika


connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))

channel = connection.channel()
channel.queue_declare(queue='servers_online')  # maybe add 'durable=True' flag

channel.basic_publish(exchange='',
                      routing_key='servers_online',
                      body='Servername2-up',
                      properties=pika.BasicProperties(
                         delivery_mode = 2, # make message persistent
                      ))

channel.basic_publish(exchange='',
                      routing_key='servers_online',
                      body='Servername-down',
                      properties=pika.BasicProperties(
                         delivery_mode = 2, # make message persistent
                      ))

connection.close()