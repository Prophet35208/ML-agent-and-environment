from 
import time
import sys
import json

# Настройки RabbitMQ
RABBITMQ_HOST = 'localhost'
AGENT_QUEUE = 'direction_queue'
ENV_REPLY_QUEUE = 'ball_position_queue'

# Кодировка направлений
UP = 0
RIGHT = 1
DOWN = 2
LEFT = 3

def Q(x, y):
    """Статическая Q-функция: всегда возвращает "вправо"."""
    return RIGHT

# Функция для получения ввода пользователя 
def get_user_input():
    """Получает ввод пользователя из консоли."""
    while True:
        command = input("Press Enter to start round, or 'exit' to quit: ").lower()
        if command == "":
            return True  # Enter pressed
        elif command == "exit":
            return False  # Exit command
        else:
            print("Invalid command.")

# Создаем экземпляр коннектора
agent_connector = Connectors.MLAgentConnector(RABBITMQ_HOST, AGENT_QUEUE, ENV_REPLY_QUEUE)
agent_connector.connect()


                

def runEpisode():
    agent_connector.sendStart()

    while self.response is None:
            self.connection.process_data_events(time_limit=None)
    

def main():
    """Главная функция, управляющая началом раундов."""
    while True:
        start_round = get_user_input()
        if start_round is None:  # Exit command
            break
        if start_round:
            if not runEpisode():
                break 
        else:
            break  

    # Закрываем соединение в конце
    agent_connector.close()
    print("Agent: Connection closed")
    sys.exit()

if __name__ == "__main__":
    main()