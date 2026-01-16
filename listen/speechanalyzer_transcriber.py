"""
Apple SpeechAnalyzer transcriber for macOS 26+.
Uses Apple's native on-device speech recognition via CLI wrapper.
"""

import numpy as np
import subprocess
import tempfile
import os
import shutil
from typing import Optional
from pathlib import Path

from .transcriber_base import BaseTranscriber, TranscriptionResult


class SpeechAnalyzerTranscriber(BaseTranscriber):
    """
    Speech-to-text transcription using Apple SpeechAnalyzer (macOS 26+).

    Requires the apple-speechanalyzer-cli binary to be built and available.
    Zero external dependencies - uses Apple's built-in speech models.
    """

    # Default path for the CLI binary
    DEFAULT_CLI_PATH = Path.home() / ".mcp-claude-say" / "bin" / "apple-speechanalyzer-cli"

    def __init__(
        self,
        cli_path: Optional[str] = None,
        locale: str = "en-US",
    ):
        """
        Initialize SpeechAnalyzer transcriber.

        Args:
            cli_path: Path to apple-speechanalyzer-cli binary.
                      Defaults to ~/.mcp-claude-say/bin/apple-speechanalyzer-cli
            locale: Locale for transcription (e.g., "en-US", "fr-FR")
        """
        self.cli_path = Path(cli_path) if cli_path else self.DEFAULT_CLI_PATH
        self.locale = locale
        self._verified = False

    def _verify_cli(self) -> bool:
        """Verify the CLI binary exists and is executable."""
        if self._verified:
            return True

        if not self.cli_path.exists():
            raise FileNotFoundError(
                f"SpeechAnalyzer CLI not found at {self.cli_path}. "
                f"Build it with: cd speechanalyzer-cli && swift build -c release"
            )

        if not os.access(self.cli_path, os.X_OK):
            raise PermissionError(
                f"SpeechAnalyzer CLI is not executable: {self.cli_path}"
            )

        self._verified = True
        return True

    def transcribe(
        self,
        audio: np.ndarray,
        language: Optional[str] = None,
    ) -> TranscriptionResult:
        """
        Transcribe audio to text using Apple SpeechAnalyzer.

        Args:
            audio: Audio data (float32, 16kHz, mono)
            language: Language/locale code (e.g., "en-US", "fr-FR")

        Returns:
            TranscriptionResult with text, detected language, and confidence
        """
        if len(audio) == 0:
            return TranscriptionResult(text="", language="", confidence=0.0)

        self._verify_cli()

        # Ensure correct dtype
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        # Normalize if needed
        if np.abs(audio).max() > 1.0:
            audio = audio / np.abs(audio).max()

        # Create temp files for input/output
        import soundfile as sf

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as audio_file:
            audio_path = audio_file.name

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as output_file:
            output_path = output_file.name

        try:
            # Write audio to temp file
            sf.write(audio_path, audio, self.SAMPLE_RATE)

            # Determine locale
            locale = language if language else self.locale

            # Call the CLI
            result = subprocess.run(
                [
                    str(self.cli_path),
                    "--input-audio-path", audio_path,
                    "--output-txt-path", output_path,
                    "--locale", locale,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                # Log error but don't fail - return empty result
                import sys
                print(f"SpeechAnalyzer error: {result.stderr}", file=sys.stderr)
                return TranscriptionResult(text="", language=locale, confidence=0.0)

            # Read transcription result
            with open(output_path, "r", encoding="utf-8") as f:
                text = f.read().strip()

            return TranscriptionResult(
                text=text,
                language=locale,
                confidence=0.95,  # SpeechAnalyzer doesn't provide confidence
            )

        except subprocess.TimeoutExpired:
            return TranscriptionResult(text="", language=self.locale, confidence=0.0)

        finally:
            # Cleanup temp files
            for path in [audio_path, output_path]:
                if os.path.exists(path):
                    os.unlink(path)

    def transcribe_streaming(
        self,
        audio: np.ndarray,
        language: Optional[str] = None,
    ) -> TranscriptionResult:
        """
        Streaming transcription (uses same method - SpeechAnalyzer is fast).
        """
        return self.transcribe(audio, language)

    @property
    def name(self) -> str:
        return "speechanalyzer"

    @property
    def supports_streaming(self) -> bool:
        return True


# Singleton instance
_transcriber: Optional[SpeechAnalyzerTranscriber] = None


def get_speechanalyzer_transcriber(
    locale: str = "en-US",
) -> SpeechAnalyzerTranscriber:
    """Get or create the global SpeechAnalyzerTranscriber instance."""
    global _transcriber
    if _transcriber is None:
        _transcriber = SpeechAnalyzerTranscriber(locale=locale)
    return _transcriber


def is_speechanalyzer_available() -> bool:
    """Check if SpeechAnalyzer is available on this system."""
    # Check macOS version
    import platform
    if platform.system() != "Darwin":
        return False

    # Check macOS 26+
    try:
        version = platform.mac_ver()[0]
        major = int(version.split(".")[0])
        if major < 26:
            return False
    except (ValueError, IndexError):
        return False

    # Check CLI exists
    cli_path = SpeechAnalyzerTranscriber.DEFAULT_CLI_PATH
    return cli_path.exists() and os.access(cli_path, os.X_OK)
