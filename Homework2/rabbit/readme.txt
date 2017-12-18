Used:
	python 2.7
		TKinter,  pika 0.11.2
	rabbitmq-server Version: 3.6.6-1
	erlang Version: 1:19.2.1+dfsg-2ubuntu1

The client and server code were written taking rabbitMQ tutorals RPC example as starting point. 
The server creates a queue for RPC calls and two direct exchanges: one for RPC calls and the other for client notifications. Server starts consuming messages with routing_key = 'rpc_queue'.

If the client calls a RPC function, it expects a reply from the server into the its own RPC reply queue.
The server can put notifications into the notifications queue (exchange='direct_notify') - such as new rooms/clients and new messages. Clients will receive notification messages based on routing_keys on exhange='direct_notify'. All the clients will listen to routing_key 'all_clients' and 'its-own-name'. If a client joins a room, it will start listening on 'room-name'. When private room is created, only privileged get notified and can join.

About client GUI:
	upper text box - displays notifications (such as client joined, new room...)
	big text box in the center - displays chat texts. It is changed when you select a chat
	low text box - there you can write and on ENTER, if an active room/client has been selected, msg will be sent
	
	on the left:
		upper list box - contains all clients on the server and chat rooms the client is participating in.
		You can use leave button to leave a chat, then you won't receive updates about it either,
		The button is disabled, if currently active chat happens to be a client
		Selecting rooms in the upper list box also changes active text and sets to which room/client you write

		lower list box - contains available rooms (private chats will be listed there, if the client is supposed to
		be a member of that room). On mouse click, the client will join the selected room

		create new room button - new room can be created. If creating a private room, the creator will be added
		also be permitted to enter the room.
		
		leave button - only for active rooms (disabled for clients). Can notify server, to be removed from the chat

Closing the Tkinter window sends notification to the server about it, so clients can get notified. If the server is shut down, it notifies the clients and clients will shut down also.

The clients and servers are set to operate on localhost.

to run write to terminal:
	python server.py
	python client.py (multiple can be opened)
		

