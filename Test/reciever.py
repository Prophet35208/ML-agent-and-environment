import arcade
import pika
import json
import threading
import time

# Настройки Arcade
WIDTH = 400
HEIGHT = 300
TITLE = "Ball Control"
BACKGROUND_COLOR = arcade.color.WHITE
BALL_RADIUS = 20
BALL_COLOR = arcade.color.BLUE
BALL_SPEED = 10  # Скорость движения шара

# Начальная позиция шара
BALL_START_X = WIDTH // 2
BALL_START_Y = HEIGHT // 2

# Настройки RabbitMQ
RABBITMQ_HOST = 'localhost'
QUEUE_NAME = 'direction_queue'

class MyGame(arcade.Window):
    def __init__(self, width, height, title):
        super().__init__(width, height, title)
        arcade.set_background_color(BACKGROUND_COLOR)

        self.ball_x = BALL_START_X
        self.ball_y = BALL_START_Y
        self.direction_queue = []  # Очередь для хранения полученных направлений

    def setup(self):
        """Настройка игры (вызывается после инициализации окна)"""
        self.setup_rabbitmq()
        arcade.schedule(self.process_messages, 0.05)  # Опрашиваем очередь RabbitMQ каждые 50мс

    def setup_rabbitmq(self):
        """Настраивает соединение с RabbitMQ в отдельном потоке."""
        self.rabbitmq_thread = threading.Thread(target=self.consume_messages, daemon=True)
        self.rabbitmq_thread.start()

    def consume_messages(self):
        """Функция для потребления сообщений из RabbitMQ."""
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST))
            channel = connection.channel()
            channel.queue_declare(queue=QUEUE_NAME)

            def callback(ch, method, properties, body):
                """Обработчик сообщений."""
                try:
                    message = json.loads(body.decode('utf-8'))
                    direction = message['direction']
                    print(f" [x] Received direction: {direction}")
                    self.direction_queue.append(direction)  # Добавляем направление в очередь

                except json.JSONDecodeError:
                    print(f" [x] Received invalid JSON: {body}")

            channel.basic_consume(queue=QUEUE_NAME, on_message_callback=callback, auto_ack=True)

            print(' [*] Waiting for messages. To exit press CTRL+C')
            channel.start_consuming() # Блокирующий вызов

        except pika.exceptions.AMQPConnectionError as e:
            print(f"Error connecting to RabbitMQ: {e}")
            # Retry connecting after a delay
            time.sleep(5)  # Wait for 5 seconds before retrying
            self.setup_rabbitmq() # Try to reconnect

    def process_messages(self, delta_time):
        """Обрабатывает сообщения из очереди."""
        while self.direction_queue:
            direction = self.direction_queue.pop(0)
            self.move_ball(direction)

    def on_draw(self):
        """Вызывается для отрисовки сцены."""
        self.clear()
        arcade.draw_circle_filled(self.ball_x, self.ball_y, BALL_RADIUS, BALL_COLOR)

    def move_ball(self, direction):
        """Перемещает шар в заданном направлении."""
        if direction == "up":
            self.ball_y += BALL_SPEED
        elif direction == "down":
            self.ball_y -= BALL_SPEED
        elif direction == "left":
            self.ball_x -= BALL_SPEED
        elif direction == "right":
            self.ball_x += BALL_SPEED

        # Ограничение шара в пределах окна
        self.ball_x = max(BALL_RADIUS, min(self.ball_x, WIDTH - BALL_RADIUS))
        self.ball_y = max(BALL_RADIUS, min(self.ball_y, HEIGHT - BALL_RADIUS))

    def update(self, delta_time):
        """Вызывается для обновления логики игры (не используется в данном случае)."""
        pass

def main():
    game = MyGame(WIDTH, HEIGHT, TITLE)
    game.setup()  # Вызываем setup после создания экземпляра игры
    arcade.run()


if __name__ == "__main__":
    main()