import requests
import json
import time
import subprocess

class ClientPlayer():
    def __init__(self, folder_id, api_key, media_path, refresh_time=60, ctrl_name='controller.txt'):
        self.folder_id = folder_id
        self.api_key = api_key
        self.media_path = media_path
        self.old_ctrl_md5Checksum = None
        self.old_video_md5Checksum = None
        self.refresh_time = refresh_time
        self.ctrl_name = ctrl_name
        self.files_query = f'https://www.googleapis.com/drive/v3/files?q=%27{self.folder_id}%27+in+parents&fields=files(id, md5Checksum,+originalFilename,%20+name)&key={self.api_key}'

    def play_content(self):

        vlc_ready = False
        while True:
            try:
                data_changed = False
                # read metadata from google drive
                response = json.loads(requests.get(self.files_query).content)
                files = response['files']

                # parse data about files
                file_map = {}
                for i, file in enumerate(files):
                    file_map[file['name']] = i

                # if controler changed download and play new content
                if files[file_map[self.ctrl_name]]['md5Checksum'] != self.old_ctrl_md5Checksum:

                    # read content of controller.txt and obtain selected video file id
                    ctrl_id = files[file_map[self.ctrl_name]]['id']
                    ctrl_download_url = f"https://drive.google.com/uc?id={ctrl_id}&export=download"
                    video_file_name = requests.get(ctrl_download_url).content.decode()
                    video_file_id = files[file_map[video_file_name]]['id']
                    video_download_url = f"https://drive.google.com/uc?id={video_file_id}&export=download"
                    data_changed = True
                
                # if currently played video changed download it again
                elif files[file_map[video_file_name]]['md5Checksum'] != self.old_video_md5Checksum:
                    data_changed = True

                if data_changed:
                    # download the selected video and save to disk
                    response = requests.get(video_download_url, stream=True)
                    with open(self.media_path, mode="wb") as f:
                        for chunk in response.iter_content(chunk_size=10 * 1024):
                            f.write(chunk)
                    
                    # remeber that what files are you playing
                    self.old_video_md5Checksum = files[file_map[video_file_name]]['md5Checksum']
                    self.old_ctrl_md5Checksum = files[file_map[self.ctrl_name]]['md5Checksum']
                    
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
            except:
                print("Check internet connection please, something is wrong")
                time.sleep(5)