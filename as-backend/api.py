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
from sentence_splitter import SentenceSplitter, split_text_into_sentences
import string


app = Flask(__name__)
CORS(app)  # Initialize Flask-CORS with the default parameters

def extract_words(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
# extract all the words from each segment and return a flat list of words. Much easier to process
    words = []
    for segment in segments:
        for word in segment["words"]:
            words.append(word)
    return words


def split_sentences(text):
    splitter = SentenceSplitter(language='en')
    sentences = splitter.split(text)
    return sentences


def create_sentence_objects(raw_transcript:str, word_objects: list[dict[str, Any]]):

    sentences = split_sentences(raw_transcript)
    sentence_objects = []
    word_index = 0

    for i, sentence in enumerate(sentences):
        # Remove punctuation from the sentence
        sentence_no_punct = sentence.translate(str.maketrans('', '', string.punctuation))
        words = sentence_no_punct.split()
        start_time = word_objects[word_index]["start"]
        end_time = word_objects[word_index + len(words) - 1]["end"]
        
        sentence_object = {
            "id": i,
            "text": sentence,
            "start": start_time,
            "end": end_time
        }
        sentence_objects.append(sentence_object)
        word_index += len(words)

    return sentence_objects




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
    return int(words * 100 / 50)  # OpenAI docs "You can think of tokens as pieces of words, where 1,000 tokens is about 750 words." but we found that this estimate is on the optimistic side


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

def create_audio_summary(source_file:str, sentences):
    source_file_path = Path(source_file)
    original_audio = AudioSegment.from_mp3(source_file_path)

    prev_end = None
    result_audio = AudioSegment.empty()
    extract_gap = AudioSegment.silent(duration=1000)
    for index, sentence in enumerate(sentences):
        start = max(0, sentence["start"] * 1000 - 300)    # Mind boundaries: no negative times
        end = sentence["end"] * 1000 + 300                # Extra boundary check not needed as pydub handles overshot

        if prev_end is not None and start < prev_end:
            start = prev_end                             # Ensure seamless audio between adjacent segments

        extract = original_audio[start:end]              

        # Apply fades but avoid in case of adjacent segments
        if start > 0:                                    
            extract = extract.fade_in(300)
        if index == len(sentences) - 1 or (index < len(sentences) - 1 and sentences[index + 1]["start"] * 1000 > sentence["end"] * 1000):
            extract = extract.fade_out(300)

        result_audio += extract + extract_gap                 # Concatenate segment
        prev_end = sentence["end"] * 1000                 # Store previous segment end time 

    summary_filename = f"{source_file_path.stem}-summary.mp3"
    result_audio.export(f"{summary_filename}", format="mp3")
    return summary_filename


TRANSCRIPT_PREFIX = ".json"
MAX_TOKENS = 8192 #gpt-4, July 2023

def generate_prompt_base(num_sentences):
    sentence_limit_pct = 0.2 # 20% of the sentences
    sentence_summary_count_limit = int(num_sentences * sentence_limit_pct)
    prompt_base = f"below is a list of sentences, prefixed by their id. Please perform an extractive summary, selecting no more than {sentence_summary_count_limit} of these sentences: specifically assess the text of all the sentences and return the ids only of the sentences that are most important and as such meet the requirements of the top {sentence_summary_count_limit} sentences\n\n"
    return prompt_base

def generate_prompt(sentences):
    prompt_base = generate_prompt_base(len(sentences))
    prompt = prompt_base + json.dumps(sentences)
    #print(f"Prompt: \n\n{prompt}\n\n")
    return prompt, estimate_num_tokens(prompt)

def estimate_openai_response_token_count(sentences):
    # stupidest API in the world bundles requests with responses so you have to dance through some hoops to estimate the full token count
    # create a list of all the ids, convert it to a string separated by commas, bracketd by [ and ], and imperically that's roughly the number of tokens used
    # this is a hack and will break if OpenAI change their API
    ids = [sentence["id"] for sentence in sentences]
    ids = str(ids)
    ids = ids.replace(" ", "")
    return len(ids) + 2 # no idea what the extra 2 given brackets are already there but the API responses don't lie


def minimise_sentence_batch_for_openai(sentence_batch):
    # openai doesn't need the start and end times, so strip them out to reduce token count
    return [{k: v for k, v in d.items() if k != "start" and k != "end"} for d in sentence_batch]

# function to send one request to OpenAI
def send_sentence_batch_to_openai(sentence_batch):
    # strip the start and end times from a copy of this batch as they're not needed for inference
    stripped_sentence_batch = minimise_sentence_batch_for_openai(sentence_batch)

    prompt, estd_num_prompt_tokens = generate_prompt(stripped_sentence_batch)

    max_tokens = MAX_TOKENS-estd_num_prompt_tokens
    print(f"Sending batch to OpenAI: {len(stripped_sentence_batch)} sentences, {estd_num_prompt_tokens} prompt tokens, {max_tokens} max tokens\n\n{stripped_sentence_batch}")
    response = openai.ChatCompletion.create(model="gpt-4", messages=[{"role": "system", "content": prompt}], max_tokens=max_tokens)
    return response



def create_sentence_objects_for_openai(sentences):
    sentence_objects = []
    for i, sentence in enumerate(sentences):
        sentence_objects.append({
            "id": i,
            "text": sentence,
        })
    return sentence_objects

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

    # convert raw transcript into an array of sentences created by sentence-splitter
    # Extract the words for processing -- segments just get in the way
    words = extract_words(transcript["segments"])
    #print( f"Words: {json.dumps(words, indent=4)}")

    raw_transcript = transcript["text"]
    sentences = create_sentence_objects(raw_transcript, words)
    #print( f"Sentences: {json.dumps(sentences, indent=4)}")    

    # Step 2: Select the top segments in batches to overcome OpenAI's limit
    responses = []
    sentence_batch = []

    for sentence in tqdm(sentences):
        # estimate whether we'd exceed the max number of tokens if we added this sentence to the batch
        # the total is the request and the response, so:
        # - the prompt
        # - the sentences with ids as formatted by json.dumps
        # - the response

        # calculate what the new batch size would be and if it's too big then send the current batch to OpenAI
        new_sentence_batch = sentence_batch.copy()
        new_sentence_batch.append(sentence)

        # todo this code is a bit messy -- we should keep the openai preprocessing in one place
        _, estd_num_prompt_tokens = generate_prompt(minimise_sentence_batch_for_openai(new_sentence_batch))
        estd_response_size = estimate_openai_response_token_count(new_sentence_batch)
        potential_round_trip_size = estd_num_prompt_tokens + estd_response_size
        # we have reached the max number of tokens, so send the batch to OpenAI
        if potential_round_trip_size > MAX_TOKENS:
            response = send_sentence_batch_to_openai(sentence_batch)
            responses.append(response)

            # new batch
            sentence_batch = [sentence]

        # we have not reached the max number of tokens, so add the segment to the batch
        else:
            sentence_batch.append(sentence)

    # send the final batch to OpenAI
    if len(sentence_batch) > 0:
        print(f"Sending final batch to OpenAI: {len(sentence_batch)} segments")
        response = send_sentence_batch_to_openai(sentence_batch)
        responses.append(response)

    top_ids = [convert_openai_response_to_int_array(r) for r in responses]
    top_ids = [item for sublist in top_ids for item in sublist]

    # now build up a list of top sentences with their start and end times from the original transcript
    top_sentences = []
    for sentence in sentences:
        if sentence["id"] in top_ids:
            top_sentences.append({
                'id': sentence["id"],
                'text': sentence["text"],
                'start': sentence["start"],
                'end': sentence["end"]
            })
    
    
    print( f"Top sentences: {json.dumps(top_sentences, indent=4)}")

    summary_filename = create_audio_summary(CACHE_DIR + file.filename, top_sentences)

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
