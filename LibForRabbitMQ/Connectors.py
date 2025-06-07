import pika
import json
import threading
import time
import uuid
import logging
import datetime
import os

TIMEOUT_WARNING_LEN = 5
TIMEOUT_EXIT_LEN = 10

class RabbitMQConnectionError(Exception):
    """Пользовательское исключение для проблем с соединением RabbitMQ."""
    pass

class MLAgentConnector:
    def __init__(self, host, envQueue):
        self.host = host
        self.env_queue = envQueue 
        self.connection = None  
        self.channel = None
        self.i = 0
        
        current_directory = os.path.dirname(os.path.abspath(__file__))
        self.log_file_path = os.path.join(current_directory, 'logs.log')
        logging.basicConfig(filename=self.log_file_path, level=logging.INFO, format='%(message)s')

    def on_response(self, ch, method, props, body):
        if self.corr_id == props.correlation_id:
            self.response = body
   
    def connect(self):
        try:
            self.connection = pika.BlockingConnection(pika.ConnectionParameters(self.host))
            if not self.connection.is_open:
                return -1
                    
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
            f = 0
            return 0
        except Exception as e:
            return -1

    def try_reconnect(self):
        f = 1
        start_time = time.time() 
        timeout_warning = TIMEOUT_WARNING_LEN       
        timeout_exit = TIMEOUT_EXIT_LEN      

        while (f):
            elapsed_time = time.time() - start_time
            if elapsed_time > timeout_exit:
                print("Timeout: Не удалось подключится, возврат в меню.")
                break 

            elif elapsed_time > timeout_warning:
                print(f"Предупреждение: Не удалось восстановить соединение в течении {timeout_warning} секунд...")
                timeout_warning = float('inf') 

            f = self.connect()

        if (f):
            return -1
        else:
            print("Подключение успешно восстановлено. Продолжение обучения")
            return 0

    # Отправляем сообщение о действии в среду
    def send_start_and_wait_reply(self):

        self.response = None
        self.corr_id = str(uuid.uuid4()) # Генерируем идентификатор запроса
         
        timeout_warning = TIMEOUT_WARNING_LEN       
        timeout_exit = TIMEOUT_EXIT_LEN        
        get_message_flag = 1

        message = {"type": 0, "training": 0}

        try:
            self.channel.basic_publish(exchange='', routing_key=self.env_queue, properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=self.corr_id,
            ), body=json.dumps(message))

        except pika.exceptions.AMQPConnectionError as e:
            print(f" [AgentConnector] Ошибка при отправке сообщения.")
            print(f"Пробуем восстановить соединение.\n")
            f = self.try_reconnect()
            if (f):
                return -1
            else:

                self.channel.basic_publish(exchange='', routing_key=self.env_queue, properties=pika.BasicProperties(
                    reply_to=self.callback_queue,
                    correlation_id=self.corr_id,
                ), body=json.dumps(message))


        start_time = time.time() 

        while self.response is None: # Ждём ответ
            elapsed_time = time.time() - start_time

            if elapsed_time > timeout_exit:
                print(f"\nTimeout: Не получен ответ в течение {timeout_exit} секунд. Выход из текущего процесса обучения.")
                get_message_flag = 0
                break 

            elif elapsed_time > timeout_warning:
                print(f"\nПредупреждение: Ответ не получен в течение {timeout_warning} секунд...")
                timeout_warning = float('inf') 


            self.connection.process_data_events(time_limit=1)
        if (get_message_flag):
            self.last_message = json.loads(self.response.decode('utf-8'))
            return 0
        else:
            return -1
    
    def send_step_and_wait_reply(self, direction,episode,step):
        self.response = None
        timeout_warning = TIMEOUT_WARNING_LEN       
        timeout_exit = TIMEOUT_EXIT_LEN        
        get_message_flag = 1
        try:
            message_id = str(uuid.uuid4())
            message = {"type": 1, "training": 0, "direction": direction}
            self.channel.basic_publish(exchange='', routing_key=self.env_queue, properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=self.corr_id,
            ), body=json.dumps(message))

            self.log_message(message,episode, step,"sent")

            start_time = time.time() 
            while self.response is None: # Ждём ответ
                elapsed_time = time.time() - start_time

                if elapsed_time > timeout_exit:
                    print(f"\nTimeout: Не получен ответ в течение {timeout_exit} секунд. Выход из текущего процесса обучения.")
                    timed_out = True
                    get_message_flag = 0
                    break 

                elif elapsed_time > timeout_warning:
                    print(f"\nПредупреждение: Ответ не получен в течение {timeout_warning} секунд...")
                    timeout_warning = float('inf') 

                self.connection.process_data_events(time_limit=1)
                
            if (get_message_flag):
                self.last_message = json.loads(self.response.decode('utf-8'))
                self.log_message(self.last_message,episode,step, "received")
                return 0
            else:
                return -1



        except pika.exceptions.AMQPConnectionError as e:
            print(f" [AgentConnector] Ошибка при отправке сообщения: {e}")
            f = self.try_reconnect()
            if (f):
                return -1
            else:
                return 0
    
    def log_message(self, message,episode, step, message_type="sent"):
        """Записывает отформатированное сообщение в лог."""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        log_string = f"{timestamp}, "  # Начинаем строку с датой и временем

        if message_type == "sent":
            log_string += "Сообщение отправлено."
            if episode is not None and step is not None:
                log_string += f" Эпизод {episode}, шаг {step}."
            log_string += "\nОтправленные данные:\n"
            for key, value in message.items():
                log_string += f"\t{key}: {value}\n"  
        elif message_type == "received":
            log_string += "Сообщение получено.\n"
            log_string += "\nПолученные данные:\n"
            for key, value in message.items():
                log_string += f"\t{key}: {value}\n" 
        elif message_type == "error":
            log_string += "Ошибка при обработке.\n"
            log_string += f"Сообщение об ошибке: {message}\n" 
        else:
            log_string += f"Неизвестный тип сообщения: {message_type}\n" 

        logging.info(log_string)  # Записываем все в лог

    def setup_logs(self):
        
        with open(self.log_file_path, 'w'):
            pass  # Очищаем файл для логов


        logging.basicConfig(
            filename=self.log_file_path,  # Записываем в файл
            level=logging.INFO,  # Записываем только INFO и выше
            format="%(message)s",  # Только сообщение (никаких уровней логирования, имен и т.д.)
            filemode='w'  
        )

    def close(self):
        if self.connection and self.connection.is_open:
            self.connection.close()
            print("[AgentConnector] Соединение успешно завершено.")





class MLEnvConnector:
    def __init__(self, host, env_queue):
        self.host = host
        self.env_queue = env_queue
        self.connection = None
        self.channel = None
        self.action_callback = None 

    def connect(self):
            try:
                self.connection = pika.BlockingConnection(pika.ConnectionParameters(self.host))
                self.channel = self.connection.channel()
                self.channel.queue_declare(queue=self.env_queue)
                return 0
            except Exception as e:
                return -1

    def try_reconnect(self):
        f = 1
        start_time = time.time() 
        timeout_warning = TIMEOUT_WARNING_LEN       
        timeout_exit = TIMEOUT_EXIT_LEN      

        while (f):
            elapsed_time = time.time() - start_time
            if elapsed_time > timeout_exit:
                print("Не удалось восстановить соединение. Завершение работы.")
                break 

            elif elapsed_time > timeout_warning:
                print(f"Предупреждение: Ответ не получен в течение {timeout_warning} секунд...")
                timeout_warning = float('inf') 

            f = self.connect()

        if (f):
            return -1
        else:
            print("Подключение успешно восстановлено. ")
            return 0
    
    def consumeMessages(self, callback):
        while(True):
            try:
                self.channel.basic_consume(queue=self.env_queue, on_message_callback=callback, auto_ack=True)
                self.channel.start_consuming()  
            except pika.exceptions.AMQPConnectionError as e:
                print(f"[EnvConnector] Соединение с RabbitMQ потеряно: {e}")
                print("[EnvConnector] Попытка восстановления соединения...")
                if self.try_reconnect() == -1:
                    return -1

    def startConsumingThread(self, callback):
        self.action_thread = threading.Thread(target=self.consumeMessages, args=(callback,), daemon=True)
        self.action_thread.start()

    def sendMessageToAgent(self, props, message):
        self.channel.basic_publish(exchange='', routing_key=props.reply_to, properties=pika.BasicProperties(correlation_id = props.correlation_id),body=json.dumps(message))


    def close(self):
        """Closes the connection to RabbitMQ."""
        if self.connection and self.connection.is_open:
            self.connection.close()
            print("[EnvConnector] Connection closed.")

        

