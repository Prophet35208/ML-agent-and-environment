from LibForRabbitMQ.Connectors import MLAgentConnector
import time
import sys
import os
import json
import numpy as np
from collections import defaultdict
import random
from tqdm import tqdm
import signal
import ast
import re

TIME_BETWEEN_STEPS = 0.0
N_EPISODES = 100_000
START_EPSILON = 1.0
LEARNING_RATE = 0.01


# Настройки RabbitMQ
RABBITMQ_HOST = 'localhost'
ENV_QUEUE = 'env_eueue'

# Кодировка направлений
UP = 0
RIGHT = 1
DOWN = 2
LEFT = 3

# Кодировка действий в меню
START = 1
LOAD_Q_VALUES = 2
SAVE_Q_VALUES = 3
RELOAD_TIME_DELTA = 4
EXIT = 5

directions = [UP, RIGHT, DOWN, LEFT]
exit_flag = False

# Причины перезапуска (ресетов)
RESET_CAUSE_OUT_OF_ROAD = 1
RESET_CAUSE_REACHED_FINISH = 2

def signal_handler(sig, frame):
    """Обработчик сигнала для Ctrl+C."""
    global exit_flag
    print("\nПолучен сигнал Ctrl-C. Завершение обучения...")
    exit_flag = True

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


# Функция для получения ввода пользователя 
def print_menu_and_get_input():
    while True:
        command = input("\nПрограмма агента запущена. " \
        "Выберите действие\n\t" \
        "1. Начать тренировку\n\t" \
        "2. Загрузить Q-значения и eps из файла\n\t" \
        "3. Сохранить Q-значения и eps в файл\n\t" \
        "4. Загрузить интервал между сообщениями из файла\n\t" \
        "5. Завершить работу и выйти\nВвод: ").lower()
        if command == "1":
            return START  
        elif command == "2":
            return LOAD_Q_VALUES 
        elif command == "3":
            return SAVE_Q_VALUES
        elif command == "4":
            return RELOAD_TIME_DELTA
        elif command == "5":
            return EXIT
        else:
            return -1


# Создаем экземпляр коннектора
agent_connector = MLAgentConnector(RABBITMQ_HOST, ENV_QUEUE)
agent_connector.connect()

def run_q_agent(agent, n_episodes,time_betw_steps):
    global exit_flag
    exit_flag = False
    signal.signal(signal.SIGINT, signal_handler)
    show_progress = 1

    pbar = tqdm(range(n_episodes))

    for episode in pbar:

        if exit_flag:
            print("\nПрерывание обучения на этапе: ", episode)
            break  

        get_message = agent_connector.send_start_and_wait_reply()
        time.sleep(time_betw_steps)
        if (get_message == -1):
            break
        cur_x = int(agent_connector.last_message['x'])
        cur_y = int(agent_connector.last_message['y'])   
        obs = (cur_x,cur_y)

        done = False

        # play one episode
        step = 0
        while not done:

            if exit_flag:
                break  

            action = agent.get_action(obs)

            f = agent_connector.send_step_and_wait_reply(action, episode + 1, step + 1)
            time.sleep(time_betw_steps)
            if (f):
                return -1
            message = agent_connector.last_message
            next_obs = (message['x'],message['y'])
            reward = message['reward']
            reset = message['reset']

            # Обновляем агента
            agent.update(obs, action, reward, reset, next_obs)

            done = reset
            obs = next_obs
            step = step + 1

        agent.decay_epsilon()
    return 0

def load_q_values(filename):
  """
  Загружает массив Q-значений из файла в текущей директории.
  Спрашивает у пользователя имя файла.  Если файл не найден, сообщает об этом
  и возвращает None.  Загружает из файла Q-значения, предполагая, что они
  сохранены в формате, созданном функцией `save_q_values`.
  Args:
    directions: Список возможных действий (например, ['1', '2', '3', '4']).
                Используется для определения длины массива нулей для defaultdict.

  Returns:
    defaultdict: Объект defaultdict, содержащий Q-значения, или None, если файл не найден.
  """
  filepath = os.path.join(os.getcwd(), filename)  
  q_values = defaultdict(lambda: np.zeros(len(directions)))

  try:
        with open(filename, 'r', encoding='utf-8') as f:
            q_values_serializable = json.load(f)

        # Преобразуем ключи обратно в кортежи
        for k_str, v_list in q_values_serializable.items():
            try:
                # Используем ast.literal_eval() для безопасного преобразования
                key = ast.literal_eval(k_str)  # Преобразовываем строковый ключ обратно в кортеж
            except (SyntaxError, ValueError):
                print(f"Не удалось преобразовать ключ {k_str} в кортеж. Возможно, это не кортеж.")
                continue  # Пропускаем этот ключ, если не удалось преобразовать

            # 3. Преобразуем значения обратно в numpy массивы
            q_values[key] = np.array(v_list)

        print(f"Q-значения успешно загружены из файла: {filename}")
  except FileNotFoundError:
        print(f"Файл {filename} не найден.") # Возвращаем пустой словарь, если файла нет.
  except Exception as e:
        print(f"Ошибка при загрузке Q-значений из файла: {e}")
        import traceback
        traceback.print_exc()

  return q_values # Возвращаем q_values
  
def save_q_values(q_values, filename):
  """
  Сохраняет массив Q-значений в файл.

  Args:
    q_values: defaultdict(lambda: np.zeros(len(directions))):  Словарь Q-значений для сохранения.
    filename: str:  Имя файла, в который следует сохранить Q-значения.  Если файл
                     уже существует, он будет перезаписан.
  """
  try:
    q_values_serializable = {
            str(k): v.tolist() for k, v in q_values.items()
        }
    
    filepath = os.path.join(os.getcwd(), filename)
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(q_values_serializable, f, indent=4)
    print(f"Q-значения успешно сохранены в файл: {filename}")
  except Exception as e:
    print(f"Ошибка при сохранении Q-значений в файл: {e}")

def save_epsilon(epsilon, filename="epsilon.txt"):
    """Сохраняет значение epsilon в файл в формате plain text."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(str(epsilon))
        print(f"Epsilon успешно сохранено в файл: {filename}")
    except Exception as e:
        print(f"Ошибка при сохранении epsilon в файл: {e}")
        import traceback
        traceback.print_exc()

def load_epsilon(filename="epsilon.txt", default_epsilon=1.0):
    """Загружает значение epsilon из файла в формате plain text.
       Если файл не найден, возвращает значение по умолчанию.
    """
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            epsilon_str = f.read()
            epsilon = float(epsilon_str)  # Преобразуем строку в float
        print(f"Epsilon успешно загружено из файла: {filename}")
        return epsilon
    except FileNotFoundError:
        print(f"Файл {filename} не найден. Возвращается значение epsilon по умолчанию: {default_epsilon}")
        return default_epsilon
    except ValueError:
        print(f"Ошибка при преобразовании значения epsilon в float.  Возвращается значение epsilon по умолчанию: {default_epsilon}")
        return default_epsilon  #  Возвращаем default, если файл содержит не число
    except Exception as e:
        print(f"Ошибка при загрузке epsilon из файла: {e}")
        import traceback
        traceback.print_exc()
        return default_epsilon
    
# Загружаем параметры из файла
def load_params(filename="params.txt"):
    default_params = {
        "learning_rate": LEARNING_RATE,
        "n_episodes": N_EPISODES,
        "start_epsilon": START_EPSILON,
        "time_betw_steps": TIME_BETWEEN_STEPS
    }

    loaded_parameters = default_params.copy()

    try:
        with open(filename, "r") as f:
            for line in f:
                match = re.match(r"(\w+)\s*=\s*([^\s]+)", line)

                if match:
                    param_name = match.group(1)
                    param_value = match.group(2)

                    if param_name in loaded_parameters:
                        try:
                            # Преобразование типов
                            default_value = loaded_parameters[param_name]
                            if isinstance(default_value, int):
                                loaded_parameters[param_name] = int(param_value)
                            elif isinstance(default_value, float):
                                loaded_parameters[param_name] = float(param_value)
                            else:
                                loaded_parameters[param_name] = param_value 

                        except ValueError:
                            print(f"Ошибка: Не удалось преобразовать значение '{param_value}' для параметра '{param_name}'.")
                            # Оставляем значение по умолчанию

                    else:
                        print(f"Предупреждение: Неизвестный параметр '{param_name}' в файле.")

        return loaded_parameters

    except FileNotFoundError:
        print(f"Ошибка: Файл '{filename}' не найден.")
        return default_params
    except Exception as e:
        print(f"Ошибка при чтении файла: {e}")
        return default_params

def get_time_delta():
    parameters = load_params()

    return parameters["time_betw_steps"]
    



def main():

    # Параметры агента
    parameters = load_params()

    learning_rate = parameters["learning_rate"]
    n_episodes = parameters["n_episodes"]
    start_epsilon = parameters["start_epsilon"]
    time_betw_steps = parameters["time_betw_steps"]

    epsilon_decay = start_epsilon / (n_episodes / 2)  # Уменьшаем упор на исследование
    final_epsilon = 0.1

    

    agent = Agent(
    learning_rate=learning_rate,
    initial_epsilon=start_epsilon,
    epsilon_decay=epsilon_decay,
    final_epsilon=final_epsilon,
)

    """ Интерфейс."""
    while True:
        command = print_menu_and_get_input()
        if command == START:
            agent_connector.setup_logs()
            run_q_agent(agent, n_episodes,time_betw_steps)
        if command == LOAD_Q_VALUES:
            agent.q_values = load_q_values("q_values.txt")
            agent.epsilon = load_epsilon()
        if (command == SAVE_Q_VALUES):
            save_q_values(agent.q_values, "q_values.txt")
            save_epsilon(agent.epsilon)
        if (command == RELOAD_TIME_DELTA):
            time_betw_steps = get_time_delta()
            print(f"Текущее значение промежутка - {time_betw_steps} секунд")
        if (command == EXIT):
            break


    # Закрываем соединение в конце
    agent_connector.close()
    print("Завершение работы\n")
    sys.exit()

if __name__ == "__main__":
    main()