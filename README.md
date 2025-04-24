# Flask Audio Streaming Application

This project is a Flask-based web application that allows users to stream audio from their microphone and save recordings in hourly segments. 

## Project Structure

```
flask-audio-app
├── app.py                # Main application file that sets up the Flask server and handles audio streaming and recording.
├── templates
│   └── index.html       # HTML template for the user interface, including controls for audio streaming.
├── static
│   └── style.css        # CSS styles for the user interface to enhance visual appeal.
├── requirements.txt      # List of dependencies required for the application, such as Flask and audio libraries.
└── README.md             # Documentation for the project, including installation and usage instructions.
```

## Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   cd flask-audio-app
   ```

2. Create a virtual environment (optional but recommended):
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

1. Run the application:
   ```
   python app.py
   ```

2. Open your web browser and navigate to `http://127.0.0.1:5000`.

3. Use the interface to start and stop audio streaming. The application will automatically save recordings in hourly segments.

## Features

- Stream audio from your microphone in real-time.
- Automatically save audio recordings every hour.
- Simple and user-friendly interface for controlling audio streaming.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

# Аудио-рекордер на Flask

Веб-приложение для записи и воспроизведения аудио с микрофона.

## Функциональность

- Запись аудио с выбранного микрофона
- Сохранение записей в формате MP3
- Просмотр архива записей
- Воспроизведение записей через веб-интерфейс

## Установка и запуск

### macOS

1. Установите Python 3.8 или выше
2. Установите Homebrew (если еще не установлен):
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

3. Установите необходимые системные зависимости:
```bash
brew install portaudio ffmpeg
```

4. Создайте и активируйте виртуальное окружение:
```bash
python -m venv venv
source venv/bin/activate
```

5. Установите зависимости Python:
```bash
pip install -r requirements.txt
```

### Windows

1. Установите Python 3.8 или выше с [официального сайта](https://www.python.org/downloads/)
2. Установите [Visual C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
3. Установите [FFmpeg](https://www.gyan.dev/ffmpeg/builds/). Добавьте путь к FFmpeg в переменную PATH

4. Создайте и активируйте виртуальное окружение:
```bash
python -m venv venv
venv\Scripts\activate
```

5. Установите зависимости Python:
```bash
pip install -r requirements.txt
```

## Запуск приложения

1. Активируйте виртуальное окружение:
- macOS: `source venv/bin/activate`
- Windows: `venv\Scripts\activate`

2. Запустите приложение:
```bash
python app.py
```

3. При первом запуске будет выведен список доступных аудиоустройств. Выберите нужный индекс микрофона и укажите его в переменной `INPUT_DEVICE_INDEX` в файле `app.py`

4. Откройте браузер и перейдите по адресу: http://localhost:5051

## Настройка

- `RECORD_SECONDS_PER_FILE` - длительность одного файла записи (в секундах)
- `INPUT_DEVICE_INDEX` - индекс устройства ввода (микрофона)
- `RECORDINGS_DIR` - директория для сохранения записей

## Требования

- Python 3.8+
- FFmpeg
- PortAudio
- Зависимости из requirements.txt

## Решение проблем

### macOS

Если возникают проблемы с установкой PyAudio:
```bash
pip install --global-option='build_ext' --global-option='-I/opt/homebrew/include' --global-option='-L/opt/homebrew/lib' pyaudio
```

### Windows

Если не находится FFmpeg:
1. Убедитесь, что путь к FFmpeg добавлен в переменную PATH
2. Перезапустите терминал/IDE после изменения PATH