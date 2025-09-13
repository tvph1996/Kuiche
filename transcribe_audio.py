# Save this code as transcribe_audio.py
import sys
import argparse
from pathlib import Path
from faster_whisper import WhisperModel

def transcribe_audio(audio_file: str, model: WhisperModel):
    """
    Transcribes an audio file and generates a well-formatted text file with paragraphs.
    """
    audio_path = Path(audio_file)
    if not audio_path.is_file():
        print(f"❌ Error: File not found at {audio_path}", file=sys.stderr)
        return

    print(f"\n▶️ Starting transcription for: {audio_path.name}")

    print("🤖 Transcribing... (This will take some time)")
    full_text = ""
    try:
        # We use word_timestamps=True to detect pauses between words,
        # which helps in structuring the text into natural sentences.
        segments, info = model.transcribe(
            str(audio_path),
            word_timestamps=True,
            vad_filter=True,
            vad_parameters=dict(min_speech_duration_ms=100)
        )

        print(f"🌍 Detected language '{info.language}' with {info.language_probability:.2f} probability.")

        all_words = []
        for segment in segments:
            if segment.words:
                all_words.extend(segment.words)

        if not all_words:
            print("⚠️ No speech detected in the audio.")
            return

        # --- Part 1: Group words into sentences based on punctuation and pauses ---
        sentences = []
        sentence_buffer = []
        # A pause of 0.7 seconds between words will also trigger a new sentence.
        max_pause_duration = 0.7

        for i, word in enumerate(all_words):
            sentence_buffer.append(word.word)
            word_text = word.word.strip()

            is_last_word = (i == len(all_words) - 1)
            next_word_starts_at = all_words[i+1].start if not is_last_word else 0

            # Conditions to end a sentence:
            # 1. The word ends with punctuation ('.', '?', '!').
            # 2. There is a long pause after the word.
            # 3. It's the last word of the entire transcription.
            if (
                word_text.endswith(('.', '?', '!')) or
                (not is_last_word and next_word_starts_at - word.end > max_pause_duration) or
                is_last_word
            ):
                # Join the words in the buffer to form a sentence.
                # .strip() cleans up any leading/trailing spaces.
                sentences.append("".join(sentence_buffer).strip())
                sentence_buffer = []

        # --- Part 2: Group sentences into paragraphs ---
        if sentences:
            paragraphs = []
            current_paragraph = []
            # You can adjust this number for longer or shorter paragraphs.
            sentences_per_paragraph = 5

            for i, sentence in enumerate(sentences):
                current_paragraph.append(sentence)
                # Create a new paragraph after a certain number of sentences
                # or if it's the very last sentence.
                if len(current_paragraph) >= sentences_per_paragraph or i == len(sentences) - 1:
                    paragraphs.append(" ".join(current_paragraph))
                    current_paragraph = []
            
            # Join paragraphs with two newlines for clear separation.
            full_text = "\n\n".join(paragraphs)

    except Exception as e:
        print(f"❌ An error occurred during transcription: {e}", file=sys.stderr)
        return

    # --- Part 3: Save the result to a .txt file ---
    if full_text:
        output_path = audio_path.with_suffix(".txt")
        output_path.write_text(full_text, encoding='utf-8')
        print("--- Transcription Complete ---")
        print(f"✅ Text file saved to: {output_path}")
    else:
        print("❌ Transcription failed or produced no output.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Transcribe one or more audio files to formatted text files."
    )
    parser.add_argument(
        "audio_paths",
        nargs="+",
        type=str,
        help="One or more paths to your audio files (e.g., input1.flac input2.wav)."
    )
    args = parser.parse_args()
    
    # You can change the model size. Options are: "tiny", "base", "small", "medium", "large-v3".
    # Larger models are more accurate but slower and use more memory.
    model_size = "small"
    print(f"⚙️ Loading model '{model_size}'... (This may take a moment on first run)")
    try:
        # Using "cpu" and "int8" is a good baseline for running on most computers.
        transcription_model = WhisperModel(model_size, device="cpu", compute_type="int8")
    except Exception as e:
        print(f"❌ Error loading model: {e}", file=sys.stderr)
        sys.exit(1)

    total_files = len(args.audio_paths)
    for i, audio_file_path in enumerate(args.audio_paths):
        print(f"\n{'='*20} Processing file {i+1} of {total_files} {'='*20}")
        transcribe_audio(audio_file_path, model=transcription_model)

    print("\n🎉 All files processed.")
