import pysrt
import translators as ts
import sys
import os
import re
import time
from datetime import datetime

def translate_srt_file_resilient(input_file, output_file, target_language='vi', batch_size=20):
    """
    Translates an SRT file using a highly resilient numbered-list batching method.
    This version includes a more flexible parser to handle reformatting by translation services.
    """
    if not os.path.exists(input_file):
        print(f"Error: The file '{input_file}' was not found.")
        return

    try:
        subs = pysrt.open(input_file, encoding='utf-8')
        total_subs = len(subs)
        
        print(f"File found: '{input_file}'")
        print(f"Translating {total_subs} entries to Vietnamese using resilient numbered batches...")
        
        start_time = datetime.now()
        
        translation_engines = ['google', 'bing']
        
        for i in range(0, total_subs, batch_size):
            batch = subs[i:i + batch_size]
            batch_translated = False
            
            # Format the batch as a numbered list. Example: "0_> Text 1\n1_> Text 2"
            numbered_texts = [f"{j}_> {sub.text}" for j, sub in enumerate(batch)]
            text_to_translate = "\n".join(numbered_texts)

            for engine in translation_engines:
                try:
                    translated_block = ts.translate_text(text_to_translate, translator=engine, to_language=target_language)
                    
                    # --- START: IMPROVED PARSING LOGIC ---
                    translated_lines_dict = {}
                    current_index = -1
                    current_text_lines = []
                    
                    # This regex is more flexible, allowing for different separators like '>', '.', ':', or '-'
                    # and variations in spacing.
                    pattern = re.compile(r'^\s*(\d+)\s*[_>.:-]\s*(.*)')

                    for line in translated_block.split('\n'):
                        match = pattern.match(line)
                        if match:
                            # If a new marker is found, save the previously collected text
                            if current_index != -1:
                                translated_lines_dict[current_index] = "\n".join(current_text_lines).strip()
                            
                            # Start collecting text for the new index
                            current_index = int(match.group(1))
                            current_text_lines = [match.group(2).strip()]
                        elif current_index != -1:
                            # This line is a continuation of the previous subtitle's text
                            current_text_lines.append(line.strip())
                    
                    # Save the last collected subtitle text after the loop finishes
                    if current_index != -1:
                        translated_lines_dict[current_index] = "\n".join(current_text_lines).strip()
                    # --- END: IMPROVED PARSING LOGIC ---

                    # Integrity check: Did we get all our lines back?
                    if len(translated_lines_dict) != len(batch):
                        print(f"\n\n--- DEBUG: BATCH MISMATCH on engine '{engine}' ---")
                        print(f"Expected {len(batch)} subtitles, but parsed {len(translated_lines_dict)}.")
                        print("--- Original Numbered Text Sent ---")
                        print(text_to_translate)
                        print("\n--- Raw Translated Block Received ---")
                        print(translated_block)
                        print("--- Parsed Dictionary ---")
                        print(translated_lines_dict)
                        print("-------------------------------------------\n")
                        raise ValueError(f"Mismatched line count in batch. Expected {len(batch)}, got {len(translated_lines_dict)}")

                    # Reassemble the batch in the correct order
                    for j, sub in enumerate(batch):
                        # Use .get() to avoid errors if an index is somehow still missing
                        # and fall back to original text.
                        sub.text = translated_lines_dict.get(j, sub.text)

                    batch_translated = True
                    print(f"\nBatch {int(i/batch_size)+1} translated successfully with '{engine}'.")
                    break # Success, move to the next batch

                except Exception as e:
                    print(f"\nWarning: Batch {int(i/batch_size)+1} failed with '{engine}' engine. Error: {e}. Trying next engine...")
            
            # Fallback for if all engines fail on a batch
            if not batch_translated:
                print(f"\nWarning: All engines failed for batch {int(i/batch_size)+1}. Translating line-by-line as a final fallback.")
                for sub_index, sub in enumerate(batch):
                    try:
                        sub.text = ts.translate_text(sub.text, translator='google', to_language=target_language)
                    except Exception as line_e:
                        print(f"Could not translate line {i+sub_index+1}: '{sub.text}'. Error: {line_e}")

            # Update progress bar
            processed_count = min(i + batch_size, total_subs)
            progress = processed_count / total_subs * 100
            sys.stdout.write(f"\rProgress: [{'#' * int(progress / 2):<50}] {progress:.2f}%")
            sys.stdout.flush()
            
            time.sleep(0.2) # Increased delay slightly to be safer

        subs.save(output_file, encoding='utf-8')
        
        end_time = datetime.now()
        duration = end_time - start_time
        
        print(f"\n\nTranslation complete!")
        print(f"Translated file saved as: '{output_file}'")
        print(f"Total time taken: {duration.total_seconds():.2f} seconds")

    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python translate_srt.py <path_to_your_file.srt>")
        sys.exit(1)

    input_filename = sys.argv[1]
    base, ext = os.path.splitext(input_filename)
    output_filename = f"{base}_vi.srt"

    translate_srt_file_resilient(input_filename, output_filename)   
