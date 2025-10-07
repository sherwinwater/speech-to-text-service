"""
Tests for transcription controller (HTTP endpoints).
"""

import pytest
from fastapi.testclient import TestClient
from api.main import app
from api.controllers.transcription_controller import get_transcriber
from api.services.transcriber_service import FakeTranscriber


# Override dependency to avoid downloading real models
@pytest.fixture
def client():
    """Create test client with mocked transcriber."""
    app.dependency_overrides[get_transcriber] = lambda: FakeTranscriber()
    yield TestClient(app)
    app.dependency_overrides.clear()


class TestTranscriptionController:
    """Test transcription HTTP endpoints."""
    
    def test_transcribe_with_file(self, client):
        """Test file upload transcription."""
        # TODO: Implement test
        pass
    
    def test_transcribe_with_url(self, client):
        """Test URL transcription."""
        # TODO: Implement test
        pass
    
    def test_transcribe_missing_input(self, client):
        """Test error when no file or URL provided."""
        # TODO: Implement test
        pass
    
    def test_transcribe_with_language(self, client):
        """Test transcription with language parameter."""
        # TODO: Implement test
        pass
    
    def test_transcribe_with_word_timestamps(self, client):
        """Test transcription with word timestamps."""
        # TODO: Implement test
        pass
    
    def test_transcribe_file_too_large(self, client):
        """Test file size limit enforcement."""
        # TODO: Implement test
        pass
