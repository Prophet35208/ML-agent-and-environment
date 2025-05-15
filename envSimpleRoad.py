from LibForRabbitMQ.Connectors import MLEnvConnector
import arcade
import pika
import json
import threading
import time

UP = 0
RIGHT = 1
DOWN = 2
LEFT = 3

# Настройки Arcade
WIDTH = 1000
HEIGHT = 600
TITLE = "SimpleRoadEnv"
BACKGROUND_COLOR = arcade.color.WHITE
BALL_RADIUS = 20
BALL_COLOR = arcade.color.BLUE
BALL_SPEED = 10  # Скорость движения шара

# Начальная позиция шара
BALL_START_X = WIDTH // 10
BALL_START_Y = HEIGHT // 2

# Дорога 
ROAD_WIDTH = WIDTH - 30
ROAD_HEIGHT = 70
ROAD_X = WIDTH // 2  # Центр дороги по X
ROAD_Y = HEIGHT // 2  # Центр дороги по Y
ROAD_COLOR = arcade.color.GRAY

# Настройки RabbitMQ
RABBITMQ_HOST = 'localhost'
AGENT_QUEUE = 'direction_queue'
ENV_REPLY_QUEUE = 'ball_position_queue'



class MyGame(arcade.Window):
    def __init__(self, width, height, title):
        super().__init__(width, height, title)
        arcade.set_background_color(BACKGROUND_COLOR)

        self.ball_x = BALL_START_X
        self.ball_y = BALL_START_Y
        self.direction_queue = []  # Очередь для хранения полученных направлений

        # Добавляем спрайт дороги
        self.road = arcade.Sprite(None, 1, hit_box_algorithm="None") # Не используем изображение, создадим прямоугольник
        self.road.width = ROAD_WIDTH
        self.road.height = ROAD_HEIGHT
        self.road.center_x = ROAD_X
        self.road.center_y = ROAD_Y

    # Этот обработчик вызывается, когда мы получаем сообщение от агента
    # Имеется несколько типов сообщений, определяемых по параметры type
    # Type = 0, сообщение о старте. Нужно передать текущие параметры шара. После чего ждать следующие сообщения.
    # Type = 1, следующий шаг. Для начала ждём, пока direction_queue не опустеет. После этого у нас будет достоверная позиция шара. Далее смотрим отправленное направление.
    # С учётом направления определяем коориданты шара после перемещения. Данные координаты надо будет отправить назад агенту (в случае обучения нужно так же отправить вознограждение)
    # Если шар вылетел с поля или дошёл до точки назначения, то нужно отправить reset = 1,resetCond = причина (вылетел за край или дошёл до конца). После этого нужно обновить симуляцию.
    def messageCallback(self, ch, method, properties, body):
        message = json.loads(body.decode('utf-8'))
        mType = message['type']
        # Старт
        if (mType == 0):
            x = self.ball_x 
            y = self.ball_y
            message = {'x': x, 'y': y}
            self.envConnector.channel.basic_publish(exchange='', routing_key=AGENT_QUEUE, body=json.dumps(message))
        if (mType == 1):
            while(self.direction_queue):
                time.sleep(0.06)
            xAfterStep = self.ball_x
            yAfterStep = self.ball_y
            dir = int(message['direction'])
            if (dir == UP):
                yAfterStep = yAfterStep + BALL_SPEED
            if (dir == RIGHT):
                xAfterStep = xAfterStep + BALL_SPEED
            if (dir == DOWN):
                yAfterStep = yAfterStep - BALL_SPEED
            if (dir == LEFT):
                xAfterStep = xAfterStep - BALL_SPEED

            # Далее нужно посмотреть, нужно ли ресетить

            # Далее передаём новые координаты в очередь на регистрацию средой (direction_queue)
            self.direction_queue.append(dir)
            # После этого отправляем сообщение агенту про следующие координаты
            reply = {'reset': 0, 'x': xAfterStep, 'y': yAfterStep}
            self.envConnector.channel.basic_publish(exchange='', routing_key=AGENT_QUEUE, body=json.dumps(reply))


            
                

    


    def setup(self):
        """Настройка игры (вызывается после инициализации окна)"""
        self.envConnector = MLEnvConnector(RABBITMQ_HOST, AGENT_QUEUE, ENV_REPLY_QUEUE)
        self.envConnector.connect()
        self.envConnector.startConsumingThread(self.messageCallback)
        arcade.schedule(self.process_messages, 0.05)  # Опрашиваем очередь RabbitMQ каждые 50мс


    def process_messages(self, delta_time):
        """Обрабатывает сообщения из очереди."""
        while self.direction_queue:
            direction = self.direction_queue.pop(0)
            self.move_ball(direction)

    def on_draw(self):
        """Вызывается для отрисовки сцены."""
        self.clear()
        arcade.draw_rect_filled(arcade.rect.XYWH(self.road.center_x, self.road.center_y, self.road.width, self.road.height), ROAD_COLOR)
        arcade.draw_circle_filled(self.ball_x, self.ball_y, BALL_RADIUS, BALL_COLOR)

    def move_ball(self, direction):
        """Перемещает шар в заданном направлении."""
        if direction == UP:
            self.ball_y += BALL_SPEED
        elif direction == DOWN:
            self.ball_y -= BALL_SPEED
        elif direction == LEFT:
            self.ball_x -= BALL_SPEED
        elif direction == RIGHT:
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