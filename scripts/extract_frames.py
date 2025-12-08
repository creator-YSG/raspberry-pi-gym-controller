import sys
import os
import glob
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QMovie, QImage
from PyQt5.QtCore import QByteArray, QBuffer, QIODevice

def extract_frames(video_path, output_dir):
    filename = os.path.basename(video_path).rsplit('.', 1)[0]
    print(f"Processing {filename}...")
    
    movie = QMovie(video_path)
    movie.setCacheMode(QMovie.CacheAll)
    
    if not movie.isValid():
        print(f"Invalid movie: {video_path}")
        return

    movie.start()
    frameCount = movie.frameCount()
    print(f"Frame count: {frameCount}")
    
    if frameCount <= 0:
        # Fallback for streams/files where frameCount isn't known
        # Try to rely on loop
        frameCount = 99999

    last_saved_data = None
    saved_count = 0
    
    for i in range(frameCount):
        if not movie.jumpToFrame(i):
            break
            
        image = movie.currentImage()
        if image.isNull():
            continue
            
        # Convert to PNG for comparison
        buffer = QBuffer()
        buffer.open(QIODevice.ReadWrite)
        image.save(buffer, "PNG")
        data = buffer.data()
        
        # Simple duplicate check
        is_duplicate = False
        if last_saved_data is not None:
            if data == last_saved_data:
                is_duplicate = True
        
        if not is_duplicate:
            out_path = os.path.join(output_dir, f"{filename}_frame_{i:04d}.png")
            # Write bytes to file
            with open(out_path, "wb") as f:
                f.write(data)
            last_saved_data = data
            saved_count += 1
            if saved_count % 10 == 0:
                print(f"Saved {saved_count} frames...")
            
    print(f"Finished {filename}: Saved {saved_count} frames.")

def main():
    # Use offscreen platform to avoid GUI requirement
    # We pass it in args if possible, but let's try standard argv first
    # actually QPA might vary.
    app = QApplication(sys.argv)
    
    docs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'docs')
    video_dir = os.path.join(docs_dir, 'videos')
    output_dir = os.path.join(docs_dir, 'extracted_screenshots')
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    videos = glob.glob(os.path.join(video_dir, "*.webp"))
    print(f"Found {len(videos)} videos in {video_dir}")
    
    for video in videos:
        extract_frames(video, output_dir)

if __name__ == "__main__":
    main()
