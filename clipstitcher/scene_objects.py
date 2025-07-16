import cv2
import textwrap
from typing import List
import os
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
import time
import random
import numpy as np
from tqdm import tqdm
import importlib.resources
import hashlib
import json
import threading
import subprocess as sp
import paramiko

class DefaultOptions:
    def __init__(self):
        self.fill_color = [255, 255, 255]
        self.background_color = [255, 255, 255]
        self.core_thread_count = 4
        self.resolution = (1920, 1080)
        self.ffmpeg_win = '.\\ffmpeg_tool\\bin\\ffmpeg.exe'
        self.client_secrets = 'client_secrets.json'
        self.fps = 24
        self.cache_dir = "clipstitcher_cache"
        # make cache dir if it doesn't exist
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

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
            new_size = (screen[0], int(frame.shape[0]*w_a))
            frame = cv2.resize(frame, new_size, interpolation = cv2.INTER_AREA)
            border_1 = int((screen[1] - frame.shape[0])/2)
            border_2 = screen[1] - frame.shape[0] - border_1
            frame = cv2.copyMakeBorder(frame, border_1, border_2, 0, 0, borderType=cv2.BORDER_CONSTANT, value=fill_color)
        elif frame_a < screen_a:
            h_a = screen[1]/frame.shape[0]
            new_size = (int(frame.shape[1]*h_a), screen[1])
            frame = cv2.resize(frame, new_size, interpolation = cv2.INTER_AREA)
            border_1 = int((screen[0] - frame.shape[1])/2)
            border_2 = screen[0] - frame.shape[1] - border_1
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
            f = f.replace('\\', '/')
            txtf.write(f"file {f} \n")
    
    # run ffmpeg
    if os.name =='posix':
        ffmpeg_executable = 'ffmpeg'
    elif os.name == 'nt':
        ffmpeg_executable = default_options.ffmpeg_win
    cmd = f"{ffmpeg_executable} -y -loglevel error -f concat -safe 0 -i {i} -vcodec copy {out}"
    sp.Popen(cmd, shell=True).wait()
    
    # remove input file
    os.remove(i)


def clear_cache(period=7*24*60*60):
    # remove all files that are untouched for more than 7 days
    for file in os.listdir(default_options.cache_dir):
        if os.path.getmtime(os.path.join(default_options.cache_dir, file)) < time.time() - period:
            os.remove(os.path.join(default_options.cache_dir, file))
       
class Scene_object:
    def __init__(self, screen=default_options.resolution, fill_color=[255, 255, 255]):
        self.window = "main window"
        self.size = screen
        self.fill_color = fill_color
        self.static = False
        self.threadLock = threading.Lock()
        self.temp_output = "chunk_{}.mp4"
        self.hash_id = None

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
        fps = default_options.fps
        video_writter = cv2.VideoWriter(output, codec, fps, self.size, True)
        total_frames = stop - start
        self.frames_processed = 0
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
            stop = self.total_frames()
        total_frames = stop - start
        chunk_size = int((stop-start)/threads)
        print(f"Chunk size: {chunk_size*threads} vs {self.total_frames()}")

        # generate and start render threads
        self.frames_processed = 0
        render_threads = []
        chunk_files = [self.temp_output.format(i) for i in range(threads)]
        kwargs_list = []
        for i in range(threads):
            kwargs_list.append({
                "start": start + chunk_size*i, 
                "stop": min(start + chunk_size*(i+1), total_frames), 
                "output": chunk_files[i]})
        kwargs_list[-1]["stop"] = total_frames
        for kwargs in kwargs_list:
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

    def update_broadcast_paramiko(self, user=None, ip=None, folder=None, ssh_key_file=None):
        # not tested
        assert(user is not None and ip is not None and ssh_key_file is not None)
        if folder is None:
            folder = f'/home/{user}/Videos/clipstitcher'
        key = paramiko.RSAKey(filename=ssh_key_file)
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # connect via ssh
        ssh.connect(ip, username=user, pkey=key)

        # stop current VLC instance
        print("Stopping current VLC instance")
        ssh.exec_command(f'pkill vlc')
        ssh.exec_command(f'sleep 1')

        # upload video
        media_file = f'{folder}/{self.output}'
        print(f"Uploading video to {media_file}")
        sftp = ssh.open_sftp()
        sftp.put(self.output, media_file)
        sftp.close()
        print(f"Video uploaded!")

        # start video
        print("Starting new VLC instance")
        ssh.exec_command(f'bash -l -c "DISPLAY=:0 vlc {media_file} --loop --fullscreen --no-video-title-show &"')
        ssh.close()
        print("VLC should be running now!!")


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
        m = hashlib.sha256()
        with open(filepath, 'rb') as f:
            m.update(f.read())
        m.update(str(duration).encode('UTF-8'))
        m.update(str(background_color).encode('UTF-8'))
        self.hash_id = m.hexdigest()

    def get_children(self):
        return self.img

    def get_frames(self, start=0, stop=None):
        if stop is None:
            stop = self.total_frames() - 1
        for i in range(start, stop):
            yield self.img

    def total_frames(self):
        return self.duration*default_options.fps

class Html_page(Scene_object):
    def __init__(self, html_str=None, html_url=None, html_file=None, duration=5, scripts=[]):
        self.duration = duration
        self.scripts = scripts
        if html_url is not None:
            content = requests.get(html_url).content
            self.img = self.url_to_image(html_url)
            m = hashlib.sha256()
            m.update(content)
            for s in self.scripts:
                m.update(s.encode('UTF-8'))
        elif html_file is not None:
            self.img = self.file_to_image(html_file)
            with open(html_file, 'rb') as f:
                m = hashlib.sha256()
                m.update(f.read())
                for s in self.scripts:
                    m.update(s.encode('UTF-8'))
        elif html_str is not None:
            self.img = self.html_str_to_image(html_str)
            m = hashlib.sha256()
            m.update(html_str.encode('UTF-8'))
            for s in self.scripts:
                m.update(s.encode('UTF-8'))
        m.update(str(duration).encode('UTF-8'))
        hash_id = m.hexdigest()
        self.output = "html_page.mp4"
        super().__init__()
        self.static = True
        self.hash_id = hash_id

    def get_children(self):
        return self.img

    def url_to_image(self, url):
        url_hash = hashlib.sha256(url.encode('UTF-8')).hexdigest()
        cache_file = os.path.join(default_options.cache_dir, f"{url_hash}.png")
        if os.path.exists(cache_file):
            return cv2.imread(cache_file)
        
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--window-size={},{}".format(*default_options.resolution))
        options.add_argument("--hide-scrollbars")
        options.add_argument(f"--force-device-scale-factor={2.0}")
        driver = webdriver.Chrome(options=options)
        driver.get(url)
        time.sleep(2)

        for s in self.scripts:
            driver.execute_script(s)
        time.sleep(1)

        driver.get_screenshot_as_file("screenshot.png")
        driver.quit()
        img = cv2.imread("screenshot.png")
        cv2.imwrite(cache_file, img)
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
        return self.duration*default_options.fps

class Tweet(Html_page):

    def __init__(self, tweet_url, duration=5):
        self.tweet_url = tweet_url
        print(f"Requesting tweet {tweet_url}")
        res = requests.get(f"https://publish.twitter.com/oembed?url={tweet_url}")
        html_str = self.embed_to_html(res.json()["html"])
        js_script = f"""
            var element = document.querySelector('.twitter-tweet');
            original_height = element.offsetHeight;
            screen_height = window.innerHeight;
            var zoom_in = screen_height / original_height;
            console.log(zoom_in);
            document.body.style.zoom = String(zoom_in);
            if (element) {{
                element.scrollIntoView({{
                    behavior: 'auto',
                    block: 'center',
                    inline: 'center'
                }});
            }}
            return new Promise(resolve => setTimeout(resolve, 1000));
        """
        print(f"Converting tweet {tweet_url} to image")
        super().__init__(html_str=html_str, duration=duration, scripts=[js_script])
        self.output = "tweet.mp4"
        m = hashlib.sha256()
        m.update(html_str.encode('UTF-8'))
        m.update(js_script.encode('UTF-8'))
        m.update(str(duration).encode('UTF-8'))
        self.hash_id = m.hexdigest()

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

class Video(Scene_object):

    def __init__(self, file):
        self.file = file
        self.output = "video.mp4"
        cap = cv2.VideoCapture(self.file)
        self.n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
        super().__init__()
        with open(self.file, 'rb') as f:
            self.hash_id = hashlib.sha256(f.read()).hexdigest()

    def get_children(self):
        return self.file

    def get_frames(self, start=0, stop=None):
        cap = cv2.VideoCapture(self.file)
        cap.set(1, start)
        if stop is None:
            stop = self.total_frames()
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
        assert os.path.exists(overlay), f"File {overlay} does not exist."
        self.overlay = cv2.imread(overlay)
        self.top_left, self.bottom_right = find_screen(self.overlay, screen_color)
        self.overlay = self.embed_scene_frame(list(self.scene.get_frames(0,1))[0]) #TODO: make method for this
        super().__init__()
        m = hashlib.sha256()
        m.update(self.overlay.tobytes())
        m.update(self.scene.hash_id.encode('UTF-8'))
        m.update(str(screen_color).encode('UTF-8'))
        self.hash_id = m.hexdigest()

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
            if self.scene.is_static():
                yield self.overlay
            else:
                yield self.embed_scene_frame(frame)

    def total_frames(self):
        return self.scene.total_frames()
    
class LinearTransform(Scene_object):
    def __init__(self, scene: Scene_object, from_overlay, to_overlay, transition_time=1, 
                 start_time=0 , from_end=False, blend=True, 
                 screen_color = [0, 255, 0], 
                 replace_color=default_options.background_color):   
        self.scene = scene
        self.output = "linear_transform.mp4"
        self.transition_time = transition_time
        self.start_time = start_time
        self.from_end = from_end
        self.blend = blend
        
        #read overlays
        assert os.path.exists(from_overlay), f"File {from_overlay} does not exist."
        assert os.path.exists(to_overlay), f"File {to_overlay} does not exist."
        self.from_overlay = cv2.imread(from_overlay)
        self.to_overlay =cv2.imread(to_overlay)

        # make sure they are the same size
        # TODO: resize higher to smaler to keep high quality
        msg = f"Overlays in LinearTransition have different size: {self.from_overlay.shape} vs {self.to_overlay.shape}"
        assert self.from_overlay.shape == self.to_overlay.shape, msg

        # find screens in overlays
        self.from_top_left, self.from_bottom_right = find_screen(self.from_overlay, screen_color)
        self.to_top_left, self.to_bottom_right = find_screen(self.to_overlay, screen_color)

        # replace green screen color with white color in from_overlay
        self.from_overlay[
            self.from_top_left[1]:self.from_bottom_right[1],
            self.from_top_left[0]:self.from_bottom_right[0]] = replace_color
        
        # replace green screen color with white color in to_overlay
        self.to_overlay[
            self.to_top_left[1]:self.to_bottom_right[1],
            self.to_top_left[0]:self.to_bottom_right[0]] = replace_color
        
        super().__init__()
        m = hashlib.sha256() 
        m.update(self.scene.hash_id.encode('UTF-8'))
        m.update(self.from_overlay.tobytes())
        m.update(self.to_overlay.tobytes())
        m.update(str(self.transition_time).encode('UTF-8'))
        m.update(str(self.start_time).encode('UTF-8'))
        m.update(str(self.from_end).encode('UTF-8'))
        m.update(str(self.blend).encode('UTF-8'))
        m.update(str(screen_color).encode('UTF-8'))
        m.update(str(replace_color).encode('UTF-8'))
        self.hash_id = m.hexdigest()

    def get_children(self):
        return self.scene

    def embed_scene_frame(self, frame, i):
        # calculate coefficient of linear transform 
        fps = default_options.fps
        if self.from_end:
            start_frame = self.total_frames() - fps*self.transition_time - fps*self.start_time
        else:
            start_frame = self.start_time*fps
        c = max(0.0, min((i-start_frame)/(fps*self.transition_time), 1.0))
        
        # calculate new position of bottom right screen corner
        bottom_right = (
            int((1-c)*self.from_bottom_right[0] + c*self.to_bottom_right[0]), 
            int((1-c)*self.from_bottom_right[1] + c*self.to_bottom_right[1])
        )

        # calculate new position of top left screen corner
        top_left = (
            int((1-c)*self.from_top_left[0] + c*self.to_top_left[0]), 
            int((1-c)*self.from_top_left[1] + c*self.to_top_left[1])
        )  
        screen = (bottom_right[0] - top_left[0], bottom_right[1] - top_left[1])

        # blend overlays during tranform
        if self.blend:
            overlay = cv2.addWeighted(self.from_overlay, (1-c), self.to_overlay, c, 0)
        else:
            overlay = self.to_overlay.copy()
    
        # put content to moving screen
        frame = resize_to_fit_screen(frame, screen)
        overlay[top_left[1]:bottom_right[1],top_left[0]:bottom_right[0]] = frame
        return overlay

    def get_frames(self, start=0, stop=None):
        for i, frame in enumerate(self.scene.get_frames(start, stop), start):
             yield self.embed_scene_frame(frame, i)

    def total_frames(self):
        return self.scene.total_frames()

class LinearTransition(Scene_object):
    def __init__(self, scene_in:Scene_object, scene_out:Scene_object, transition_time=1):   
        self.scene_in = scene_in
        self.scene_out = scene_out
        self.transition_time = transition_time
        self.output = "linear_transition.mp4"
        super().__init__()
        m = hashlib.sha256() 
        m.update(self.scene_in.hash_id.encode('UTF-8'))
        m.update(self.scene_out.hash_id.encode('UTF-8'))
        m.update(str(self.transition_time).encode('UTF-8'))
        self.hash_id = m.hexdigest()

    def get_children(self):
        return self.scenes

    def get_frames(self, start=0, stop=None):
        fps = default_options.fps
        if stop is None:
            stop = self.total_frames() - 1
        total_transition_frames =  int(fps*self.transition_time)
        transition_start = self.scene_in.total_frames() - total_transition_frames
        transition_stop = self.scene_in.total_frames()


        for i in range(start, stop):
            if i < transition_start:
                frame = self.scene_in.get_frames(i, i+1).__next__()
                yield resize_to_fit_screen(frame, self.size)
            elif i >= transition_start and i < transition_stop:
                c = max(0.0, min((i-transition_start)/(fps*self.transition_time), 1.0))
                frame_in = resize_to_fit_screen(self.scene_in.get_frames(i, i+1).__next__(), self.size)
                frame_out = resize_to_fit_screen(self.scene_out.get_frames(i, i+1).__next__(), self.size)
                yield cv2.addWeighted(frame_in, (1-c), frame_out, c, 0)
            else:
                frame = self.scene_out.get_frames(i, i+1).__next__()
                yield resize_to_fit_screen(frame, self.size)

        counter = 0
        # if start < transition_start:
        #     start_in = start
        #     stop_in = min(stop, transition_start)
        #     for frame in self.scene_in.get_frames(start_in, stop_in):
        #         frame = resize_to_fit_screen(frame, self.size)
        #         yield frame
        # if stop > transition_start and start < transition_stop:
        #     start_in = max(start, transition_start)
        #     stop_in = min(stop, self.scene_in.total_frames()) 
        #     start_out = max(0, start-transition_start)
        #     stop_out = min(stop-transition_start, total_transition_frames)
        #     gen_in = self.scene_in.get_frames(start_in, stop_in)
        #     gen_out = self.scene_out.get_frames(start_out, stop_out)
        #     i = max(0, start-transition_start)
        #     for frame_in, frame_out in zip(gen_in, gen_out):
        #         c = max(0.0, min(i/(fps*self.transition_time), 1.0))
        #         i += 1
        #         frame_in = resize_to_fit_screen(frame_in, self.size)
        #         frame_out = resize_to_fit_screen(frame_out, self.size)
        #         counter += 1
        #         print(f"LinearTransition transition: {counter}")
        #         yield cv2.addWeighted(frame_in, (1-c), frame_out, c, 0)
        # if stop > transition_stop:
        #     start_out = max(total_transition_frames, start-self.scene_in.total_frames())
        #     stop_out = min(stop, self.scene_out.total_frames())
        #     for frame in self.scene_out.get_frames(start_out, stop_out):
        #         frame = resize_to_fit_screen(frame, self.size)
        #         counter += 1
        #         print(f"LinearTransition out: {counter}")
        #         yield frame
            
    def total_frames(self):
        return self.scene_in.total_frames() + self.scene_out.total_frames() - default_options.fps*self.transition_time

class Scene_sequence(Scene_object):
    
    def __init__(self, scene_list: List[Scene_object]):
        self.scene_list = scene_list
        self.frames_in_scene = [scene.total_frames() for scene in self.scene_list]
        self._total_frames = np.sum(self.frames_in_scene)
        self.scene_start_idx = np.cumsum([0] + self.frames_in_scene[:-1])
        self.scene_stop_idx = np.cumsum(self.frames_in_scene) - 1
        self.output = "sequence.mp4"
        super().__init__()
        m = hashlib.sha256() 
        for scene in self.scene_list:
            m.update(scene.hash_id.encode('UTF-8'))
        self.hash_id = m.hexdigest()

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
            print(f"{self.scene_list[scene_idx].__class__.__name__} - {scene_idx} - {scene_start}, {scene_stop}")
            for frame in self.scene_list[scene_idx].get_frames(scene_start, scene_stop):
                yield frame

    def render_flattened(self, threads=1, output="sequence.mp4", return_files=False):
        cache_dir = default_options.cache_dir
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)

        files_to_concatenate = []
        for scene in self.scene_list:
            hash_id = scene.hash_id
            scene_chunk_path = os.path.join(cache_dir, hash_id) + ".mp4"
            if os.path.exists(scene_chunk_path):
                files_to_concatenate.append(scene_chunk_path)
                print(f"{scene.__class__.__name__} - Cached scene {hash_id}")
                continue
            print(f"{scene.__class__.__name__} - Rendering scene {hash_id}")
            if isinstance(scene, Scene_sequence):
                l = scene.render_flattened(threads=threads, output=scene_chunk_path, return_files=True)
                files_to_concatenate.extend(l)
            else:
                scene.render(threads=threads, output=scene_chunk_path)
                files_to_concatenate.append(scene_chunk_path)

        ffmpeg_concatenate(files_to_concatenate, out=output)
        if return_files:
            return files_to_concatenate
        else:
            return output

    def render_scene(self, i):
        self.scene_list[i].render(output=f"scene_{i}_{self.scene_list[i].output}")

    def total_frames(self):
        return self._total_frames