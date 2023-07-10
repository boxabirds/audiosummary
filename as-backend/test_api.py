import pytest
from flask.testing import FlaskClient
from werkzeug.datastructures import FileStorage
import io
import os

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
