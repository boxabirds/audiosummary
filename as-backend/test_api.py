import pytest
from flask.testing import FlaskClient
from werkzeug.datastructures import FileStorage
import io
import os
from api import extract_sentence_timestamps

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


@pytest.mark.parametrize("sentences, segments, expected", [
    (
        [{"id": 0, "text": "We referenced the products."}],
        [
            {
                "id": 0,
                "words": [
                    {"text": "We", "start": 0.08, "end": 0.26},
                    {"text": "referenced", "start": 0.26, "end": 0.78},
                    {"text": "the", "start": 0.78, "end": 1.02},
                    {"text": "products.", "start": 1.02, "end": 1.5}
                ]
            }
        ],
        [{"id": 0, "text": "We referenced the products.", "start": 0.08, "end": 1.5}]
    ),
    (
        [{"id": 0, "text": "We referenced the products we used."}],
        [
            {
                "id": 0,
                "words": [
                    {"text": "We", "start": 0.08, "end": 0.26},
                    {"text": "referenced", "start": 0.26, "end": 0.78},
                    {"text": "the", "start": 0.78, "end": 1.02},
                    {"text": "products", "start": 1.02, "end": 1.5}
                ]
            },
            {
                "id": 1,
                "words": [
                    {"text": "we", "start": 1.5, "end": 1.7},
                    {"text": "used.", "start": 1.7, "end": 2.0}
                ]
            }
        ],
        [{"id": 0, "text": "We referenced the products we used.", "start": 0.08, "end": 2.0}]
    ),
    (
        [{"id": 0, "text": "We referenced the products, we used today."}],
        [
            {
                "id": 0,
                "words": [
                    {"text": "We", "start": 0.08, "end": 0.26},
                    {"text": "referenced", "start": 0.26, "end": 0.78},
                    {"text": "the", "start": 0.78, "end": 1.02},
                    {"text": "products", "start": 1.02, "end": 1.5}
                ]
            },
            {
                "id": 1,
                "words": [
                    {"text": "we", "start": 1.5, "end": 1.7},
                    {"text": "used", "start": 1.7, "end": 2.0}
                ]
            },
            {
                "id": 2,
                "words": [
                    {"text": "today.", "start": 2.0, "end": 2.36}
                ]
            }
        ],
        [{"id": 0, "text": "We referenced the products, we used today.", "start": 0.08, "end": 2.36}]
    ),
    (
        [{"id": 0, "text": "the products we used"}],
        [
            {
                "id": 0,
                "words": [
                    {"text": "We", "start": 0.08, "end": 0.26},
                    {"text": "referenced", "start": 0.26, "end": 0.78},
                    {"text": "the", "start": 0.78, "end": 1.02},
                    {"text": "products", "start": 1.02, "end": 1.5}
                ]
            },
            {
                "id": 1,
                "words": [
                    {"text": "we", "start": 1.5, "end": 1.7},
                    {"text": "used", "start": 1.7, "end": 2.0},
                    {"text": "today.", "start": 2.0, "end": 2.36}
                ]
            }
        ],
        [{"id": 0, "text": "the products we used", "start": 0.78, "end": 2.0}]
    )
])
def test_extract_sentence_timestamps(sentences, segments, expected):
    result = extract_sentence_timestamps(sentences, segments)
    assert result == expected, f'Expected {expected}, but got {result}'
