import arcade
import math
import pika
import sys

# --- Константы ---
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
SCREEN_TITLE = "Simple Road"  #  Обновили заголовок
ROAD_COLOR = arcade.color.RED
ROAD_WIDTH = 100
BALL_SCALE = 0.1 
BALL_SPEED = 3

BALL_TEXTURE_PATH = "Environment/Images/ball.png"  


class BallSprite(arcade.Sprite):
    def __init__(self, scale, x, y, texture_path=BALL_TEXTURE_PATH):  # Укажите путь к текстуре
        super().__init__(texture_path,scale=scale,center_x=x, center_y=y)
        self.angle = 0
        self.speed = 0
        self.angle_change = 0 # Добавили атрибут

        self.upPressed = False
        self.downPressed = False
        self.leftPressed = False
        self.rightPressed = False

    def draw(self):
        # Используем метод draw, чтобы нарисовать спрайт
        arcade.draw_sprite(self)

    def update(self):
        self.calculateVelocity()
        self.center_y += self.speed * math.cos(math.radians(self.angle))
        self.center_x += self.speed * math.sin(math.radians(self.angle))
        self.angle += self.angle_change # Обновляем угол

    def calculateVelocity(self):
        self.speed = 0
        self.angle_change = 0
        if (self.upPressed):
            if (self.downPressed):
                pass
            else:
                self.speed = CAR_SPEED
        
        if (self.downPressed):
            if(self.upPressed):
                pass
            else:
                self.speed = -CAR_SPEED

        if (self.rightPressed):
            if(self.leftPressed):
                pass
            else:
                self.angle_change = BALL_TURN_SPEED

        if (self.leftPressed):
            if(self.rightPressed):
                pass
            else:
                self.angle_change = -BALL_TURN_SPEED

    def is_off_road(self, road_segments):
        # Проверяем, находится ли машинка вне дороги
        ball_rect = self.get_rect() # Получаем прямоугольник машинки

        for segment in road_segments:
            # Проверяем, пересекает ли прямоугольник машинки сегмент дороги
            if arcade.has_intersect(ball_rect, segment.get_rect()):
                return False  # Машинка на дороге
        return True  # Машинка вне дороги


class RoadSegment(arcade.Sprite):
    def __init__(self, centerX, centerY, height, color=ROAD_COLOR, width=ROAD_WIDTH):
        super().__init__(center_x=centerX, center_y=centerY)
        self.width = width
        self.height = height
        self.color= ROAD_COLOR





# --- Класс Game ---
class Game(arcade.Window):
    def __init__(self, width, height, title):
        super().__init__(width, height, title)
        arcade.set_background_color(arcade.color.WHITE)
        self.car_sprite = None
        self.road_segments = arcade.SpriteList()

        # Инициируем RabbitMq
        #
        self.timer = 0
        connection = pika.BlockingConnection(
        pika.ConnectionParameters(host='localhost'))
        self.channel = connection.channel()
        # Определяем эксчэндж, по которому будем передавать сообщения
        self.channel.exchange_declare(exchange='logs', exchange_type='fanout')   

    def setup(self):
        # Инициализация игры
        self.car_sprite = BallSprite(CAR_SCALE,SCREEN_WIDTH/2,100) 
        self.create_road()

    def create_road(self):
        # Создаем прямую дорогу
        start_x = 588
        start_y = SCREEN_HEIGHT // 2
        end_x = SCREEN_WIDTH
        end_y = SCREEN_HEIGHT // 2
        segment = RoadSegment(start_x, start_y, end_x, end_y)
        segment.color = arcade.color.BABY_BLUE
        segment2 = RoadSegment(50, 50, 20)
        self.road_segments.append(segment)
        self.road_segments.append(segment2)

    def on_draw(self):
        arcade.Window.clear(self)
        self.road_segments.draw()
        self.car_sprite.draw()

    def on_update(self, delta_time):
        # Обновление состояния игры
        self.car_sprite.update()

        # Пробуем передать текущие координаты машинки
        self.timer = self.timer + 1
        if (self.timer == 20):
            X = self.car_sprite.center_x
            Y = self.car_sprite.center_y    
            message = str(X) + "  " + str(Y)
            self.channel.basic_publish(exchange='logs', routing_key='', body=message)
            self.timer = 0


    def on_key_press(self, key, modifiers):
    # Обработка нажатий клавиш
        if key == arcade.key.UP or key == arcade.key.W:
            self.car_sprite.upPressed = True
        elif key == arcade.key.DOWN or key == arcade.key.S:
            self.car_sprite.downPressed = True
        elif key == arcade.key.LEFT or key == arcade.key.A:
            self.car_sprite.leftPressed = True
        elif key == arcade.key.RIGHT or key == arcade.key.D:
            self.car_sprite.rightPressed = True


    def on_key_release(self, key, modifiers):
        # Обработка отпускания клавиш
        if key == arcade.key.UP or key == arcade.key.W:
            self.car_sprite.upPressed = False
        elif key == arcade.key.DOWN or key == arcade.key.S:
            self.car_sprite.downPressed = False
        elif key == arcade.key.LEFT or key == arcade.key.A:
            self.car_sprite.leftPressed = False
        elif key == arcade.key.RIGHT or key == arcade.key.D:
            self.car_sprite.rightPressed = False

        
def main():
    game = Game(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
    game.setup()
    arcade.run()

if __name__ == "__main__":
    main()