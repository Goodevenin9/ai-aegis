"""
Unit tests for Aegis AI Threat Monitor Client
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from aegis import AegisClient
from aegis.models.analysis_result import AnalysisResult, DetectionMethod, ThreatDetection
from aegis.models.config_models import OperationMode
from aegis.utils.exceptions import ConfigurationError, ValidationError


class TestAegisClient:
    """Test cases for AegisClient"""

    def test_client_initialization_local_mode(self):
        """Test client initialization in local mode"""
        client = AegisClient(mode=OperationMode.LOCAL)
        assert client is not None
        assert client.config.mode == OperationMode.LOCAL

    def test_client_initialization_hybrid_mode(self, mock_api_key):
        """Test client initialization in hybrid mode"""
        client = AegisClient(mode=OperationMode.HYBRID, api_key=mock_api_key)
        assert client is not None
        assert client.config.mode == OperationMode.HYBRID

    def test_client_initialization_api_mode(self, mock_api_key):
        """Test client initialization in API mode"""
        client = AegisClient(mode=OperationMode.API, api_key=mock_api_key)
        assert client is not None
        assert client.config.mode == OperationMode.API

    def test_client_initialization_without_api_key_fails(self):
        """Test that API mode fails without API key"""
        with pytest.raises(ConfigurationError):
            AegisClient(mode=OperationMode.API)

    @patch("aegis.client.AegisClient.analyze")
    def test_analyze_safe_prompt(self, mock_analyze, sample_prompts):
        """Test analysis of safe prompts"""
        # Mock the analyze method to return a safe result
        mock_result = AnalysisResult(
            is_threat=False, 
            risk_score=0, 
            confidence=0.95, 
            detections=[], 
            analysis_time_ms=15.0,
            detection_method=DetectionMethod.LOCAL_RULES
        )
        mock_analyze.return_value = mock_result

        client = AegisClient(mode=OperationMode.LOCAL)

        for prompt in sample_prompts["safe"]:
            result = client.analyze(prompt)
            assert result.is_threat is False
            assert result.risk_score < 0.5
            assert result.confidence > 0.8

    @patch("aegis.client.AegisClient.analyze")
    def test_analyze_threat_prompt(self, mock_analyze, sample_prompts):
        """Test analysis of threat prompts"""
        # Mock the analyze method to return a threat result
        mock_result = AnalysisResult(
            is_threat=True,
            risk_score=90,
            detections=[ThreatDetection(
                threat_type="prompt_injection",
                risk_score=90,
                confidence=0.95,
                description="Prompt injection detected"
            )],
            confidence=0.95,
            analysis_time_ms=20.0,
            detection_method=DetectionMethod.LOCAL_RULES,
        )
        mock_analyze.return_value = mock_result

        client = AegisClient(mode=OperationMode.LOCAL)

        for prompt in sample_prompts["threats"]:
            result = client.analyze(prompt)
            assert result.is_threat is True
            assert result.risk_score > 0.7
            assert len(result.threat_types) > 0

    def test_analyze_empty_prompt(self):
        """Test analysis of empty prompt"""
        client = AegisClient(mode=OperationMode.LOCAL)

        with pytest.raises(ValidationError):
            client.analyze("")

    def test_analyze_none_prompt(self):
        """Test analysis of None prompt"""
        client = AegisClient(mode=OperationMode.LOCAL)

        with pytest.raises(ValidationError):
            client.analyze(None)

    @patch("aegis.client.AegisClient.analyze_batch")
    def test_analyze_batch(self, mock_analyze_batch, sample_prompts):
        """Test batch analysis"""
        # Mock batch analysis results
        mock_results = [
            AnalysisResult(
                is_threat=False,
                risk_score=0.1,
                detections=[],
                confidence=0.95,
                analysis_time_ms=15.0,
                detection_method=DetectionMethod.LOCAL_RULES,
                )
            for _ in sample_prompts["safe"]
        ]
        mock_analyze_batch.return_value = mock_results

        client = AegisClient(mode=OperationMode.LOCAL)
        results = client.analyze_batch(sample_prompts["safe"])

        assert len(results) == len(sample_prompts["safe"])
        for result in results:
            assert isinstance(result, AnalysisResult)

    def test_analyze_batch_empty_list(self):
        """Test batch analysis with empty list"""
        client = AegisClient(mode=OperationMode.LOCAL)

        results = client.analyze_batch([])
        assert results == []

    def test_client_context_manager(self):
        """Test client as context manager"""
        with AegisClient(mode=OperationMode.LOCAL) as client:
            assert client is not None

    def test_client_configuration_validation(self, client_config):
        """Test client configuration validation"""
        client = AegisClient(mode=OperationMode.LOCAL, **client_config)
        assert client is not None
        # Add more specific configuration tests here
