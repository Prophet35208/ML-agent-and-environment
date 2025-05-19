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
BALL_COLOR = arcade.color.AMERICAN_ROSE
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

# Настройки границ дороги
BORDER_WIDTH = 5

# Флаг
FLAG_IMAGE_PATH = "Environment/Images/flag.png"
FLAG_SKALE = 0.1

# Причины перезапуска (ресетов)
RESET_CAUSE_OUT_OF_ROAD = 1
RESET_CAUSE_REACHED_FINISH = 2

# Настройки вознограждений
REWARD_GET_CLOSER = 1
REWARD_GET_FURTHER = -1
REWARD_GET_OFF_ROAD = -10
REWARD_REACHED_FLAG = 10

# Настройки RabbitMQ
RABBITMQ_HOST = 'localhost'
ENV_QUEUE = 'env_eueue'

class MyGame(arcade.Window):
    def __init__(self, width, height, title):
        super().__init__(width, height, title)
        arcade.set_background_color(BACKGROUND_COLOR)

        self.ball = None  # Спрайт шара
        self.ball_sprite_list = arcade.SpriteList()

        # Добавляем дорогу
        self.road = None
        self.road_sprite_list = arcade.SpriteList()
        self.borders_sprite_list = arcade.SpriteList()

        # Добавляем флаг
        self.road = None
        self.flag_sprite_list = arcade.SpriteList()

        self.direction_queue = []  # Очередь для хранения полученных направлений

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
            x = self.ball.center_x
            y = self.ball.center_y
            reply = {'reset': 0 ,'x': x, 'y': y}
            self.envConnector.sendMessageToAgent(properties, reply)
        if (mType == 1):
            dir = int(message['direction'])

            previous_x = self.ball.center_x
            previous_y = self.ball.center_y

            self.move_ball(dir)

            current_x = self.ball.center_x
            current_y = self.ball.center_y

            # Далее нужно посмотреть, нужно ли ресетить. Мячик мы подвинули, теперь смотрим коллизии
            # Если вышел за пределы дороги
            reset = False
            road_collision = self.ball.collides_with_list(self.borders_sprite_list)
            if road_collision:
                # Коллизия имеется
                reset = True
                # Возвращаем мяч в начало
                self.reset_ball_position()
                # Отправляем сообщение 
                reply = {'reset': 1 , 'reset_cause': RESET_CAUSE_OUT_OF_ROAD, 'x': current_x, 'y': current_y, 'reward': REWARD_GET_OFF_ROAD}
                self.envConnector.sendMessageToAgent(properties, reply)
            
            # Если дошёл до финиша
            finish_collision = self.ball.collides_with_list(self.flag_sprite_list)
            if finish_collision:
                # Коллизия имеется
                reset = True
                # Возвращаем мяч в начало
                self.reset_ball_position()
                # Отправляем сообщение 
                reply = {'reset': 1 , 'reset_cause': RESET_CAUSE_REACHED_FINISH, 'x': current_x, 'y': current_y, 'reward': REWARD_REACHED_FLAG}
                self.envConnector.sendMessageToAgent(properties, reply)

            # После этого отправляем сообщение агенту про следующие координаты, если не нужно перезапускать среду
            # Так же не забываем про вознаграждение для агента
            if not reset:
                # Вычисляем вознограждение
                reward = None

                if (dir == UP or dir == DOWN):
                    distance_prev_y = abs(previous_y - self.flag.center_y)
                    distance_cur_y = abs(current_y - self.flag.center_y)
                    if (distance_prev_y > distance_cur_y):
                        reward = REWARD_GET_CLOSER
                    if (distance_prev_y < distance_cur_y):
                        reward = REWARD_GET_FURTHER
                    if (distance_prev_y == distance_cur_y):
                        reward = 0

                if (dir == LEFT or dir == RIGHT):
                    distance_prev_x = abs(previous_x - self.flag.center_x)
                    distance_cur_x = abs(previous_x - self.flag.center_x)
                    if (distance_prev_x > distance_cur_x):
                        reward = REWARD_GET_CLOSER
                    if (distance_prev_x < distance_cur_x):
                        reward = REWARD_GET_FURTHER
                    if (distance_prev_x == distance_cur_x):
                        reward = 0

                # Отправляем сообщение
                reply = {'reset': 0, 'x': current_x, 'y': current_y, 'reward':reward}
                self.envConnector.sendMessageToAgent(properties, reply)


    def setup(self):
        """Настройка игры (вызывается после инициализации окна)"""
        self.envConnector = MLEnvConnector(RABBITMQ_HOST,  ENV_QUEUE)
        self.envConnector.connect()
        self.envConnector.startConsumingThread(self.messageCallback)

        # Создаём спрайт шара
        self.ball = arcade.SpriteCircle(BALL_RADIUS, BALL_COLOR)
        self.ball.center_x = BALL_START_X
        self.ball.center_y = BALL_START_Y
        self.ball_sprite_list.append(self.ball)

        self.road = arcade.SpriteSolidColor(ROAD_WIDTH, ROAD_HEIGHT,color= ROAD_COLOR)
        self.road.center_x = ROAD_X
        self.road.center_y = ROAD_Y
        self.road_sprite_list.append(self.road)

        # Создаем границы дороги
        self.create_borders()

        self.flag = arcade.Sprite(FLAG_IMAGE_PATH, FLAG_SKALE)  # Scale the image
        self.flag.center_x = self.road.center_x + ROAD_WIDTH / 2 - 25  # Размещаем флаг в конце дороги.
        self.flag.center_y = self.road.center_y
        self.flag_sprite_list.append(self.flag)

        arcade.schedule(self.process_messages, 0.05)  # Опрашиваем очередь RabbitMQ каждые 50мс

    def reset_ball_position(self):
        self.ball.center_x = BALL_START_X
        self.ball.center_y = BALL_START_Y

    def create_borders(self):
        """Создаёт границы дороги."""
        # Левая граница
        border_left = arcade.SpriteSolidColor(BORDER_WIDTH, ROAD_HEIGHT, color = arcade.color.RED)
        border_left.center_x = self.road.center_x - ROAD_WIDTH / 2 - BORDER_WIDTH / 2
        border_left.center_y = self.road.center_y
        self.borders_sprite_list.append(border_left)

        # Правая граница
        border_right = arcade.SpriteSolidColor(BORDER_WIDTH, ROAD_HEIGHT, color = arcade.color.RED)
        border_right.center_x = self.road.center_x + ROAD_WIDTH / 2 + BORDER_WIDTH / 2
        border_right.center_y = self.road.center_y
        self.borders_sprite_list.append(border_right)

        # Верхняя граница
        border_top = arcade.SpriteSolidColor(ROAD_WIDTH, BORDER_WIDTH, color = arcade.color.RED)
        border_top.center_x = self.road.center_x
        border_top.center_y = self.road.center_y + ROAD_HEIGHT / 2 + BORDER_WIDTH / 2
        self.borders_sprite_list.append(border_top)

        # Нижняя граница
        border_bottom = arcade.SpriteSolidColor(ROAD_WIDTH, BORDER_WIDTH, color = arcade.color.RED)
        border_bottom.center_x = self.road.center_x
        border_bottom.center_y = self.road.center_y - ROAD_HEIGHT / 2 - BORDER_WIDTH / 2
        self.borders_sprite_list.append(border_bottom)

    def process_messages(self, delta_time):
        """Обрабатывает сообщения из очереди."""
        while self.direction_queue:
            direction = self.direction_queue.pop(0)
            self.move_ball(direction)

    def on_draw(self):
        """Вызывается для отрисовки сцены."""
        self.clear()
        self.road_sprite_list.draw()
        self.ball_sprite_list.draw()  # Рисуем шар
        self.borders_sprite_list.draw()
        self.flag_sprite_list.draw()
        #arcade.draw_rect_filled(arcade.rect.XYWH(self.road.center_x, self.road.center_y, self.road.width, self.road.height), ROAD_COLOR)
        #arcade.draw_circle_filled(self.ball_x, self.ball_y, BALL_RADIUS, BALL_COLOR)

    def move_ball(self, direction):
        """Перемещает шар в заданном направлении."""
        if direction == UP:
            self.ball.center_y += BALL_SPEED
        elif direction == DOWN:
            self.ball.center_y -= BALL_SPEED
        elif direction == LEFT:
            self.ball.center_x -= BALL_SPEED
        elif direction == RIGHT:
            self.ball.center_x += BALL_SPEED

        # Ограничение шара в пределах окна
        self.ball.center_x = max(BALL_RADIUS, min(self.ball.center_x, WIDTH - BALL_RADIUS))
        self.ball.center_y = max(BALL_RADIUS, min(self.ball.center_y, HEIGHT - BALL_RADIUS))

    def update(self, delta_time):
        """Вызывается для обновления логики игры (не используется в данном случае)."""
        pass

def main():
    game = MyGame(WIDTH, HEIGHT, TITLE)
    game.setup()  # Вызываем setup после создания экземпляра игры
    arcade.run()


if __name__ == "__main__":
    main()