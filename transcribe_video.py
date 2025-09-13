# Save this code as transcribe_video.py
import sys
import argparse
from pathlib import Path
from faster_whisper import WhisperModel
from pydub import AudioSegment
import tempfile
import os

def format_timestamp(seconds: float) -> str:
    """Converts seconds into the SRT timestamp format HH:MM:SS,ms."""
    assert seconds >= 0, "non-negative timestamp expected"
    milliseconds = round(seconds * 1000.0)
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    seconds, milliseconds = divmod(milliseconds, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

def transcribe_video_final(video_file: str, model: WhisperModel):
    """
    Transcribes a video file and generates a grammatically-aware,
    word-level synchronized SRT subtitle file.
    """
    video_path = Path(video_file)
    if not video_path.is_file():
        print(f"❌ Error: File not found at {video_path}", file=sys.stderr)
        return

    print(f"\n▶️ Starting transcription for: {video_path.name}")

    print("🔊 Extracting audio from video...")
    temp_audio_path = None
    try:
        audio_segment = AudioSegment.from_file(video_path, format=video_path.suffix.lstrip('.'))
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_audio_file:
            temp_audio_path = tmp_audio_file.name
            audio_segment.export(temp_audio_path, format="wav", parameters=["-ar", "16000", "-ac", "1"])
    except Exception as e:
        print(f"❌ Error extracting audio from {video_path.name}: {e}", file=sys.stderr)
        if temp_audio_path and os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)
        return

    print("🤖 Transcribing... (This will take some time)")
    srt_content = ""
    try:
        verbatim_prompt = "The following is a raw, verbatim transcription, including all filler words like 'uhm' and 'ah'."
        
        segments, info = model.transcribe(
            temp_audio_path,
            word_timestamps=True,
            vad_filter=True,
            vad_parameters=dict(min_speech_duration_ms=50, threshold=0.4),
            condition_on_previous_text=False,
            initial_prompt=verbatim_prompt
        )
        
        print(f"🌍 Detected language '{info.language}' with {info.language_probability:.2f} probability.")
        print(f"🕒 Estimated audio duration for transcription: {format_timestamp(info.duration)}")
        
        all_words = []
        for segment in segments:
            all_words.extend(segment.words)

        srt_counter = 1
        max_chars = 45
        max_pause_duration = 0.8
        line_buffer = []

        if all_words:
            for i, word in enumerate(all_words):
                line_buffer.append(word)
                current_text = " ".join([w.word.strip() for w in line_buffer])
                is_last_word_overall = (i == len(all_words) - 1)
                
                should_break = False
                word_text = word.word.strip()

                if word_text.endswith(('.', '?', '!')):
                    should_break = True
                elif not is_last_word_overall and (all_words[i+1].start - word.end > max_pause_duration):
                    should_break = True
                elif len(current_text) > max_chars:
                    found_punctuation_ahead = False
                    for j in range(1, 4):
                        if (i + j) < len(all_words):
                            next_word_text = all_words[i+j].word.strip()
                            if next_word_text.endswith(('.', '?', '!')):
                                found_punctuation_ahead = True
                                break
                    
                    if not found_punctuation_ahead:
                        should_break = True
                
                if is_last_word_overall or should_break:
                    start_time = format_timestamp(line_buffer[0].start)
                    end_time = format_timestamp(line_buffer[-1].end)
                    text_to_write = " ".join([w.word.strip() for w in line_buffer])
                    
                    srt_content += f"{srt_counter}\n"
                    srt_content += f"{start_time} --> {end_time}\n"
                    srt_content += f"{text_to_write}\n\n"
                    srt_counter += 1
                    line_buffer = []
    finally:
        if temp_audio_path and os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)

    if srt_content:
        output_path = video_path.with_suffix(".srt")
        output_path.write_text(srt_content, encoding='utf-8')
        print("--- Transcription Complete ---")
        print(f"✅ Subtitle file saved to: {output_path}")
    else:
        print("❌ Transcription failed or produced no output.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Transcribe one or more videos to SRT files with multi-language support."
    )
    parser.add_argument(
        "video_paths",
        nargs="+",
        type=str,
        help="One or more paths to your video files (e.g., input1.mp4 input2.mkv)."
    )
    args = parser.parse_args()
    
    model_size = "small"
    print(f"⚙️ Loading model '{model_size}'... (This may take a moment on first run)")
    try:
        transcription_model = WhisperModel(model_size, device="cpu", compute_type="int8")
    except Exception as e:
        print(f"❌ Error loading model: {e}", file=sys.stderr)
        sys.exit(1)

    # --- THIS LINE IS NOW FIXED ---
    total_files = len(args.video_paths)
    for i, video_file_path in enumerate(args.video_paths):
        print(f"\n{'='*20} Processing file {i+1} of {total_files} {'='*20}")
        transcribe_video_final(video_file_path, model=transcription_model)

    print("\n🎉 All files processed.")
