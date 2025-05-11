import arcade
import pika
import json
import threading
import time

# Настройки Arcade
WIDTH = 400
HEIGHT = 300
TITLE = "Control Panel"

# Настройки RabbitMQ
RABBITMQ_HOST = 'localhost'  # Или IP адрес сервера RabbitMQ
QUEUE_NAME = 'direction_queue'
REPLY_QUEUE_NAME = 'ball_position_queue'  # Новая очередь для ответов

class MyGame(arcade.Window):
    def __init__(self, width, height, title):
        super().__init__(width, height, title)
        arcade.set_background_color(arcade.color.WHITE)

        self.ball_position = None # Store the last known position

        self.setup_rabbitmq()

    def setup_rabbitmq(self):
        """Настраивает соединение с RabbitMQ в отдельном потоке."""
        self.rabbitmq_thread = threading.Thread(target=self.consume_replies, daemon=True)
        self.rabbitmq_thread.start()

    def consume_replies(self):
         try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST))
            channel = connection.channel()
            channel.queue_declare(queue=REPLY_QUEUE_NAME)

            def callback(ch, method, properties, body):
                """Обработчик сообщений для получения позиции шара."""
                try:
                    ball_position = json.loads(body.decode('utf-8'))
                    print(f" [x] Received ball position: {ball_position}")
                    self.ball_position = ball_position  # Store it for later use

                except json.JSONDecodeError:
                    print(f" [x] Received invalid JSON: {body}")

            channel.basic_consume(queue=REPLY_QUEUE_NAME, on_message_callback=callback, auto_ack=True)

            print(' [*] Waiting for ball position replies. To exit press CTRL+C')
            channel.start_consuming()  # Блокирующий вызов

         except pika.exceptions.AMQPConnectionError as e:
            print(f"Error connecting to RabbitMQ: {e}")
            # Retry connecting after a delay
            time.sleep(5)  # Wait for 5 seconds before retrying
            self.setup_rabbitmq() # Try to reconnect


    def send_message(self, direction):
        """Отправляет сообщение в RabbitMQ."""
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST))
            channel = connection.channel()
            channel.queue_declare(queue=QUEUE_NAME) # Ensure the request queue exists

            message = {'direction': direction}  # Создаем JSON-объект
            channel.basic_publish(exchange='', routing_key=QUEUE_NAME, body=json.dumps(message))  # Отправляем JSON

            print(f" [x] Sent '{message}' to RabbitMQ")

        except pika.exceptions.AMQPConnectionError as e:
            print(f"Error connecting to RabbitMQ: {e}")
        finally:
           try:
             connection.close() # Закрываем соединение, если оно было установлено
           except NameError:
             pass # Если connection не был инициализирован, ничего не делаем

    def on_key_press(self, key, modifiers):
        """Вызывается при нажатии клавиши."""
        if key == arcade.key.UP:
            self.send_message("up")
        elif key == arcade.key.DOWN:
            self.send_message("down")
        elif key == arcade.key.LEFT:
            self.send_message("left")
        elif key == arcade.key.RIGHT:
            self.send_message("right")


        if self.ball_position:  # Print AFTER the move and receiving the new coordinates
            print(f"Current Ball Position (from reply): {self.ball_position}")
        else:
            print("Waiting for initial ball position...")


def main():
    game = MyGame(WIDTH, HEIGHT, TITLE)
    arcade.run()


if __name__ == "__main__":
    main()