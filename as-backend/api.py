from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Initialize Flask-CORS with the default parameters

@app.route('/process_audio', methods=['POST'])
def process_audio():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    # Here you would typically process the file with Whisper and get the sentences and audio path
    # But for now, we'll just return a mock response

    response = {
        'sentences': [
            { 'id': 1, 'text': "This is a short sentence.", 'selected': True },
            { 'id': 2, 'text': "This is slightly longer.", 'selected': True },
            { 'id': 3, 'text': "Here is the longest sentence of all, filled with grandeur and eloquence.", 'selected': True }
        ],
        'audioPath': '/lesson-of-greatness-daniel-ek.mp3'  # the path to your mp3 file
    }

    return jsonify(response)

if __name__ == '__main__':
    app.run(debug=True)
