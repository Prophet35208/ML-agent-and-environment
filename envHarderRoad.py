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
TITLE = "HarderRoadEnv"
BACKGROUND_COLOR = arcade.color.WHITE
BALL_RADIUS = 20
BALL_COLOR = arcade.color.AMERICAN_ROSE
BALL_SPEED = 10  # Скорость движения шара



# Дорога 
ROAD_HEIGHT = 70

CENTER_ROAD_HEIGHT = 400
CENTER_ROAD_X = WIDTH // 2 -13
CENTER_ROAD_Y = HEIGHT // 2


UP_ROAD_WIDTH = WIDTH // 2.25
UP_ROAD_X = WIDTH - WIDTH // 4 - 20
UP_ROAD_Y = HEIGHT- HEIGHT// 4 + 15

ROAD_X = WIDTH // 2  # Центр дороги по X
ROAD_Y = HEIGHT // 2  # Центр дороги по Y

ROAD_START_X = 20
ROAD_START_Y = 50

ROAD_COLOR = arcade.color.GRAY

# Начальная позиция шара
BALL_START_X = WIDTH // 10
BALL_START_Y = 90

# Настройки границ дороги
BORDER_WIDTH = 5

# Флаг
FLAG_IMAGE_PATH = "Environment/Images/flag.png"
FLAG_SKALE = 0.1

# Причины перезапуска (ресетов)
RESET_CAUSE_OUT_OF_ROAD = 1
RESET_CAUSE_REACHED_FINISH = 2

# Настройки вознаграждений
REWARD_GET_CLOSER = 1
REWARD_GET_FURTHER = -1
REWARD_GET_OFF_ROAD = -10
REWARD_REACHED_FLAG = 10

# Контрольные точки для расчёта вознограждения на сложной карте
CONTROL_POINT_X = CENTER_ROAD_X - ROAD_HEIGHT/2 + 2
CONTROL_POINT_Y = UP_ROAD_Y - ROAD_HEIGHT/2

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

        self.road_segment_width = self.width // 2  # Ширина первого сегмента дороги
        self.road_segment_height = self.height // 2 # Высота второго сегмента дороги
        self.road_start_x = BORDER_WIDTH + ROAD_START_X  # Начальная точка X дороги, отступ слева
        self.road_start_y = BORDER_WIDTH + ROAD_START_Y # Начальная точка Y дороги, отступ снизу
        self.road_end_y = self.height - 30 # Конечная точка по оси Y

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
                print("\nМяч дошёл до флага.\n")

            # После этого отправляем сообщение агенту про следующие координаты, если не нужно перезапускать среду
            # Так же не забываем про вознаграждение для агента
            if not reset:
                # Вычисляем вознограждение
                reward = None

                if (previous_x < CONTROL_POINT_X):
                    if (dir == UP or dir == DOWN):
                        reward = 0
                    if (dir == LEFT):
                        reward = REWARD_GET_FURTHER
                    if (dir == RIGHT):
                        reward = REWARD_GET_CLOSER

                if (previous_x > CONTROL_POINT_X and previous_y < CONTROL_POINT_Y):
                    if (dir == LEFT or dir == RIGHT):
                        reward = 0
                    if (dir == UP):
                        reward = REWARD_GET_CLOSER
                    if (dir == DOWN):
                        reward = REWARD_GET_FURTHER

                if (previous_y >= CONTROL_POINT_Y):
                    if (dir == UP or dir == DOWN):
                        reward = 0
                    if (dir == LEFT):
                        reward = REWARD_GET_FURTHER
                    if (dir == RIGHT):
                        reward = REWARD_GET_CLOSER
                    
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


        # Создаем границы дороги
        self.create_borders()
        self.create_road()

        self.flag = arcade.Sprite(FLAG_IMAGE_PATH, FLAG_SKALE)  # Scale the image
        self.flag.center_x = UP_ROAD_X + UP_ROAD_WIDTH / 2 - 25 # Размещаем флаг в конце дороги. Используем UP_ROAD_X и UP_ROAD_WIDTH
        self.flag.center_y = UP_ROAD_Y
        self.flag_sprite_list.append(self.flag)

        arcade.schedule(self.process_messages, 0.05)  # Опрашиваем очередь RabbitMQ каждые 50мс

    def reset_ball_position(self):
        self.ball.center_x = BALL_START_X
        self.ball.center_y = BALL_START_Y

    def create_borders(self):
        """Создаёт границы дороги."""
         # Границы первого сегмента (horizontal)
        border_left1 = arcade.SpriteSolidColor(BORDER_WIDTH, ROAD_HEIGHT, color = arcade.color.RED)
        border_left1.center_x = ROAD_START_X - BORDER_WIDTH / 2 + 4
        border_left1.center_y = ROAD_START_Y + ROAD_HEIGHT / 2 + 5
        self.borders_sprite_list.append(border_left1)

        border_bottom1 = arcade.SpriteSolidColor(self.road_segment_width - 2, BORDER_WIDTH, color = arcade.color.RED)
        border_bottom1.center_x = ROAD_START_X + self.road_segment_width / 2 + 3
        border_bottom1.center_y = ROAD_START_Y - BORDER_WIDTH / 2 + 5
        self.borders_sprite_list.append(border_bottom1)

        border_top1 = arcade.SpriteSolidColor(self.road_segment_width - ROAD_HEIGHT, BORDER_WIDTH, color = arcade.color.RED)
        border_top1.center_x = ROAD_START_X + self.road_segment_width / 2 - 33
        border_top1.center_y = ROAD_START_Y + ROAD_HEIGHT + BORDER_WIDTH / 2 +5
        self.borders_sprite_list.append(border_top1)

        # Границы второго сегмента (vertical)
        border_left2 = arcade.SpriteSolidColor(BORDER_WIDTH, CENTER_ROAD_HEIGHT - 30, color = arcade.color.RED)
        border_left2.center_x = CENTER_ROAD_X - ROAD_HEIGHT / 2 - BORDER_WIDTH / 2  # Center road x это центр дороги, road_height это ширина границы
        border_left2.center_y = CENTER_ROAD_Y + 15
        self.borders_sprite_list.append(border_left2)

        border_right2 = arcade.SpriteSolidColor(BORDER_WIDTH, CENTER_ROAD_HEIGHT- 20, color = arcade.color.RED)
        border_right2.center_x = CENTER_ROAD_X + ROAD_HEIGHT / 2 + BORDER_WIDTH / 2  # Center road x это центр дороги, road_height это ширина границы
        border_right2.center_y = CENTER_ROAD_Y - ROAD_HEIGHT + 10
        self.borders_sprite_list.append(border_right2)

        # Границы третьего сегмента (horizontal, top)
        border_top3 = arcade.SpriteSolidColor(UP_ROAD_WIDTH + ROAD_HEIGHT - 10, BORDER_WIDTH, color = arcade.color.RED)
        border_top3.center_x = UP_ROAD_X - 30
        border_top3.center_y = UP_ROAD_Y + ROAD_HEIGHT / 2 + BORDER_WIDTH / 2
        self.borders_sprite_list.append(border_top3)

        border_bottom3 = arcade.SpriteSolidColor(UP_ROAD_WIDTH - 19, BORDER_WIDTH, color = arcade.color.RED)
        border_bottom3.center_x = UP_ROAD_X + 10
        border_bottom3.center_y = UP_ROAD_Y - ROAD_HEIGHT / 2 - BORDER_WIDTH / 2
        self.borders_sprite_list.append(border_bottom3)

        border_right3 = arcade.SpriteSolidColor(BORDER_WIDTH, ROAD_HEIGHT, color = arcade.color.RED)
        border_right3.center_x = UP_ROAD_X + UP_ROAD_WIDTH / 2 + BORDER_WIDTH / 2 # Добавил ширину
        border_right3.center_y = UP_ROAD_Y
        self.borders_sprite_list.append(border_right3)

    def create_road(self):
        # Первый сегмент: слева внизу -> вправо
        road_segment1 = arcade.SpriteSolidColor(
            self.road_segment_width,  
            ROAD_HEIGHT,
            color=ROAD_COLOR
        )
        road_segment1.center_x = self.road_start_x + (self.road_segment_width - BORDER_WIDTH) // 2
        road_segment1.center_y = self.road_start_y + ROAD_HEIGHT // 2
        self.road_sprite_list.append(road_segment1)

        # Второй сегмент: вверх
        road_segment2 = arcade.SpriteSolidColor(
            ROAD_HEIGHT,
            CENTER_ROAD_HEIGHT,
            color=ROAD_COLOR
        )
        road_segment2.center_x = CENTER_ROAD_X
        road_segment2.center_y = CENTER_ROAD_Y
        self.road_sprite_list.append(road_segment2)

        # Третий сегмент: вправо
        road_segment3 = arcade.SpriteSolidColor(
            UP_ROAD_WIDTH,  # Учитываем границы и отступ справа
            ROAD_HEIGHT,
            color=ROAD_COLOR
        )
        road_segment3.center_x = UP_ROAD_X
        road_segment3.center_y = UP_ROAD_Y
        self.road_sprite_list.append(road_segment3)


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
        #arcade.draw_point(CENTER_ROAD_X - ROAD_HEIGHT/2 + 10,UP_ROAD_Y - ROAD_HEIGHT/2,(0, 255, 0),10)

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

    def on_key_press(self, key, modifiers):
        """Вызывается при нажатии клавиши."""
        if key == arcade.key.ESCAPE:
            # Возвращаем мяч на начальную позицию
            self.ball.center_x = BALL_START_X
            self.ball.center_y = BALL_START_Y

def main():
    game = MyGame(WIDTH, HEIGHT, TITLE)
    game.setup()  # Вызываем setup после создания экземпляра игры
    arcade.run()


if __name__ == "__main__":
    main()