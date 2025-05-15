import pika
import json
import threading
import time

class MLAgentConnector:
    def __init__(self, host, agentQueue, envReplyQueue):
        self.host = host
        self.agent_queue = agentQueue  # Queue where agent sends actions (directions)
        self.env_reply_queue = envReplyQueue  # Queue where environment sends replies (ball position, rewards)
        self.connection = None  
        self.channel = None

    def connect(self):
        """Подключаемся к RabbitMQ. Определяем 2 очереди для обмена"""
        try:
            self.connection = pika.BlockingConnection(pika.ConnectionParameters(self.host))
            self.channel = self.connection.channel()
            self.channel.queue_declare(queue=self.agent_queue)
            self.channel.queue_declare(queue=self.env_reply_queue)

        except pika.exceptions.AMQPConnectionError as e:
            print(f"Error connecting to RabbitMQ: {e}")
            time.sleep(5)
            self.connect()

    # Инициализирует отдельную поток, где будут обрабатываться сообщения
    def startConsumingThread(self):
        self.rabbitmq_thread = threading.Thread(target=self.consumeReplies, daemon=True)
        self.rabbitmq_thread.start()
    
    # Отправляем сообщение о действии в среду

    def sendStart(self):
        try:
            message = {"type": 0, "training": 0}
            self.channel.basic_publish(exchange='', routing_key=self.agent_queue, body=json.dumps(message))

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
    def __init__(self, host, agent_queue, env_reply_queue):
        self.host = host
        self.agent_queue = agent_queue
        self.env_reply_queue = env_reply_queue
        self.connection = None
        self.channel = None
        self.action_callback = None 

    def connect(self):
        """Connects to RabbitMQ."""
        try:
            self.connection = pika.BlockingConnection(pika.ConnectionParameters(self.host))
            self.channel = self.connection.channel()
            self.channel.queue_declare(queue=self.agent_queue)
            self.channel.queue_declare(queue=self.env_reply_queue)

        except pika.exceptions.AMQPConnectionError as e:
            print(f"Error connecting to RabbitMQ: {e}")
            time.sleep(5)
            self.connect()

    def consumeMessages(self, callback):
        if self.channel:
            print("All OK")
            self.channel.basic_consume(queue=self.agent_queue, on_message_callback=callback, auto_ack=True)
            self.channel.start_consuming()  
        else:
            print("[EnvConnector] Error: Channel not initialized for consuming")

    def startConsumingThread(self, callback):
        self.action_thread = threading.Thread(target=self.consumeMessages, args=(callback,), daemon=True)
        self.action_thread.start()


    # Эта функция отправляет ответ на запрос агента.
    def sendReply():
        pass


    def close(self):
        """Closes the connection to RabbitMQ."""
        if self.connection and self.connection.is_open:
            self.connection.close()
            print("[EnvConnector] Connection closed.")

        

