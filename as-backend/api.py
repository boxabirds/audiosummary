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
from tqdm import tqdm


app = Flask(__name__)
CORS(app)  # Initialize Flask-CORS with the default parameters

def get_sample_rate(file_path):
    info = mediainfo(file_path)
    return int(info['sample_rate'])

# extract_segments_with_id takes a transcript and returns a list of segments with their ids
def extract_segments_with_id(transcript):
    segments = []
    for sentence in transcript["segments"]:
        segments.append({
            'id': sentence["id"],
            'text': sentence["text"]
            # 'start': sentence.start,
            # 'end': sentence.end
        })
    return segments

def estimate_num_tokens(text:str) -> int:
    words = len(text.split())
    return int(words * 100 / 65)  # OpenAI docs "You can think of tokens as pieces of words, where 1,000 tokens is about 750 words." but we found that this estimate is on the optimistic side


# convert_openai_response_to_int_array takes an OpenAI response and returns a list of the ids of the top segments
# the output is simply a text string e.g. [2, 15, 17, 18, 24, 27, 28, 31, 32, 35, 41, 43, 54, 66, 67, 73, 74, 76]
# sample OpenAI response
# OpenAI response: '{
#   "id": "chatcmpl-7b6XjdWokuIeWCVyGUCUVSbAuzlGM",
#   "object": "chat.completion",
#   "created": 1689077643,
#   "model": "gpt-4-0613",
#   "choices": [
#     {
#       "index": 0,
#       "message": {
#         "role": "assistant",
#         "content": "[3, 4, 11, 14, 21, 24, 25, 30, 35, 37, 40, 42, 44, 45, 59, 62, 64, 68, 70, 79, 81, 82, 84, 85, 86, 88, 90]"
#       },
#       "finish_reason": "stop"
#     }
#   ],
#   "usage": {
#     "prompt_tokens": 2964,
#     "completion_tokens": 81,
#     "total_tokens": 3045
#   }
# }'
# I think this will change shortly to use ChatML which is nice cos parsing this stuff is error-prone and slow
def convert_openai_response_to_int_array(response):
    # convert the response to a list of integers
    print( f"OpenAI response: '{response}'")
    response = response.choices[0].message.content
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
    print(f"Extracting audio segment: {segment}")
    # Convert the audio data to a byte stream
    audio_byte_stream = io.BytesIO()
    audio_as_int16 = np.int16(audio_data * 32767).tobytes()
    audio_byte_stream.write(audio_as_int16)
    audio_byte_stream.seek(0)

    print(f"Audio byte stream: {audio_byte_stream}")
    # Load the audio data as an AudioSegment
    audio = AudioSegment.from_raw(audio_byte_stream, sample_width=2, channels=1, frame_rate=sample_rate)

    # Convert the start and end times to milliseconds
    start_time_ms = segment['start'] * 1000
    end_time_ms = segment['end'] * 1000

    # Extract the segment
    segment_audio = audio[start_time_ms:end_time_ms]

    return segment_audio




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


TRANSCRIPT_PREFIX = ".json"
SEGMENTS_PREFIX = ".segments.json"
MAX_TOKENS = 8192
PROMPT_BASE = "below is a list of sentence segments, prefixed by their segment id. please perform an extractive summary of no more than 20% of these sentences: specifically assess the text of all the segments and return the ids only of the segments that you deem to be the most important and as such meet the requirements of the top 20%.\n\n"
PROMPT_BASE_ESTD_NUM_TOKENS = estimate_num_tokens(PROMPT_BASE)

# function to send one request to OpenAI
def send_openai_request(segment_batch):
    prompt = PROMPT_BASE + json.dumps(segment_batch)
    estd_num_prompt_tokens = estimate_num_tokens(prompt)
    response = openai.ChatCompletion.create(model="gpt-4", messages=[{"role": "system", "content": prompt}], max_tokens=MAX_TOKENS-estd_num_prompt_tokens)
    return response


@app.route('/process_audio', methods=['POST', 'OPTIONS'])
def process_audio():

    CACHE_DIR = "cache/"
    os.makedirs(CACHE_DIR, exist_ok=True)
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    # save the mp3 to the cache directory
    audio = file.read()
    with open(CACHE_DIR + file.filename, 'wb') as f:
        f.write(audio)

    transcript = None

    # transcript is cached
    if os.path.exists(CACHE_DIR + file.filename + TRANSCRIPT_PREFIX ):
        with open(CACHE_DIR + file.filename + TRANSCRIPT_PREFIX) as f:
            transcript = json.load(f)
            
    # transcript is not cached
    else:
        print("Cache not found -- transcribing audio file {}".format(file.filename))
        # Load the audio and model
        audio = whisper.load_audio(file.filename)
        model = whisper.load_model("tiny", device="cpu") # use "medium" for better results but 10x slower

        # Transcribe the audio
        transcript = whisper.transcribe_timestamped(model, audio, language="en", vad=True, beam_size=5, best_of=5, temperature=(0.0, 0.2, 0.4, 0.6, 0.8, 1.0))

        # cache result in a file with the same name as the uploaded file
        with open(CACHE_DIR + file.filename + TRANSCRIPT_PREFIX, 'w') as f:
            json.dump(transcript, f)

    # segments are cached
    if os.path.exists(CACHE_DIR + file.filename + SEGMENTS_PREFIX ):
        print("Cache found -- loading segments from file")
        with open(CACHE_DIR + file.filename + SEGMENTS_PREFIX) as f:
            segments = json.load(f)

    # segments are not cached
    else:
        print("Cache not found -- extracting segments from transcript")
        segments = extract_segments_with_id(transcript)
        with open(CACHE_DIR + file.filename + SEGMENTS_PREFIX, 'w') as f:
            json.dump(segments, f)

    # Step 2: Select the top segments in batches to overcome OpenAI's limit
    responses = []
    segment_batch = []
    total_tokens = 0

    for segment in tqdm(segments):
        num_segment_tokens = estimate_num_tokens(json.dumps(segment, indent=4))

        # we have reached the max number of tokens, so send the batch to OpenAI
        if (total_tokens + num_segment_tokens + PROMPT_BASE_ESTD_NUM_TOKENS) > MAX_TOKENS:
            response = send_openai_request(segment_batch)
            responses.append(response)

            # new batch
            segment_batch = [segment]

            total_tokens = num_segment_tokens

        # we have not reached the max number of tokens, so add the segment to the batch
        else:
            segment_batch.append(segment)
            total_tokens += num_segment_tokens

    # send the final batch to OpenAI
    if len(segment_batch) > 0:
        print(f"Sending final batch to OpenAI: {len(segment_batch)} segments, {total_tokens} tokens")
        response = send_openai_request(segment_batch)
        responses.append(response)

    top_ids = [convert_openai_response_to_int_array(r) for r in responses]
    top_ids = [item for sublist in top_ids for item in sublist]

    # the segment id is a sequence so to ensure we preserve the order we sort the segments by id
    top_segments = sorted([segment for segment in segments if segment['id'] in top_ids], key=lambda x:x['id'])
    print( f"Top segments: {top_segments}")

    # Step 3: Extract the corresponding audio
    sample_rate = get_sample_rate(file.filename)
    audio_segments = [extract_audio(segment, audio, sample_rate) for segment in top_segments]
    # dump audio segments to file for debugging
    print(f"Dumping {len(audio_segments)} audio segments to files")
    for i, audio_segment in enumerate(audio_segments):
        audio_segment.export(f"segment_{i}.mp3", format="mp3")

    # Step 4: Stitch the audio together
    summary_audio = stitch_audio(audio_segments, fade_in=0.3, fade_out=0.3, silence=1)

    # Save the summary audio to a file
    print(f"Saving summary audio to {file.filename}-summary.mp3")
    summary_audio.export(f"{file.filename}-summary.mp3", format="mp3")


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
