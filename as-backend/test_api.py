import pytest
from flask.testing import FlaskClient
from werkzeug.datastructures import FileStorage
import io
import os
from api import split_sentences, create_sentence_objects

def test_process_audio(client: FlaskClient):
    # Load the audio file
    with open("lesson-of-greatness-daniel-ek.mp3", "rb") as f:
        audio_content = f.read()
    
    audio_file = FileStorage(
        stream=io.BytesIO(audio_content),
        filename="lesson-of-greatness-daniel-ek.mp3",
        content_type="audio/mpeg",
    )

    # Send a POST request to the /process_audio endpoint
    response = client.post("/process_audio", data={"file": audio_file})

    # Check that the response status code is 200
    assert response.status_code == 200

    # Check that the response data matches the expected result
    # (replace this with your actual expected result)
    expected_result = {
        "sentences": [
            {"id": 1, "text": "This is a short sentence.", "selected": False},
            {"id": 2, "text": "This is slightly longer.", "selected": False},
            {"id": 3, "text": "Here is the longest sentence of all, filled with grandeur and eloquence.", "selected": False}
        ],
        "audioPath": "/lesson-of-greatness-daniel-ek.mp3"
    }
    assert response.json == expected_result

    # Check that the summary audio file was created
    assert os.path.exists("summary.mp3")

@pytest.fixture
def client():
    from api import app  # replace with the name of your Flask app module
    with app.test_client() as client:
        yield client


import pytest

import pytest

@pytest.mark.parametrize("raw_transcript, word_objects, expected", [
    # Test case 1: Basic test case
    ("Hello world. How are you?", 
     [
        {"id": 0, "start": 0.0, "end": 0.5, "text": "Hello"},
        {"id": 1, "start": 0.5, "end": 1.0, "text": "world"},
        {"id": 2, "start": 1.0, "end": 1.5, "text": "How"},
        {"id": 3, "start": 1.5, "end": 2.0, "text": "are"},
        {"id": 4, "start": 2.0, "end": 2.5, "text": "you"}
     ],
     [
        {"id": 0, "text": "Hello world.", "start": 0.0, "end": 1.0},
        {"id": 1, "text": "How are you?", "start": 1.0, "end": 2.5}
     ]),
     
     # Test case 2: Repeated sentence
    ("Hello world. Hello world.", 
     [
        {"id": 0, "start": 0.0, "end": 0.5, "text": "Hello"},
        {"id": 1, "start": 0.5, "end": 1.0, "text": "world"},
        {"id": 2, "start": 1.0, "end": 1.5, "text": "Hello"},
        {"id": 3, "start": 1.5, "end": 2.0, "text": "world"}
     ],
     [
        {"id": 0, "text": "Hello world.", "start": 0.0, "end": 1.0},
        {"id": 1, "text": "Hello world.", "start": 1.0, "end": 2.0}
     ]),
     
     # Test case 3: Empty lists
    ("", [], []),
     
     # Test case 4: Additional words in a sentence
    ("Hello world. Hello world again.", 
     [
        {"id": 0, "start": 0.0, "end": 0.5, "text": "Hello"},
        {"id": 1, "start": 0.5, "end": 1.0, "text": "world"},
        {"id": 2, "start": 1.0, "end": 1.5, "text": "Hello"},
        {"id": 3, "start": 1.5, "end": 2.0, "text": "world"},
        {"id": 4, "start": 2.0, "end": 2.5, "text": "again"}
     ],
     [
        {"id": 0, "text": "Hello world.", "start": 0.0, "end": 1.0},
        {"id": 1, "text": "Hello world again.", "start": 1.0, "end": 2.5}
     ]),
     
     # Test case 5: Punctuation
    ("Hello, world! How are you?", 
     [
        {"id": 0, "start": 0.0, "end": 0.5, "text": "Hello"},
        {"id": 1, "start": 0.5, "end": 1.0, "text": "world"},
        {"id": 2, "start": 1.0, "end": 1.5, "text": "How"},
        {"id": 3, "start": 1.5, "end": 2.0, "text": "are"},
        {"id": 4, "start": 2.0, "end": 2.5, "text": "you"}
     ],
     [
        {"id": 0, "text": "Hello, world!", "start": 0.0, "end": 1.0},
        {"id": 1, "text": "How are you?", "start": 1.0, "end": 2.5}
     ]),
     
     # Test case 6: Single word sentence
    ("Hello", 
     [
        {"id": 0, "start": 0.0, "end": 0.5, "text": "Hello"}
     ],
     [
        {"id": 0, "text": "Hello", "start": 0.0, "end": 0.5}
     ])
])
def test_create_sentence_objects(raw_transcript, word_objects, expected):
    result = create_sentence_objects(raw_transcript, word_objects)
    assert result == expected


