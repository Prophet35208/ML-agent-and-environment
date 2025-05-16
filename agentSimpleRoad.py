from LibForRabbitMQ.Connectors import MLAgentConnector
import time
import sys
import json

# Настройки RabbitMQ
RABBITMQ_HOST = 'localhost'
ENV_QUEUE = 'env_eueue'

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
agent_connector = MLAgentConnector(RABBITMQ_HOST, ENV_QUEUE)
agent_connector.connect()


                

def runEpisode():
    agent_connector.send_start_and_wait_reply()

    cur_x = int(agent_connector.last_message['x'])
    cur_y = int(agent_connector.last_message['y'])
    direction = Q(cur_x, cur_y)
    agent_connector.send_step_and_wait_reply(direction)

    while (True):
        cur_x = int(agent_connector.last_message['x'])
        cur_y = int(agent_connector.last_message['y'])
        direction = Q(cur_x, cur_y)
        agent_connector.send_step_and_wait_reply(direction)



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