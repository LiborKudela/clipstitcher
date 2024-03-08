import requests
import json
import time
import subprocess
from tqdm import tqdm

class ClientPlayer():
    def __init__(self, controller_id, media_path, refresh_time=60):
        self.ctrl_id = controller_id
        self.old_ctrl_data = [None, None, None]
        self.media_path = media_path
        self.refresh_time = refresh_time

    def play_content(self):

        vlc_ready = False
        while True:
            try:
                data_changed = False
                # read metadata from google drive
                ctrl_download_url = f"https://drive.google.com/uc?id={self.ctrl_id}&export=download"
                ctrl_content = requests.get(ctrl_download_url).content.decode()
                ctrl_data = dict(zip(['file_name', 'file_id', 'file_hash'], ctrl_content.split(';')))

                # if controller changed download and play new content
                if ctrl_data != self.old_ctrl_data:

                    # get url of the requested video
                    video_file_id = ctrl_data['file_id']
                    video_file_name = ctrl_data['file_name']
                    video_download_url = f"https://drive.google.com/uc?id={video_file_id}&export=download"

                    # download the video
                    response = requests.get(video_download_url, stream=True)
                    total_size = int(response.headers.get('content-length', 0))
                    with open(self.media_path, mode="wb") as f:
                        progress_bar = tqdm(total=total_size, unit='B', unit_scale=True, unit_divisor=1024, desc=f"Downloading {video_file_name}", miniters=1)
                        for chunk in response.iter_content(chunk_size=10*1024):
                            f.write(chunk)
                            progress_bar.update(len(chunk))
                        progress_bar.close()
                    
                    # remember what files are you playing
                    self.old_ctrl_data = ctrl_data.copy()
                    
                    # start new video loop
                    print(f"Playing: {video_file_name}")
                    if not vlc_ready:
                        cmd = [
                            'cvlc',
                            self.media_path,
                            '--loop',
                            '--fullscreen',
                            '--no-video-title-show'] 
                        p = subprocess.Popen(cmd)
                        vlc_ready = True

                # wait 60s till next sync
                time.sleep(self.refresh_time)
            except Exception as e:
                print("Check internet connection please, cannot access controller")
                print(e)
                time.sleep(5)