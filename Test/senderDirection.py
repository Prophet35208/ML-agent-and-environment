import arcade
import pika
import json

# Настройки Arcade
WIDTH = 400
HEIGHT = 300
TITLE = "Control Panel"

# Настройки RabbitMQ
RABBITMQ_HOST = 'localhost'  # Или IP адрес сервера RabbitMQ
QUEUE_NAME = 'direction_queue'


def send_message(direction):
    """Отправляет сообщение в RabbitMQ."""
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST))
        channel = connection.channel()
        channel.queue_declare(queue=QUEUE_NAME)

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

class MyGame(arcade.Window):
    def __init__(self, width, height, title):
        super().__init__(width, height, title)
        arcade.set_background_color(arcade.color.WHITE)

    def on_key_press(self, key, modifiers):
        """Вызывается при нажатии клавиши."""
        if key == arcade.key.UP:
            send_message("up")
            send_message("down")
            send_message("down")
            send_message("down")
            send_message("down")
            send_message("left")
        elif key == arcade.key.DOWN:
            send_message("down")
        elif key == arcade.key.LEFT:
            send_message("left")
        elif key == arcade.key.RIGHT:
            send_message("right")


def main():
    game = MyGame(WIDTH, HEIGHT, TITLE)
    arcade.run()


if __name__ == "__main__":
    main()