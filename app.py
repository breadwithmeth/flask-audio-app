from flask import Flask, render_template, Response, send_from_directory
import pyaudio
import threading
import time
import os
from datetime import datetime
import signal
import sys
import glob
from pydub import AudioSegment
from pydub.utils import make_chunks
import io

app = Flask(__name__)

# --- Конфигурация аудио ---
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
CHUNK = 1024 * 2
RECORD_SECONDS_PER_FILE = 600  # 1 час
RECORDINGS_DIR = "recordings"
INPUT_DEVICE_INDEX = 3

# --- Глобальные переменные ---
recording_active = threading.Event()
current_recording_file = None
p = None
stream = None

def list_audio_devices():
    """Выводит список доступных аудиоустройств ввода."""
    p_temp = pyaudio.PyAudio()
    try:
        for i in range(p_temp.get_device_count()):
            device = p_temp.get_device_info_by_index(i)
            if device.get('maxInputChannels') > 0:
                print(f"[{i}] {device.get('name')}")
    finally:
        p_temp.terminate()

def record_audio():
    """Записывает аудио напрямую в MP3 файлы."""
    global p, stream, current_recording_file

    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT,
                   channels=CHANNELS,
                   rate=RATE,
                   input=True,
                   frames_per_buffer=CHUNK,
                   input_device_index=INPUT_DEVICE_INDEX)

    while recording_active.is_set():
        # Создаем новый файл каждый час
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = os.path.join(RECORDINGS_DIR, f"record_{timestamp}.mp3")
        current_recording_file = filename
        
        print(f"Начало записи в файл: {filename}")
        
        frames = []
        start_time = time.time()
        
        # Записываем данные в течение часа или до остановки
        while recording_active.is_set() and (time.time() - start_time) < RECORD_SECONDS_PER_FILE:
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames.append(data)

        # Конвертируем записанные данные в MP3
        audio_segment = AudioSegment(
            data=b''.join(frames),
            sample_width=p.get_sample_size(FORMAT),
            frame_rate=RATE,
            channels=CHANNELS
        )
        
        # Сохраняем как MP3
        audio_segment.export(filename, format="mp3", bitrate="128k")
        print(f"Файл записан: {filename}")

    # Очистка
    stream.stop_stream()
    stream.close()
    p.terminate()

def get_latest_recording():
    """Получает путь к последнему записанному файлу."""
    files = glob.glob(os.path.join(RECORDINGS_DIR, "record_*.mp3"))
    return max(files, key=os.path.getctime) if files else None

def stream_file(filename):
    """Стримит MP3 файл."""
    chunk_size = 8192
    with open(filename, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            yield chunk

def audio_stream():
    """Генератор для стриминга живого аудио."""
    global p, stream

    if p is None:
        p = pyaudio.PyAudio()
    if stream is None:
        stream = p.open(format=FORMAT,
                       channels=CHANNELS,
                       rate=RATE,
                       input=True,
                       frames_per_buffer=CHUNK,
                       input_device_index=INPUT_DEVICE_INDEX)

    try:
        while True:
            # Собираем несколько чанков для лучшего качества
            frames = []
            for _ in range(10):  # берем 10 чанков за раз
                data = stream.read(CHUNK, exception_on_overflow=False)
                frames.append(data)

            # Конвертируем в MP3
            audio_segment = AudioSegment(
                data=b''.join(frames),
                sample_width=p.get_sample_size(FORMAT),
                frame_rate=RATE,
                channels=CHANNELS
            )
            
            # Используем более низкий битрейт для уменьшения задержки
            buffer = io.BytesIO()
            audio_segment.export(buffer, format="mp3", bitrate="64k")
            
            # Добавляем заголовок для chunked transfer encoding
            yield buffer.getvalue()
    except Exception as e:
        print(f"Ошибка стриминга: {e}")
        if stream:
            stream.stop_stream()
            stream.close()
        if p:
            p.terminate()

def get_recordings():
    """Получает список всех записей с их метаданными."""
    files = glob.glob(os.path.join(RECORDINGS_DIR, "record_*.mp3"))
    recordings = []
    for file in files:
        filename = os.path.basename(file)
        # Получаем дату из имени файла (формат: record_YYYYMMDD_HHMMSS.mp3)
        date_str = filename[7:15]  # YYYYMMDD
        time_str = filename[16:22]  # HHMMSS
        date_time = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]} {time_str[:2]}:{time_str[2:4]}:{time_str[4:]}"
        recordings.append({
            'filename': filename,
            'datetime': date_time,
            'path': file
        })
    return sorted(recordings, key=lambda x: x['datetime'], reverse=True)

@app.route('/')
def index():
    """Главная страница."""
    recordings = get_recordings()
    status = "Активна" if recording_active.is_set() else "Остановлена"
    return render_template('index.html', status=status, recordings=recordings)

@app.route('/recordings/<path:filename>')
def serve_recording(filename):
    """Отдает аудиофайл."""
    return send_from_directory(RECORDINGS_DIR, filename)

@app.route('/audio_feed')
def audio_feed():
    """Стриминг последнего записанного файла."""
    latest_file = get_latest_recording()
    if not latest_file:
        return Response("Нет доступных записей", status=404)
    return Response(stream_file(latest_file), mimetype='audio/mpeg')

@app.route('/live')
def live_audio():
    """Маршрут для стриминга живого аудио."""
    return Response(
        audio_stream(),
        mimetype='audio/mpeg',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )

def shutdown_handler(signum, frame):
    """Корректное завершение при получении сигнала."""
    print("\nЗавершение работы...")
    recording_active.clear()
    sys.exit(0)

if __name__ == '__main__':
    if not os.path.exists(RECORDINGS_DIR):
        os.makedirs(RECORDINGS_DIR)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    recording_active.set()
    recording_thread = threading.Thread(target=record_audio)
    recording_thread.start()

    print("Сервер запущен на http://0.0.0.0:5051")
    app.run(host='0.0.0.0', port=5051, debug=False)