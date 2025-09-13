# This script downloads a YouTube video, transcribes it, and embeds the subtitles.
# It runs in a continuous loop, asking for a new URL after each task.
#
# Requires ffmpeg to be installed and available in the system's PATH.

import sys
import os
import tempfile
import subprocess
from pathlib import Path
import yt_dlp
from faster_whisper import WhisperModel
from pydub import AudioSegment

# --- Transcription Logic ---

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
        print(f"❌ Error: Transcriber could not find file at {video_path}", file=sys.stderr)
        return

    print(f"\n▶️ STEP 2: Starting transcription for: {video_path.name}")
    print("🔊 Extracting audio from video...")
    temp_audio_path = None
    try:
        audio_segment = AudioSegment.from_file(video_file, format=video_path.suffix.lstrip('.'))
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
            temp_audio_path, word_timestamps=True, vad_filter=True,
            vad_parameters=dict(min_speech_duration_ms=50, threshold=0.4),
            condition_on_previous_text=False, initial_prompt=verbatim_prompt
        )
        print(f"🌍 Detected language '{info.language}' with {info.language_probability:.2f} probability.")
        
        all_words = [word for segment in segments for word in segment.words]

        srt_counter, max_chars, max_pause_duration, line_buffer = 1, 45, 0.8, []
        if all_words:
            for i, word in enumerate(all_words):
                line_buffer.append(word)
                current_text = " ".join([w.word.strip() for w in line_buffer])
                is_last_word = (i == len(all_words) - 1)
                
                should_break = False
                if word.word.strip().endswith(('.', '?', '!')):
                    should_break = True
                elif not is_last_word and (all_words[i+1].start - word.end > max_pause_duration):
                    should_break = True
                elif len(current_text) > max_chars:
                    if not any(w.word.strip().endswith(('.', '?', '!')) for w in all_words[i+1:i+4]):
                        should_break = True
                
                if is_last_word or should_break:
                    start_time = format_timestamp(line_buffer[0].start)
                    end_time = format_timestamp(line_buffer[-1].end)
                    text = " ".join([w.word.strip() for w in line_buffer])
                    srt_content += f"{srt_counter}\n{start_time} --> {end_time}\n{text}\n\n"
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

# --- Subtitle Embedding Logic ---

def embed_subtitles(video_path: str, srt_path: str):
    """
    Embeds an SRT file into a video file as a soft subtitle track using ffmpeg.
    The original video is replaced with the subtitled version, and the SRT file is deleted.
    """
    video_p = Path(video_path)
    srt_p = Path(srt_path)
    output_p = video_p.with_name(f"{video_p.stem}_subtitled{video_p.suffix}")

    print(f"\n▶️ STEP 3: Embedding subtitles into {video_p.name}")
    command = [
        'ffmpeg', '-i', str(video_p), '-i', str(srt_p),
        '-c', 'copy', '-c:s', 'mov_text', '-metadata:s:s:0', 'language=eng',
        '-y', str(output_p)
    ]

    try:
        print("🔩 Running ffmpeg command...")
        subprocess.run(
            command, check=True, capture_output=True, text=True, encoding='utf-8'
        )
        print("✅ Subtitles embedded successfully.")
        os.remove(video_p)
        os.remove(srt_p)
        os.rename(output_p, video_p)
        print(f"✅ Final video saved to: {video_p}")
    except FileNotFoundError:
        print("\n❌ Error: 'ffmpeg' command not found.", file=sys.stderr)
        print("Please install ffmpeg and ensure it's in your system's PATH.", file=sys.stderr)
        if output_p.exists(): os.remove(output_p)
    except subprocess.CalledProcessError as e:
        print("\n❌ An error occurred while embedding subtitles with ffmpeg:", file=sys.stderr)
        print(f"FFmpeg stderr:\n{e.stderr}", file=sys.stderr)
        if output_p.exists(): os.remove(output_p)

# --- YouTube Download Logic ---

def download_video(url: str) -> str | None:
    """Downloads a YouTube video and returns the path to the final merged file."""
    print(f"▶️ STEP 1: Starting download for URL: {url}")
    
    def progress_hook(d):
        if d['status'] == 'downloading':
            progress_str = d.get('_percent_str', '  0.0%').strip()
            speed_str = d.get('_speed_str', 'N/A')
            print(f"\rDownloading: {progress_str} at {speed_str}", end='')
        elif d['status'] == 'finished':
             print("\nDownload finished, post-processing...")

    ydl_opts = {
        'format': 'bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': os.path.join('recordings', '%(title)s.%(ext)s'),
        'progress_hooks': [progress_hook], 'noplaylist': True, 'merge_output_format': 'mp4',
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            final_filepath = info_dict.get('filepath')
            if not final_filepath:
                 final_filepath = ydl.prepare_filename(info_dict)
            return final_filepath
    except yt_dlp.utils.DownloadError as e:
        print(f"\n❌ A download error occurred: {e}")
        return None
    except Exception as e:
        print(f"\n❌ An unexpected error occurred during download: {e}")
        return None

# --- Main Execution ---

if __name__ == "__main__":
    # Load the transcription model once at the very start to save time
    print(f"⚙️ Loading transcription model 'small'. Please wait...")
    try:
        transcription_model = WhisperModel("small", device="cpu", compute_type="int8")
        print("✅ Model loaded successfully.")
    except Exception as e:
        print(f"❌ Critical Error: Could not load the transcription model: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Main loop to process multiple videos until the program is closed
    while True:
        print("\n" + "="*60)
        print("🔗 Please paste a YouTube URL and press Enter to begin.")
        print("   (Type 'exit' or 'quit' to close the program)")
        url = input("URL: ").strip()

        if url.lower() in ['exit', 'quit']:
            print("👋 Exiting program. Goodbye!")
            break
        
        if not url:
            continue

        # Wrap the core logic in a try-except block to prevent a single failure
        # from crashing the entire program.
        try:
            # STEP 1: Download the video
            video_file = download_video(url)

            if video_file and os.path.exists(video_file):
                # STEP 2: Transcribe the downloaded video
                transcribe_video_final(video_file, model=transcription_model)
                
                # STEP 3: Embed the subtitles if the SRT file was created
                video_path = Path(video_file)
                srt_path = video_path.with_suffix(".srt")

                if srt_path.is_file():
                    embed_subtitles(str(video_path), str(srt_path))
                    print("\n🎉 Task complete. Ready for the next link.")
                else:
                    print("\n❌ Subtitle file was not created. Skipping embedding.")
            else:
                print(f"\n❌ Download failed. Please check the URL and your connection.")
        
        except Exception as e:
            print(f"\n❌ An unexpected error occurred during the process: {e}", file=sys.stderr)
            print("   Please try another link or restart the script.")
