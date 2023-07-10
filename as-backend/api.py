import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import whisper_timestamped as whisper
import tempfile
import json
import openai
from pydub.utils import mediainfo
from pydub import AudioSegment
import numpy as np
import io


app = Flask(__name__)
CORS(app)  # Initialize Flask-CORS with the default parameters

def get_sample_rate(file_path):
    info = mediainfo(file_path)
    return int(info['sample_rate'])

# extract_segments_with_id takes a transcript and returns a list of segments with their ids
def extract_segments_with_id(transcript):
    segments = []
    for sentence in transcript:
        segments.append({
            'id': sentence.id,
            'text': sentence.text
            # 'start': sentence.start,
            # 'end': sentence.end
        })
    return segments

# parse_response takes an OpenAI response and returns a list of the ids of the top segments
# the output is simply a text string e.g. [2, 15, 17, 18, 24, 27, 28, 31, 32, 35, 41, 43, 54, 66, 67, 73, 74, 76]
def parse_response(response):
    # convert the response to a list of integers
    response = response.choices[0].text
    response = response.replace("[", "")
    response = response.replace("]", "")
    response = response.replace(" ", "")
    response = response.split(",")
    response = [int(id) for id in response]
    return response



def extract_audio(segment, audio_data, sample_rate=16000):
    """
    Extract a segment from an audio data array.

    Parameters:
    segment (dict): The segment dict with 'start' and 'end' keys in seconds.
    audio_data (numpy.ndarray): The audio data array.
    sample_rate (int): The sample rate of the audio data.

    Returns:
    AudioSegment: The extracted audio segment.
    """
    # Convert the audio data to a byte stream
    audio_byte_stream = io.BytesIO()
    audio_as_int16 = np.int16(audio_data * 32767).tobytes()
    audio_byte_stream.write(audio_as_int16)
    audio_byte_stream.seek(0)

    # Load the audio data as an AudioSegment
    audio = AudioSegment.from_raw(audio_byte_stream, sample_width=2, channels=1, frame_rate=sample_rate)

    # Convert the start and end times to milliseconds
    start_time_ms = segment['start'] * 1000
    end_time_ms = segment['end'] * 1000

    # Extract the segment
    segment_audio = audio[start_time_ms:end_time_ms]

    return segment_audio


from pydub import AudioSegment

def stitch_audio(audio_segments, fade_in, fade_out, silence):
    """
    Stitch together a list of audio segments.

    Parameters:
    audio_segments (list of AudioSegment): The audio segments to stitch together.
    fade_in (float): The duration of the fade-in effect in seconds.
    fade_out (float): The duration of the fade-out effect in seconds.
    silence (float): The duration of the silence to insert between segments in seconds.

    Returns:
    AudioSegment: The stitched-together audio.
    """
    # Convert the fade-in, fade-out, and silence durations to milliseconds
    fade_in_ms = fade_in * 1000
    fade_out_ms = fade_out * 1000
    silence_ms = silence * 1000

    # Create an empty AudioSegment for the silence
    silence_segment = AudioSegment.silent(duration=silence_ms)

    # Add fade-in and fade-out effects to each segment and concatenate them with silence in between
    stitched_audio = AudioSegment.empty()
    for segment in audio_segments:
        segment = segment.fade_in(fade_in_ms).fade_out(fade_out_ms)
        stitched_audio += segment + silence_segment

    return stitched_audio



@app.route('/process_audio', methods=['POST'])
def process_audio():
    CACHE_DIR = "cache/"
    os.makedirs(CACHE_DIR, exist_ok=True)
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    # save the mp3 to the cache directory
    with open(CACHE_DIR + file.filename, 'wb') as f:
        f.write(file.read())

    result = None
    # we cache the transcript mostly for development purposes -- depending on model size and audio length, it can take 10 minutes or as long as 2 hours to transcribe
    # if the corresponding cache file exists, use that instead of transcribing again
    if os.path.exists(CACHE_DIR + file.filename + ".json" ):
        # load the cached mp3 file
        with open(CACHE_DIR + file.filename, 'rb') as f:
            audio = f.read()

        with open(CACHE_DIR + file.filename + ".json") as f:
            result = json.load(f)

        with open(CACHE_DIR + file.filename + "segments.json") as f:
            segments = json.load(f)

    else:
        # Load the audio and model
        audio = whisper.load_audio(file.filename)
        model = whisper.load_model("tiny", device="cpu") # use "medium" for better results but 10x slower

        # Transcribe the audio
        result = whisper.transcribe_timestamped(model, audio, language="en", vad=True, beam_size=5, best_of=5, temperature=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0))

        # cache result in a file with the same name as the uploaded file
        with open(CACHE_DIR + file.filename + ".json", 'w') as f:
            json.dump(result, f)

        segments = extract_segments_with_id(result)
        with open(file.filename + ".segments.json", 'w') as f:
            json.dump(segments, f)

    # Step 2: Select the top segments
    prompt = "below is a list of sentence segments, prefixed by their segment id. please perform an extractive summary of no more than 20% of these sentences: specifically assess the text of all the segments and return the ids only of the segments that you deem to be the most important and as such meet the requirements of the top 20%.\n\n" + json.dumps(segments)
    response = openai.ChatCompletion.create(model="gpt4", messages=[{"role": "system", "content": prompt}], max_tokens=32000)

    print("openai.ChatCompletion response: {}".format(response))

    top_ids = parse_response(response)
    top_segments = [segment for segment in segments if segment.id in top_ids]

    # Step 3: Extract the corresponding audio
    sample_rate = get_sample_rate(file.filename)
    audio_segments = [extract_audio(segment, audio, sample_rate) for segment in top_segments]

    # Step 4: Stitch the audio together
    summary_audio = stitch_audio(audio_segments, fade_in=0.3, fade_out=0.3, silence=1)

    # Save the summary audio to a file
    summary_audio.export("summary.mp3", format="mp3")


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
