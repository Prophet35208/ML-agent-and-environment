from LibForRabbitMQ.Connectors import MLAgentConnector
import time
import sys
import json
import numpy as np
from collections import defaultdict
import random
from tqdm import tqdm

TIME_BETWEEN_STEPS = 0

# Настройки RabbitMQ
RABBITMQ_HOST = 'localhost'
ENV_QUEUE = 'env_eueue'

# Кодировка направлений
UP = 0
RIGHT = 1
DOWN = 2
LEFT = 3

directions = [UP, RIGHT, DOWN, LEFT]

# Причины перезапуска (ресетов)
RESET_CAUSE_OUT_OF_ROAD = 1
RESET_CAUSE_REACHED_FINISH = 2


class Agent:
    def __init__(
        self,
        learning_rate: float,
        initial_epsilon: float,
        epsilon_decay: float,
        final_epsilon: float,
        discount_factor: float = 0.95,
    ):
        """Initialize a Reinforcement Learning agent with an empty dictionary
        of state-action values (q_values), a learning rate and an epsilon.

        Args:
            learning_rate: The learning rate
            initial_epsilon: The initial epsilon value
            epsilon_decay: The decay for epsilon
            final_epsilon: The final epsilon value
            discount_factor: The discount factor for computing the Q-value
        """
        self.q_values = defaultdict(lambda: np.zeros(len(directions)))

        self.lr = learning_rate
        self.discount_factor = discount_factor

        self.epsilon = initial_epsilon
        self.epsilon_decay = epsilon_decay
        self.final_epsilon = final_epsilon

        self.training_error = []

    # Возвращает действие с вероятностью (1 - epsilon), исходя из текущих наблюдений (координат x,y).
    #  Иначе осуществляет случайное для того, чтобы лучше понять обстановку (сделать выводы из случайного шага и награды, которую он принёс)
    def get_action(self, obs: tuple[int, int]) -> int:
        """
        Returns the best action with probability (1 - epsilon)
        otherwise a random action with probability epsilon to ensure exploration.
        """
        # 
        if np.random.random() < self.epsilon:
            return random.choice(directions)

        # with probability (1 - epsilon) act greedily (exploit)
        else:
            return int(np.argmax(self.q_values[obs]))

    
    def update(
        self,
        obs: tuple[int, int],
        action: int,
        reward: float,
        reset: bool,
        next_obs: tuple[int, int],
    ):
        """Updates the Q-value of an action."""
        future_q_value = (not reset) * np.max(self.q_values[next_obs])
        temporal_difference = (
            reward + self.discount_factor * future_q_value - self.q_values[obs][action]
        )

        self.q_values[obs][action] = (
            self.q_values[obs][action] + self.lr * temporal_difference
        )
        self.training_error.append(temporal_difference)

    def decay_epsilon(self):
        self.epsilon = max(self.final_epsilon, self.epsilon - self.epsilon_decay)


def artificial_q(x, y):
    """Статическая Q-функция: всегда возвращает "вправо"."""
    return UP

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

def runQFunct():
    agent_connector.send_start_and_wait_reply()
    time.sleep(TIME_BETWEEN_STEPS)

    cur_x = int(agent_connector.last_message['x'])
    cur_y = int(agent_connector.last_message['y'])
    direction = artificial_q(cur_x, cur_y)
    agent_connector.send_step_and_wait_reply(direction)
    time.sleep(TIME_BETWEEN_STEPS)

    # Продолжаем совершать шаги, пока не получим сообщение о reset 
    while (True):
        time.sleep(TIME_BETWEEN_STEPS)
        cur_x = int(agent_connector.last_message['x'])
        cur_y = int(agent_connector.last_message['y'])
        direction = artificial_q(cur_x, cur_y)
        agent_connector.send_step_and_wait_reply(direction)
        
        reply = agent_connector.last_message
        reset = int(reply['reset'])
        if reset:
            cause = reply['reset_cause']
            if cause == RESET_CAUSE_OUT_OF_ROAD:
                print ("Агент вылетел с дороги. Среда перезапущена, выполнение Q - функции завершено")
            if cause == RESET_CAUSE_REACHED_FINISH:
                print ("Агент дошёл до финиша. Среда перезапущена, выполнение Q - функции завершено ")
            break

def run_q_agent():
    # hyperparameters
    learning_rate = 0.01
    n_episodes = 100_000
    start_epsilon = 1.0
    epsilon_decay = start_epsilon / (n_episodes / 2)  # reduce the exploration over time
    final_epsilon = 0.1

    agent = Agent(
    learning_rate=learning_rate,
    initial_epsilon=start_epsilon,
    epsilon_decay=epsilon_decay,
    final_epsilon=final_epsilon,
)
    
    for episode in tqdm(range(n_episodes)):
        agent_connector.send_start_and_wait_reply()
        time.sleep(TIME_BETWEEN_STEPS)
        cur_x = int(agent_connector.last_message['x'])
        cur_y = int(agent_connector.last_message['y'])   
        obs = (cur_x,cur_y)

        done = False

        # play one episode
        while not done:
            action = agent.get_action(obs)

            agent_connector.send_step_and_wait_reply(action)
            message = agent_connector.last_message
            next_obs = (message['x'],message['y'])
            reward = message['reward']
            reset = message['reset']

            if reward == 10:
                print("Сюдыыы. Я у флага\n")

            # update the agent
            agent.update(obs, action, reward, reset, next_obs)

            # update if the environment is done and the current obs
            done = reset
            obs = next_obs

        agent.decay_epsilon()


def main():
    """Главная функция, управляющая началом раундов."""
    while True:
        start_round = get_user_input()
        if start_round is None:  # Exit command
            break
        if (start_round == 1):
            #runQFunct()
            run_q_agent()
        else:

            break  

    # Закрываем соединение в конце
    agent_connector.close()
    print("Agent: Connection closed")
    sys.exit()

if __name__ == "__main__":
    main()