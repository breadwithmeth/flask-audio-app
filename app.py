from flask import Flask, render_template, Response, request
import pyaudio
import wave
import threading
import time
import queue
import os
from datetime import datetime
import sys
import signal

app = Flask(__name__)

# --- Конфигурация аудио ---
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
CHUNK = 1024
RECORD_SECONDS_PER_FILE = 3600 # 1 час
RECORDINGS_DIR = "recordings"

INPUT_DEVICE_INDEX = 2

# --- Глобальные переменные ---
# Используем одну очередь для сохранения и список очередей для стриминга
save_queue = queue.Queue()
stream_listeners = []
listeners_lock = threading.Lock()
recording_active = threading.Event() # Используем для сигнала остановки
p = None
stream = None
audio_saver_thread = None
recording_thread = None
shutdown_event = threading.Event() # Для координации завершения

# --- Функции ---

def list_audio_devices():
    """Выводит список доступных аудиоустройств ввода."""
    print("Поиск аудиоустройств...")
    p_temp = None
    device_name = "Не найдено или ошибка"
    is_valid_index = False
    try:
        p_temp = pyaudio.PyAudio()
        info = p_temp.get_host_api_info_by_index(0)
        numdevices = info.get('deviceCount')
        print("-------------------------------------------")
        print("Доступные устройства ввода (микрофоны):")
        found_input = False
        for i in range(0, numdevices):
            device_info = p_temp.get_device_info_by_host_api_device_index(0, i)
            if (device_info.get('maxInputChannels')) > 0:
                print(f"  [Индекс {i}] {device_info.get('name')} (Каналов: {device_info.get('maxInputChannels')})")
                found_input = True
                if i == INPUT_DEVICE_INDEX:
                    is_valid_index = True
                    device_name = f"[{i}] {device_info.get('name')}"
        if not found_input:
            print("  Не найдено устройств ввода.")
        print("-------------------------------------------")
        if INPUT_DEVICE_INDEX is None:
             print("!!! INPUT_DEVICE_INDEX не установлен. Запись не начнется.")
        elif not is_valid_index:
             print(f"!!! Выбран неверный индекс устройства: {INPUT_DEVICE_INDEX}. Запись не начнется.")
        else:
             print(f"* Выбрано устройство: {device_name}")
        print("-------------------------------------------")
        return is_valid_index, device_name
    except Exception as e:
        print(f"Ошибка при получении списка устройств: {e}")
        return False, f"Ошибка получения списка: {e}"
    finally:
        if p_temp:
            p_temp.terminate()


def record_audio_task():
    """Читает аудио с микрофона, кладет в очередь сохранения и раздает слушателям стрима."""
    global p, stream, recording_active

    if INPUT_DEVICE_INDEX is None or not recording_active.is_set():
        print("record_audio_task: Запись неактивна или устройство не выбрано.")
        return # Не начинаем запись

    try:
        p = pyaudio.PyAudio()
        try:
            device_info = p.get_device_info_by_index(INPUT_DEVICE_INDEX)
            print(f"* Используется устройство ввода: [{INPUT_DEVICE_INDEX}] {device_info.get('name')}")
        except IOError:
            print(f"Ошибка: Неверный индекс устройства ввода: {INPUT_DEVICE_INDEX}")
            recording_active.clear() # Останавливаем все
            save_queue.put(None) # Сигнал для потока сохранения
            if p: p.terminate()
            return

        stream = p.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        frames_per_buffer=CHUNK,
                        input_device_index=INPUT_DEVICE_INDEX)

        print("* Начало записи...")
        while recording_active.is_set():
            try:
                data = stream.read(CHUNK, exception_on_overflow=False)

                # 1. Помещаем в очередь для сохранения
                save_queue.put(data)

                # 2. Раздаем всем слушателям стрима
                with listeners_lock:
                    # Создаем копию списка для безопасной итерации
                    current_listeners = list(stream_listeners)
                for listener_q in current_listeners:
                    try:
                        # Используем non-blocking put с небольшим таймаутом или проверкой размера,
                        # чтобы не блокировать запись, если клиент "завис"
                        listener_q.put_nowait(data)
                    except queue.Full:
                        # Клиент не успевает обрабатывать, можно пропустить или удалить его
                        print(f"Предупреждение: Очередь клиента {id(listener_q)} переполнена, данные пропущены.")
                        # Возможно, стоит удалить такого клиента:
                        # with listeners_lock:
                        #    if listener_q in stream_listeners:
                        #        stream_listeners.remove(listener_q)
                        #        print(f"Клиент {id(listener_q)} удален из-за переполнения.")
                    except Exception as e:
                         print(f"Ошибка при отправке данных клиенту {id(listener_q)}: {e}")


            except IOError as e:
                if e.errno == pyaudio.paInputOverflowed:
                     print(f"Предупреждение: Переполнение входного буфера ({e})")
                     # Небольшая пауза может помочь, но лучше убедиться, что обработка не тормозит
                     time.sleep(0.001)
                else:
                    print(f"Ошибка чтения из потока: {e}")
                    recording_active.clear() # Останавливаем при ошибке
                    break
            except Exception as e:
                 print(f"Неожиданная ошибка в потоке записи: {e}")
                 recording_active.clear()
                 break

    except Exception as e:
        print(f"Ошибка инициализации PyAudio или потока записи: {e}")
        recording_active.clear()
    finally:
        print("* Остановка записи (record_audio_task завершается)")
        # Сигнал для потока сохранения
        save_queue.put(None)
        # Сигнал для всех активных слушателей стрима
        with listeners_lock:
            for listener_q in stream_listeners:
                try:
                    listener_q.put_nowait(None) # Сигнал завершения
                except queue.Full:
                    pass # Если переполнена, клиент и так отвалится
                except Exception as e:
                    print(f"Ошибка при отправке None клиенту {id(listener_q)}: {e}")

        if stream:
            try:
                if stream.is_active(): stream.stop_stream()
                stream.close()
            except Exception as e: print(f"Ошибка при закрытии потока: {e}", file=sys.stderr)
        if p:
            try: p.terminate()
            except Exception as e: print(f"Ошибка при завершении PyAudio: {e}", file=sys.stderr)
        stream = None
        p = None
        print("* Ресурсы PyAudio освобождены (record_audio_task)")


def save_audio_task():
    """Получает аудио блоки из ОЧЕРЕДИ СОХРАНЕНИЯ и сохраняет их в часовые WAV файлы."""
    p_saver = None
    sample_width = 2
    try:
        p_saver = pyaudio.PyAudio()
        sample_width = p_saver.get_sample_size(FORMAT)
    except Exception as e: print(f"Не удалось инициализировать PyAudio для sample_width: {e}")
    finally:
        if p_saver: p_saver.terminate()

    current_file = None
    wf = None
    file_start_time = 0
    file_duration = 0

    print("* Поток сохранения аудио запущен.")
    while True:
        try:
            chunk = save_queue.get() # Блокируется до получения элемента

            if chunk is None:
                print("* Получен сигнал остановки в потоке сохранения.")
                if wf:
                    duration_str = time.strftime('%H:%M:%S', time.gmtime(file_duration))
                    print(f"* Закрытие последнего файла: {current_file} (Длительность: {duration_str})")
                    wf.close()
                    wf = None
                    current_file = None
                break # Завершаем поток сохранения

            now = time.time()

            if wf is None or (now - file_start_time) >= RECORD_SECONDS_PER_FILE:
                if wf:
                    duration_str = time.strftime('%H:%M:%S', time.gmtime(file_duration))
                    print(f"* Закрытие файла (по времени): {current_file} (Длительность: {duration_str})")
                    wf.close()

                file_start_time = now
                file_duration = 0
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = os.path.join(RECORDINGS_DIR, f"record_{timestamp}.wav")
                try:
                    if not os.path.exists(RECORDINGS_DIR): os.makedirs(RECORDINGS_DIR)
                    wf = wave.open(filename, 'wb')
                    wf.setnchannels(CHANNELS)
                    wf.setsampwidth(sample_width)
                    wf.setframerate(RATE)
                    current_file = filename
                    print(f"* Открытие нового файла: {current_file}")
                except Exception as e:
                    print(f"Ошибка открытия WAV файла {filename}: {e}")
                    wf = None
                    save_queue.task_done()
                    continue

            if wf:
                try:
                    wf.writeframes(chunk)
                    # Расчет длительности можно оптимизировать, делая его реже
                    file_duration += len(chunk) / (sample_width * CHANNELS * RATE)
                except Exception as e:
                    print(f"Ошибка записи в WAV файл {current_file}: {e}")
                    try: wf.close()
                    except Exception as close_e: print(f"Ошибка при закрытии файла после ошибки записи: {close_e}")
                    wf = None
                    current_file = None

            save_queue.task_done()

        except queue.Empty: # Не должно происходить с get()
            time.sleep(0.01)
        except Exception as e:
            print(f"Критическая ошибка в потоке сохранения аудио: {e}")
            if wf:
                try: wf.close()
                except Exception as close_e: print(f"Ошибка при закрытии файла в блоке except: {close_e}")
            wf = None
            current_file = None
            # При критической ошибке, возможно, стоит остановить весь процесс
            # recording_active.clear() # Сигнализируем основному потоку и записи
            # break # Выходим из цикла сохранения
            time.sleep(0.1) # Пауза перед следующей попыткой

    print("* Поток сохранения аудио завершен.")


def generate_audio_stream():
    """Генератор для потоковой передачи аудио конкретному клиенту."""
    client_q = queue.Queue(maxsize=10) # Очередь для этого клиента, maxsize для предотвращения утечек памяти
    listener_id = id(client_q)
    print(f"* Клиент стрима {listener_id} подключается...")

    with listeners_lock:
        stream_listeners.append(client_q)
    print(f"* Клиент стрима {listener_id} добавлен. Всего слушателей: {len(stream_listeners)}")

    try:
        # Можно отправить WAV заголовок один раз в начале, если клиент его ожидает
        # header = create_wav_header() # Нужна функция для генерации заголовка
        # yield header
        while True:
            chunk = client_q.get() # Блокируется, пока не появятся данные
            if chunk is None:
                print(f"* Получен сигнал остановки для клиента {listener_id}.")
                break # Запись остановлена глобально
            try:
                yield chunk
                client_q.task_done()
            except GeneratorExit:
                 print(f"* Клиент {listener_id} отключился (GeneratorExit).")
                 break
            except Exception as e:
                 print(f"* Ошибка при отправке данных клиенту {listener_id}: {e}")
                 break
    except Exception as e:
         print(f"* Ошибка в цикле обработки очереди клиента {listener_id}: {e}")
    finally:
        with listeners_lock:
            if client_q in stream_listeners:
                stream_listeners.remove(client_q)
        print(f"* Клиент стрима {listener_id} удален. Осталось слушателей: {len(stream_listeners)}")


@app.route('/')
def index():
    """Отображает главную страницу."""
    status = "Активна" if recording_active.is_set() else "Остановлено (или ошибка инициализации)"
    # Получаем имя устройства (может быть кэшировано)
    _, device_name = list_audio_devices() # Повторный вызов для актуальности, можно оптимизировать
    return render_template('index.html', status=status, device_name=device_name)

# --- УДАЛЕНЫ ЭНДПОИНТЫ /start и /stop ---

@app.route('/audio_feed')
def audio_feed():
     """Эндпоинт для потоковой передачи аудио."""
     if not recording_active.is_set():
         return Response("Запись не активна, поток недоступен.", status=404, mimetype='text/plain')
     # Возвращаем генератор. Mimetype 'audio/l16' (Linear PCM) может быть более подходящим,
     # но 'audio/wav' часто лучше поддерживается <audio> тегом, хотя и не совсем корректен для потока.
     # Клиент должен знать параметры (RATE, CHANNELS, FORMAT).
     # return Response(generate_audio_stream(), mimetype='audio/l16;rate=44100;channels=1')
     return Response(generate_audio_stream(), mimetype='audio/wav')

def start_recording_process():
    """Инициализирует и запускает потоки записи и сохранения."""
    global audio_saver_thread, recording_thread, recording_active

    is_valid_device, _ = list_audio_devices()
    if not is_valid_device:
        print("!!! Невозможно начать запись: неверное или не указано устройство ввода.")
        return False

    if recording_active.is_set():
        print("Запись уже активна.")
        return True

    print("Запуск процесса записи...")
    recording_active.set() # Устанавливаем флаг активности

    # Запускаем поток сохранения
    if audio_saver_thread is None or not audio_saver_thread.is_alive():
        # Очищаем очередь на всякий случай перед стартом
        while not save_queue.empty():
            try: save_queue.get_nowait(); save_queue.task_done()
            except queue.Empty: break
        audio_saver_thread = threading.Thread(target=save_audio_task, daemon=True) # daemon=True для простоты
        audio_saver_thread.start()
        print("Поток сохранения запущен.")
    else:
        print("Поток сохранения уже был запущен.")

    # Запускаем поток записи
    if recording_thread is None or not recording_thread.is_alive():
        recording_thread = threading.Thread(target=record_audio_task)
        recording_thread.start()
        print("Поток записи запущен.")
    else:
        print("Поток записи уже был запущен.")

    return True


def shutdown_handler(signum, frame):
    """Обработчик сигналов для корректного завершения."""
    print(f"\nПолучен сигнал {signal.Signals(signum).name}. Завершение работы...")
    global recording_active, shutdown_event
    if recording_active.is_set():
        recording_active.clear() # Сигнал потоку записи остановиться
    shutdown_event.set() # Сигнал основному потоку

    # Даем потокам время на завершение (особенно потоку записи)
    print("Ожидание завершения потока записи...")
    if recording_thread and recording_thread.is_alive():
        recording_thread.join(timeout=5.0)
        if recording_thread.is_alive():
            print("Предупреждение: Поток записи не завершился в таймаут.")

    print("Ожидание завершения потока сохранения...")
    if audio_saver_thread and audio_saver_thread.is_alive():
        # Поток сохранения ждет None в очереди, который отправит поток записи
        audio_saver_thread.join(timeout=5.0)
        if audio_saver_thread.is_alive():
             print("Предупреждение: Поток сохранения не завершился в таймаут.")

    print("Завершение работы Flask...")
    # Обычно Flask сам завершается после выхода из app.run(),
    # но можно добавить sys.exit(0) если нужно гарантированное завершение.
    # sys.exit(0)


if __name__ == '__main__':
    if not os.path.exists(RECORDINGS_DIR):
        os.makedirs(RECORDINGS_DIR)

    # Настраиваем обработчики сигналов
    signal.signal(signal.SIGINT, shutdown_handler)  # Обработка Ctrl+C
    signal.signal(signal.SIGTERM, shutdown_handler) # Обработка команды kill

    # Пытаемся запустить запись автоматически
    if start_recording_process():
        print(f"Сервер Flask запущен на http://0.0.0.0:5050")
        print("Запись и стриминг активны. Нажмите Ctrl+C для остановки.")
        # Запускаем Flask сервер в основном потоке
        # use_reloader=False ВАЖНО, иначе потоки будут запускаться дважды
        app.run(host='0.0.0.0', port=5050, debug=False, use_reloader=False)
    else:
        print("!!! Сервер Flask запущен, но запись НЕ АКТИВНА из-за ошибки конфигурации устройства.")
        print(f"!!! Проверьте настройки INPUT_DEVICE_INDEX в app.py и перезапустите.")
        # Запускаем сервер даже если запись не пошла, чтобы можно было видеть статус
        app.run(host='0.0.0.0', port=5050, debug=False, use_reloader=False)

    # Ожидаем сигнала завершения (если Flask завершился сам)
    shutdown_event.wait(timeout=2) # Небольшой таймаут на всякий случай
    print("Основной поток завершен.")