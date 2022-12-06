import cv2
import textwrap
from typing import List
import os
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import random
import numpy as np
from tqdm import tqdm
import importlib

default_fill_color = [255, 255, 255]
default_background_color = [255, 255, 255]
default_core_thread_count = 4
with importlib.resources.path("clipstitcher", "styles.css") as p:
    html_style_path = p

def resize_to_fit_screen(frame, screen, fill_color=default_fill_color):
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
       
class Scene_object:
    def __init__(self, screen=(1920, 1080), fill_color=[255, 255, 255]):
        self.window = "main window"
        self.size = screen
        self.fill_color = fill_color
        self.static = False

    def is_static(self):
        return self.static

    def get_frames(self, start=0, stop=None):
        if stop is None:
            stop = self.total_frames()-1
        for i in range(start, stop):
            yield self.get_frame(i)

    def total_frames(self):
        "Returns total number of frames in the scene"
        pass

    def render(self, start=0, stop=None, output=None):
        "This method renders a scene into a video file given in path output"
        if output is None:
            output = self.output
        if stop is None:
            stop = self.total_frames()-1
        codec = cv2.VideoWriter_fourcc('P', 'I', 'M', '1')
        fps = 24
        video_writter = cv2.VideoWriter(output, codec, fps, self.size)
        total_frames = stop - start
        for frame in tqdm(self.get_frames(start, stop), total=total_frames):
            frame = resize_to_fit_screen(frame, self.size)
            video_writter.write(frame)
        video_writter.release()

    def save_frame_to_image(self, i=0, output=None):
        if output is None:
            output = f"{self.output}_f{i}.jpg"
        cv2.imwrite(output, self.get_frame(i))

    def play(self, start=0, stop=None):
        "This method plays the scene in opencv window (as fast as possible)"
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

class Image(Scene_object):
    def __init__(self, filepath, duration=5, background_color=default_background_color):
        self.output = "image.avi"
        self.duration = duration
        self.img = cv2.imread(filepath, cv2.IMREAD_UNCHANGED)
        trans_mask = self.img[:,:,3] == 0
        self.img[trans_mask] = background_color + [255]
        self.img = cv2.cvtColor(self.img, cv2.COLOR_BGRA2BGR)
        super().__init__()
        self.static = True

    def get_frame(self, i):
        if i < self.total_frames():
            return self.img
        else:
            return None

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
        self.output = "html_page.avi"
        super().__init__()
        self.static = True

    def url_to_image(self, url):
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--hide-scrollbars")
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
        temp_file = "temp_web_page.html"
        with open(temp_file, "w") as f:
            f.write(html_str)
        return self.file_to_image(temp_file)

    def get_frame(self, i):
        if i < self.total_frames():
            return self.img
        else:
            return None

    def total_frames(self):
        return self.duration*24

class Tweet(Html_page):

    def __init__(self, tweet_url, duration=5):
        self.tweet_url = tweet_url
        res = requests.get(f"https://publish.twitter.com/oembed?url={tweet_url}")
        html_str = self.embed_to_html(res.json()["html"])
        super().__init__(html_str=html_str, duration=duration)
        self.output = "tweet.avi"

    def embed_to_html(self, embed_code):
        print(html_style_path)
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
        self.output = "video.avi"
        self.cap = cv2.VideoCapture(self.file)
        self.n_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        super().__init__()

    def get_frame(self, i):
        if i < self.total_frames():
            if i != self.cap.get(1):
                self.cap.set(1, i)
            ret, frame = self.cap.read()
            return frame
        else:
            return None

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
        self.output = "Overlay.avi"
        self.overlay = cv2.imread(overlay)
        self.top_left, self.bottom_right = find_screen(self.overlay, screen_color)
        self.embed_scene_frame(self.scene.get_frame(0))
        super().__init__()

    def embed_scene_frame(self, frame):
        screen = (self.bottom_right[0] - self.top_left[0], self.bottom_right[1] - self.top_left[1])
        frame = resize_to_fit_screen(frame, screen)
        self.overlay[self.top_left[1]:self.bottom_right[1],self.top_left[0]:self.bottom_right[0]] = frame
        return self.overlay

    def get_frame(self, i):
        if i < self.total_frames():
            if self.scene.is_static():
                return self.overlay
            else:
                return self.embed_scene_frame(self.scene.get_frame(i))
        else:
            return None

    def total_frames(self):
        return self.scene.total_frames()

class Scene_sequence(Scene_object):
    
    def __init__(self, scene_list: List[Scene_object]):
        self.scene_list = scene_list
        self._frame_count_list = [scene.total_frames() for scene in self.scene_list]
        self._total_frames = np.sum(self._frame_count_list)
        self._frame_max_idx_list = np.cumsum(self._frame_count_list) - 1
        self.output = "sequence.avi"
        super().__init__()

    def get_frame(self, i):
        scene_idx = np.argmin(self._frame_max_idx_list <= i)
        new_i = i
        new_i -= self._frame_max_idx_list[scene_idx-1] if scene_idx > 0 else 0
        return self.scene_list[scene_idx].get_frame(new_i)

    def render_scene(self, i):
        self.scene_list[i].render(output=f"scene_{i}_{self.scene_list[i].output}")

    def total_frames(self):
        return np.sum(self._frame_count_list)

    def shufle(self):
        random.shuffle(self.scene_list)



