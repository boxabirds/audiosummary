from ast import Dict
import os
import string
from typing import Any
from flask import Flask, request, jsonify
from flask_cors import CORS
import whisper_timestamped as whisper
import tempfile
import json
import openai
from pydub import AudioSegment
import numpy as np
import io
from tqdm import tqdm
from pathlib import Path
import ffmpeg


app = Flask(__name__)
CORS(app)  # Initialize Flask-CORS with the default parameters


def extract_sentence_timestamps(sentences: list[dict[str, Any]], segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # written and tested by chatgpt code interpreter 
    # Initialize list to hold all words and their timestamps
    all_words = []

    # Iterate over each segment
    for segment in segments:
        # Extend all_words list with words in current segment
        all_words.extend(segment["words"])

    # Function to remove punctuation from a word
    def remove_punctuation(word):
        return word.strip(string.punctuation)

    # Iterate over each sentence
    for sentence in sentences:
        # Split sentence into words
        sentence_words = sentence["text"].split()

        # Initialize word index for sentence and segments
        sentence_word_index = 0
        segment_word_index = 0

        # Find the starting timestamp
        while sentence_word_index < len(sentence_words) and segment_word_index < len(all_words):
            if remove_punctuation(sentence_words[sentence_word_index]) == remove_punctuation(all_words[segment_word_index]["text"]):
                sentence["start"] = all_words[segment_word_index]["start"]
                break
            segment_word_index += 1

        # Find the ending timestamp
        while sentence_word_index < len(sentence_words) and segment_word_index < len(all_words):
            if remove_punctuation(sentence_words[sentence_word_index]) == remove_punctuation(all_words[segment_word_index]["text"]):
                sentence_word_index += 1
            if sentence_word_index == len(sentence_words) or (segment_word_index < len(all_words) - 1 and remove_punctuation(sentence_words[sentence_word_index]) != remove_punctuation(all_words[segment_word_index + 1]["text"])):
                sentence["end"] = all_words[segment_word_index]["end"]
            segment_word_index += 1

    return sentences




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

def add_audio_fades(segment, fade_in=300, fade_out=300):
    # Applying fade in and fade out effect
    segment = segment.fade_in(fade_in).fade_out(fade_out)
    return segment

def create_audio_summary(source_file:str, segments):
    source_file_path = Path(source_file)
    original_audio = AudioSegment.from_mp3(source_file_path)

    prev_end = None
    result_audio = AudioSegment.empty()
    for index, segment in enumerate(segments):
        start = max(0, segment["start"] * 1000 - 300)    # Mind boundaries: no negative times
        end = segment["end"] * 1000 + 300                # Extra boundary check not needed as pydub handles overshot

        if prev_end is not None and start < prev_end:
            start = prev_end                             # Ensure seamless audio between adjacent segments

        extract = original_audio[start:end]              

        # Apply fades but avoid in case of adjacent segments
        if start > 0:                                    
            extract = extract.fade_in(300)
        if index == len(segments) - 1 or (index < len(segments) - 1 and segments[index + 1]["start"] * 1000 > segment["end"] * 1000):
            extract = extract.fade_out(300)

        result_audio += extract                          # Concatenate segment
        prev_end = segment["end"] * 1000                 # Store previous segment end time 

    summary_filename = f"{source_file_path.stem}-summary.mp3"
    result_audio.export(f"{summary_filename}", format="mp3")
    return summary_filename


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

    # now build up a list of top segments with their start and end times from the original transcript
    top_segments = []
    for segment in transcript["segments"]:
        if segment["id"] in top_ids:
            top_segments.append({
                'id': segment["id"],
                'text': segment["text"],
                'start': segment["start"],
                'end': segment["end"]
            })
    
    
    print( f"Top segments: {top_segments}")

    summary_filename = create_audio_summary(CACHE_DIR + file.filename, top_segments)

    response = {
        'sentences': [
            { 'id': 1, 'text': "This is a short sentence.", 'selected': True },
            { 'id': 2, 'text': "This is slightly longer.", 'selected': True },
            { 'id': 3, 'text': "Here is the longest sentence of all, filled with grandeur and eloquence.", 'selected': True }
        ],
        'audioPath': "/" + summary_filename  # the path to your mp3 file
    }

    return jsonify(response)

if __name__ == '__main__':
    app.run(debug=True)
