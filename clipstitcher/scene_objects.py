import cv2
import textwrap
from typing import List
import os
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
import time
import random
import numpy as np
from tqdm import tqdm
import importlib.resources
import hashlib
import json
import threading
import subprocess as sp
from .host_sync import Uploader

class DefaultOptions:
    def __init__(self):
        self.fill_color = [255, 255, 255]
        self.background_color = [255, 255, 255]
        self.core_thread_count = 4
        self.resolution = (1920, 1080)
        self.ffmpeg_win = '.\\ffmpeg_tool\\bin\\ffmpeg.exe'
        self.client_secrets = 'client_secrets.json'

default_options = DefaultOptions()

with importlib.resources.path("clipstitcher", "styles.css") as p:
    html_style_path = p

def resize_to_fit_screen(frame, screen, fill_color=default_options.fill_color):
    frame_a = frame.shape[1]/frame.shape[0]
    screen_a = screen[0]/screen[1]
    #TODO: make the bellow chunk nicer
    if frame.shape[1] != screen[0] or frame.shape[0] != screen[1]:
        if frame_a > screen_a:
            w_a = screen[0]/frame.shape[1]
            new_size = (int(frame.shape[1]*w_a), int(frame.shape[0]*w_a))
            frame = cv2.resize(frame, new_size, interpolation = cv2.INTER_AREA)
            border_1 = int((screen[1] - frame.shape[0])/2)
            border_2 = screen[1] -frame.shape[0]- border_1
            frame = cv2.copyMakeBorder(frame, border_1, border_2, 0, 0, borderType=cv2.BORDER_CONSTANT, value=fill_color)
        elif frame_a < screen_a:
            h_a = screen[1]/frame.shape[0]
            new_size = (int(frame.shape[1]*h_a), int(frame.shape[0]*h_a))
            frame = cv2.resize(frame, new_size, interpolation = cv2.INTER_AREA)
            border_1 = int((screen[0] - frame.shape[1])/2)
            border_2 = screen[0] -frame.shape[1] - border_1
            frame = cv2.copyMakeBorder(frame, 0, 0, border_1, border_2, borderType=cv2.BORDER_CONSTANT, value=fill_color)
        else:
            frame = cv2.resize(frame, screen, interpolation = cv2.INTER_AREA)
    return frame

def find_screen(overlay, screen_color = [0, 255, 0]):
    overlay_hsv = cv2.cvtColor(overlay, cv2.COLOR_RGB2HSV)
    screen_color = np.uint8([[screen_color]])
    hsv_screen_color = cv2.cvtColor(screen_color, cv2.COLOR_RGB2HSV)[0][0]
    mask = cv2.inRange(overlay_hsv, hsv_screen_color, hsv_screen_color)
    mask_flip = cv2.flip(cv2.flip(mask, 0), 1)
    _, _, _, top_left = cv2.minMaxLoc(mask)
    _, _, _, max_loc = cv2.minMaxLoc(mask_flip)
    bottom_right = (mask.shape[1] - max_loc[0], mask.shape[0] - max_loc[1])
    return top_left, bottom_right

def ffmpeg_concatenate(files, out="merge.mp4"):
   
    # write content to ffmpeg input file
    i = "concat_files.txt"
    with open("concat_files.txt", "w") as txtf:
        for f in files:
            txtf.write("file {} \n".format(f))
    
    # run ffmpeg
    if os.name =='posix':
        ffmpeg_executable = 'ffmpeg'
    elif os.name == 'nt':
        ffmpeg_executable = default_options.ffmpeg_win
    cmd = f"{ffmpeg_executable} -y -loglevel error -f concat -safe 0 -i {i} -vcodec copy {out}"
    sp.Popen(cmd, shell=True).wait()
    
    # remove input file
    os.remove(i)

       
class Scene_object:
    def __init__(self, screen=default_options.resolution, fill_color=[255, 255, 255]):
        self.window = "main window"
        self.size = screen
        self.fill_color = fill_color
        self.static = False
        self.threadLock = threading.Lock()
        self.temp_output = "chunk_{}.mp4"

    def get_children(self):
        return None

    def is_static(self):
        return self.static

    def total_frames(self):
        "Returns total number of frames in the scene"
        pass

    def render_serial(self, start=0, stop=None, output=None):
        "This method renders a scene into a video file given in path output"
        if output is None:
            output = self.output
        if stop is None:
            stop = self.total_frames() - 1
        codec = cv2.VideoWriter_fourcc('m', 'p', '4', 'v')
        fps = 24
        video_writter = cv2.VideoWriter(output, codec, fps, self.size, True)
        total_frames = stop - start
        for frame in self.get_frames(start, stop):
            frame = resize_to_fit_screen(frame, self.size)
            video_writter.write(frame)
            with self.threadLock:
                self.frames_processed += 1
        video_writter.release()

    def render(self, start=0, stop=None, threads=1, output=None):
        "This method renders the scene into a video file"
        
        # resolve output video filename
        if output is None:
            output = self.output
        
        # resolve chunks and their size
        if stop is None:
            stop = self.total_frames() - 1
        total_frames = stop - start
        chunk_size = int((stop-start)/threads)

        # generate and start render threads
        self.frames_processed = 0
        render_threads = []
        chunk_files = [self.temp_output.format(i) for i in range(threads)]
        for i in range(threads):
            kwargs = {
                "start": start + chunk_size*i, 
                "stop": min(start + chunk_size*(i+1), total_frames), 
                "output": chunk_files[i]}
            t = threading.Thread(target=self.render_serial, kwargs=kwargs)
            render_threads.append(t)
            t.start()
        
        # updating progress bar and waiting for video chunks
        with tqdm(total=self.total_frames()) as pbar:
            processing = True
            while processing:
                time.sleep(0.2)
                pbar.update(self.frames_processed - pbar.n)
                processing = any([t.is_alive() for t in render_threads])
        pbar.update(self.frames_processed - pbar.n)
        
        # concatenate chunks into one video 
        ffmpeg_concatenate(chunk_files, out=output)
        
        # remove video chunk files
        for cf in chunk_files:
            os.remove(cf)
        
    def play(self, start=0, stop=None):
        "This method plays the scene in opencv window (as fast as possible)"
        if stop is None:
            stop = self.total_frames() - 1
            
        cv2.namedWindow("main window")
        cv2.resizeWindow("main window", width=self.size[0], height=self.size[1])
        for frame in tqdm(self.get_frames(start, stop), total=stop - start):
            frame = resize_to_fit_screen(frame, self.size)
            cv2.imshow("main window", frame)

            # quit window playing
            pressed_key = cv2.waitKey(1) & 0xFF
            if pressed_key == ord('q'):  # quit all play/render
                break
        cv2.destroyAllWindows()

    def get_hash_id(self):
        m = hashlib.sha256()
        d_str = json.dumps(self.__dict__)
        m.update(d_str.encode('UTF-8'))
        return m.hexdigest()
    
    def get_file_hash(self):
        """"This function returns the SHA-1 hash
        of the file passed into it"""

        # make a hash object
        h = hashlib.sha1()

        # open file for reading in binary mode
        with open(self.output, 'rb') as file:

            # loop till the end of the file
            chunk = 0
            while chunk != b'':
                # read only 1024 bytes at a time
                chunk = file.read(1024)
                h.update(chunk)

        # return the hex representation of digest
        return h.hexdigest()
    
    def update_broadcast(self, folder_id):

        # create instance of uploader
        if not hasattr(self, 'uploader'):
            self.uploader = Uploader(default_options.client_secrets)

        # upload video and get metadata for controller
        file_id = self.uploader.upload_file(self.output, folder_id)
        file_name = os.path.split(self.output)[1]
        file_hash = self.get_file_hash()
       

        # update controller
        with open('controller.txt', 'w') as cf:
            ctrl = f'{file_name};{file_id};{file_hash}'
            cf.write(ctrl)
        self.uploader.upload_file('controller.txt', folder_id)

    def upload_linux_rsync(self, user=None, ip=None, folder=None):
        # not tested
        assert(user is not None and ip is not None and folder is not None)
        os.system(f'rsync  -v --progress {self.output} {user}@{ip}:{folder}/{self.output}')


class Image(Scene_object):
    def __init__(self, filepath, duration=5, background_color=default_options.background_color):
        self.output = "image.mp4"
        self.duration = duration
        self.img = cv2.imread(filepath, cv2.IMREAD_UNCHANGED)
        if self.img.shape[2] == 4: # has transparency channel?
            trans_mask = self.img[:,:,3] == 0
            self.img[trans_mask] = background_color + [255]
        self.img = cv2.cvtColor(self.img, cv2.COLOR_BGRA2BGR)
        super().__init__()
        self.static = True

    def get_children(self):
        return self.img

    def get_frames(self, start=0, stop=None):
        if stop is None:
            stop = self.total_frames() - 1
        for i in range(start, stop):
            yield self.img

    def total_frames(self):
        return self.duration*24

class Html_page(Scene_object):
    def __init__(self, html_str=None, html_url=None, html_file=None, duration=5,
                 actions=[]):
        self.duration = duration
        if html_url is not None:
            self.img = self.url_to_image(html_url)
        if html_file is not None:
            self.img = self.file_to_image(html_file)
        elif html_str is not None:
            self.img = self.html_str_to_image(html_str)
        self.output = "html_page.mp4"
        super().__init__()
        self.static = True

    def get_children(self):
        return self.img

    def url_to_image(self, url):
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--window-size={},{}".format(*default_options.resolution))
        options.add_argument("--hide-scrollbars")
        options.add_argument(f"--force-device-scale-factor={2.0}")
        driver = webdriver.Chrome(options=options)
        driver.get(url)
        time.sleep(2)
        driver.get_screenshot_as_file("screenshot.png")
        driver.quit()
        img = cv2.imread("screenshot.png")
        return img

    def file_to_image(self, file):
        file = "file://" + os.path.abspath(file)
        return self.url_to_image(file)

    def html_str_to_image(self, html_str):
        url = "data:text/html;charset=utf-8," + html_str
        temp_file = "temp_web_page.html"
        with open(temp_file, "w", encoding='utf-8') as f:
           f.write(html_str)
        return self.file_to_image(temp_file)
        #return self.url_to_image(url)
    
    def get_frames(self, start=0, stop=None):
        if stop is None:
            stop = self.total_frames() - 1
        for i in range(start, stop):
            yield self.img

    def total_frames(self):
        return self.duration*24

class Tweet(Html_page):

    def __init__(self, tweet_url, duration=5):
        self.tweet_url = tweet_url
        res = requests.get(f"https://publish.twitter.com/oembed?url={tweet_url}")
        html_str = self.embed_to_html(res.json()["html"])
        super().__init__(html_str=html_str, duration=duration)
        self.output = "tweet.mp4"

    def embed_to_html(self, embed_code):
        code = f"""
                <!DOCTYPE html>
                <html>
                <head>
                  <link rel="stylesheet" href="{html_style_path}">
                </head>
                <body>
                    <div class="center">{embed_code}</div>
                </body>
                </html>"""
        return textwrap.dedent(code)

def load_tweets_from_file(path, duration=5):
    tweets = []
    with open(path, 'r') as f:
        lines = f.readlines()
    for line in lines:
        if (line[0:15] == "https://twitter"):
            tweets.append(Tweet(line, duration))
    return tweets

class Video(Scene_object):

    def __init__(self, file):
        self.file = file
        self.output = "video.mp4"
        cap = cv2.VideoCapture(self.file)
        self.n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
        super().__init__()

    def get_children(self):
        return self.file

    def get_frames(self, start=0, stop=None):
        cap = cv2.VideoCapture(self.file)
        cap.set(1, start)
        if stop is None:
            stop = self.total_frames() - 1
        for i in range(start, stop):
            ret, frame = cap.read()
            yield frame
        cap.release()

    def total_frames(self):
        return self.n_frames

def load_videos_from_folder(folder):
    file_paths = os.listdir(folder)
    videos = []
    for path in file_paths:
        videos.append(Video(os.path.join(folder, path)))
    return videos

class Overlay(Scene_object):
    def __init__(self, scene, overlay, screen_color = [0, 255, 0]):
        self.scene = scene
        self.output = "overlay.mp4"
        self.overlay = cv2.imread(overlay)
        self.top_left, self.bottom_right = find_screen(self.overlay, screen_color)
        self.embed_scene_frame(list(self.scene.get_frames(0,1))[0]) #TODO: make method for this
        super().__init__()

    def get_children(self):
        return self.scene

    def embed_scene_frame(self, frame):
        screen = (self.bottom_right[0] - self.top_left[0], self.bottom_right[1] - self.top_left[1])
        frame = resize_to_fit_screen(frame, screen)
        overlay = self.overlay.copy()
        overlay[self.top_left[1]:self.bottom_right[1],self.top_left[0]:self.bottom_right[0]] = frame
        return overlay

    def get_frames(self, start=0, stop=None):
        for frame in self.scene.get_frames(start, stop):
            if self.is_static():
                yield self.overlay
            else:
                yield self.embed_scene_frame(frame)

    def total_frames(self):
        return self.scene.total_frames()

class Scene_sequence(Scene_object):
    
    def __init__(self, scene_list: List[Scene_object]):
        self.scene_list = scene_list
        self.frames_in_scene = [scene.total_frames() for scene in self.scene_list]
        self._total_frames = np.sum(self.frames_in_scene)
        self.scene_start_idx = np.cumsum([0] + self.frames_in_scene[:-1])
        self.scene_stop_idx = np.cumsum(self.frames_in_scene) - 1
        self.output = "sequence.mp4"
        super().__init__()

    def get_children(self):
        return self.scene_list

    def get_frames(self, start=500, stop=None):
        if stop is None:
            stop = self.total_frames() - 1
        first_scene_idx = np.argmax(self.scene_stop_idx >= start)
        last_scene_idx = np.argmax(self.scene_stop_idx >= stop)
        for scene_idx in range(first_scene_idx, last_scene_idx+1):
            scene_start = min(self.frames_in_scene[scene_idx]-1, max(0, start - self.scene_start_idx[scene_idx]))
            scene_stop = min(self.frames_in_scene[scene_idx], max(0, stop - self.scene_start_idx[scene_idx]))
            for frame in self.scene_list[scene_idx].get_frames(scene_start, scene_stop):
                yield frame

    def render_scene(self, i):
        self.scene_list[i].render(output=f"scene_{i}_{self.scene_list[i].output}")

    def total_frames(self):
        return self._total_frames

    def shufle(self):
        random.shuffle(self.scene_list)



