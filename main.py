import os
import requests
import asyncio
import edge_tts
import google.generativeai as genai
from moviepy.editor import *
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Configuration
GEMINI_API_KEY = os.environ['GEMINI_API_KEY']
PEXELS_API_KEY = os.environ['PEXELS_API_KEY']
YOUTUBE_CLIENT_ID = os.environ['YOUTUBE_CLIENT_ID']
YOUTUBE_CLIENT_SECRET = os.environ['YOUTUBE_CLIENT_SECRET']
YOUTUBE_REFRESH_TOKEN = os.environ['YOUTUBE_REFRESH_TOKEN']

# Step 1 - Get trending AI topic
def get_trending_topic():
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content(
        "Give me ONE trending AI or technology topic that is popular in the USA right now in 2026. "
        "Return ONLY the topic name, nothing else. Example: ChatGPT Voice Mode"
    )
    return response.text.strip()

# Step 2 - Generate script
def generate_script(topic):
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content(
        f"You are a YouTube scriptwriter for a faceless AI & Technology tutorials channel called Visiq AI, targeting a US audience aged 18-35. "
        f"Write a 3-minute script about: {topic}. "
        f"Structure: Hook (10 seconds shocking fact), Problem (30 seconds), Tutorial (2 minutes step by step), CTA (20 seconds subscribe). "
        f"Keep language simple and conversational. Return ONLY the script text."
    )
    return response.text.strip()

# Step 3 - Generate voiceover
async def generate_voiceover(script, output_file):
    communicate = edge_tts.Communicate(script, voice="en-US-ChristopherNeural")
    await communicate.save(output_file)

# Step 4 - Get stock footage from Pexels
def get_stock_footage(topic, num_videos=5):
    headers = {"Authorization": PEXELS_API_KEY}
    search_query = topic.split()[0] + " technology"
    url = f"https://api.pexels.com/videos/search?query={search_query}&per_page={num_videos}&orientation=landscape"
    response = requests.get(url, headers=headers)
    data = response.json()
    video_files = []
    for video in data.get('videos', [])[:num_videos]:
        video_url = video['video_files'][0]['link']
        video_path = f"footage_{len(video_files)}.mp4"
        r = requests.get(video_url, stream=True)
        with open(video_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        video_files.append(video_path)
    return video_files

# Step 5 - Assemble video
def assemble_video(footage_files, audio_file, output_file):
    audio = AudioFileClip(audio_file)
    total_duration = audio.duration
    clips = []
    duration_per_clip = total_duration / len(footage_files)
    for footage in footage_files:
        clip = VideoFileClip(footage).subclip(0, min(duration_per_clip, VideoFileClip(footage).duration))
        clip = clip.resize((1920, 1080))
        clips.append(clip)
    final_video = concatenate_videoclips(clips, method="compose")
    final_video = final_video.subclip(0, total_duration)
    final_video = final_video.set_audio(audio)
    final_video.write_videofile(output_file, fps=24, codec='libx264', audio_codec='aac')

# Step 6 - Generate title and description
def generate_metadata(topic):
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content(
        f"Generate YouTube metadata for a video about {topic} for the channel Visiq AI. "
        f"Return in this exact format:\n"
        f"TITLE: (catchy title under 60 chars)\n"
        f"DESCRIPTION: (150 word description with keywords)\n"
        f"TAGS: (10 comma separated tags)"
    )
    lines = response.text.strip().split('\n')
    title = lines[0].replace('TITLE:', '').strip()
    description = lines[1].replace('DESCRIPTION:', '').strip()
    tags = lines[2].replace('TAGS:', '').strip().split(',')
    return title, description, tags

# Step 7 - Upload to YouTube
def upload_to_youtube(video_file, title, description, tags):
    credentials = Credentials(
        token=None,
        refresh_token=YOUTUBE_REFRESH_TOKEN,
        client_id=YOUTUBE_CLIENT_ID,
        client_secret=YOUTUBE_CLIENT_SECRET,
        token_uri='https://oauth2.googleapis.com/token'
    )
    youtube = build('youtube', 'v3', credentials=credentials)
    request = youtube.videos().insert(
        part='snippet,status',
        body={
            'snippet': {
                'title': title,
                'description': description,
                'tags': tags,
                'categoryId': '28'
            },
            'status': {
                'privacyStatus': 'public'
            }
        },
        media_body=MediaFileUpload(video_file, chunksize=-1, resumable=True)
    )
    response = request.execute()
    print(f"Video uploaded! ID: {response['id']}")
    return response['id']

# Main pipeline
def main():
    print("Starting Visiq AI automation...")
    
    print("Step 1: Getting trending topic...")
    topic = get_trending_topic()
    print(f"Topic: {topic}")
    
    print("Step 2: Generating script...")
    script = generate_script(topic)
    print("Script generated!")
    
    print("Step 3: Generating voiceover...")
    asyncio.run(generate_voiceover(script, "voiceover.mp3"))
    print("Voiceover done!")
    
    print("Step 4: Getting stock footage...")
    footage_files = get_stock_footage(topic)
    print(f"Downloaded {len(footage_files)} footage clips!")
    
    print("Step 5: Assembling video...")
    assemble_video(footage_files, "voiceover.mp3", "final_video.mp4")
    print("Video assembled!")
    
    print("Step 6: Generating metadata...")
    title, description, tags = generate_metadata(topic)
    print(f"Title: {title}")
    
    print("Step 7: Uploading to YouTube...")
    video_id = upload_to_youtube("final_video.mp4", title, description, tags)
    print(f"Success! Video live at: https://youtube.com/watch?v={video_id}")

if __name__ == "__main__":
    main()
