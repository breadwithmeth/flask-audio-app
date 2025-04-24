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