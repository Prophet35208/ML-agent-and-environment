import pika
import json
import threading
import time
import uuid

class MLAgentConnector:
    def __init__(self, host, envQueue):
        self.host = host
        self.env_queue = envQueue  # Queue where environment sends replies (ball position, rewards)
        self.connection = None  
        self.channel = None

    def on_response(self, ch, method, props, body):
        if self.corr_id == props.correlation_id:
            self.response = body
   
    def connect(self):

        try:
            self.connection = pika.BlockingConnection(pika.ConnectionParameters(self.host))
            self.channel = self.connection.channel()

            # Определим очередь, в которой будем получать ответы от среды
            result = self.channel.queue_declare(queue='', exclusive=True)
            self.callback_queue = result.method.queue

            self.channel.basic_consume(
            queue=self.callback_queue,
            on_message_callback=self.on_response,
            auto_ack=True)
            
            # Текущий ответ
            self.response = None
            self.corr_id = None


        except pika.exceptions.AMQPConnectionError as e:
            print(f"Error connecting to RabbitMQ: {e}")
            time.sleep(5)
            self.connect()

    # Инициализирует отдельную поток, где будут обрабатываться сообщения
    def start_consuming_thread(self):
        self.rabbitmq_thread = threading.Thread(target=self.consumeReplies, daemon=True)
        self.rabbitmq_thread.start()
    
    # Отправляем сообщение о действии в среду

    def send_start_and_wait_reply(self):
        self.response = None
        self.corr_id = str(uuid.uuid4()) # Генерируем идентификатор запроса
        try:
            message = {"type": 0, "training": 0}
            self.channel.basic_publish(exchange='', routing_key=self.env_queue, properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=self.corr_id,
            ), body=json.dumps(message))

            while self.response is None: # Ждём ответ
                self.connection.process_data_events(time_limit=None)
            self.last_message = json.loads(self.response.decode('utf-8'))

        except pika.exceptions.AMQPConnectionError as e:
            print(f" [AgentConnector] Error sending action: {e}")
            self.connect()

    def send_step_and_wait_reply(self, direction):
        self.response = None
        self.corr_id = str(uuid.uuid4()) # Генерируем идентификатор запроса
        try:
            message = {"type": 1, "training": 0, "direction": direction}
            self.channel.basic_publish(exchange='', routing_key=self.env_queue, properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=self.corr_id,
            ), body=json.dumps(message))

            while self.response is None: # Ждём ответ
                self.connection.process_data_events(time_limit=None)
            self.last_message = json.loads(self.response.decode('utf-8'))

        except pika.exceptions.AMQPConnectionError as e:
            print(f" [AgentConnector] Error sending action: {e}")
            self.connect()



    def send_action(self, action):
        if not self.channel or not self.connection.is_open:
            print("[AgentConnector] Error: Not connected to RabbitMQ.")
            return

        try:
            message = {"type": 1, "training": 0}
            self.channel.basic_publish(exchange='', routing_key=self.agent_queue, body=json.dumps(message))

        except pika.exceptions.AMQPConnectionError as e:
            print(f" [AgentConnector] Error sending action: {e}")
            self.connect()

    def sendReset(self):
        try:
            message = {"type": 2, "training": 0}
            self.channel.basic_publish(exchange='', routing_key=self.agent_queue, body=json.dumps(message))

        except pika.exceptions.AMQPConnectionError as e:
            print(f" [AgentConnector] Error sending action: {e}")
            self.connect()

    
    def close(self):
        if self.connection and self.connection.is_open:
            self.connection.close()
            print("[AgentConnector] Connection closed.")



class MLEnvConnector:
    def __init__(self, host, env_queue):
        self.host = host
        self.env_queue = env_queue
        self.connection = None
        self.channel = None
        self.action_callback = None 

    def connect(self):
        """Connects to RabbitMQ."""
        try:
            self.connection = pika.BlockingConnection(pika.ConnectionParameters(self.host))
            self.channel = self.connection.channel()
            self.channel.queue_declare(queue=self.env_queue)

        except pika.exceptions.AMQPConnectionError as e:
            print(f"Error connecting to RabbitMQ: {e}")
            time.sleep(5)
            self.connect()

    def consumeMessages(self, callback):
        if self.channel:
            self.channel.basic_consume(queue=self.env_queue, on_message_callback=callback, auto_ack=True)
            self.channel.start_consuming()  
        else:
            print("[EnvConnector] Error: Channel not initialized for consuming")

    def startConsumingThread(self, callback):
        self.action_thread = threading.Thread(target=self.consumeMessages, args=(callback,), daemon=True)
        self.action_thread.start()

    def sendMessageToAgent(self, props, message):
        self.channel.basic_publish(exchange='', routing_key=props.reply_to, properties=pika.BasicProperties(correlation_id = props.correlation_id),body=json.dumps(message))


    # Эта функция отправляет ответ на запрос агента.
    def sendReply():
        pass


    def close(self):
        """Closes the connection to RabbitMQ."""
        if self.connection and self.connection.is_open:
            self.connection.close()
            print("[EnvConnector] Connection closed.")

        

