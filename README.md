<div align="center">
<b style="font-size:320%;">ClipStitcher</b>
<p style="font-size:120%;">
A simple tool to automaticaly create video sequences with simple edits<br>
¯\_(ツ)_/¯
</p>
  <img src="logo.png?raw=True" width="250"/>
</div>

## Instalation instruction using pip (Lixux)
```bash  
python3 -m pip install git+https://github.com/LiborKudela/clipsticher.git
```  

## Quick documentation:

**Start with importing the package:**
```python
from clipstitcher import *
```

**How to create scenes:**
```python
my_scene_1 = Image("path_to_my_img.jpg", duration=5)
my_scene_2 = Video("path_to_my_video.mp4")
scene_seq_1 = Scene_sequence([my_scene_1, my_scene_2])
```

**How to play or render any scene:**
```python
my_scene_1.play()
my_scene_2.render()
scene_seq.render()
```

**Or more specific instructions:**
```python
my_scene_1.play(start=start_frame_int, stop=stop_frame_int)
scene_seq.render(start=start_frame_int, stop=stop_frame_int, output="my_video.avi")
```

**We can nest scenes arbitrarily:**
```python
deepest_level = Video("path_to_my_video.mp4")
middle_level = Overlay(deepest_scene, "path_to_my_overlay.jpg")
almost_top_level = Overlay(middle_level_scene, "path_to_different_overlay.jpg")
the_most_top_level = Scene_sequence([deepest_level, middle_level, almost_top_level])
the_most_top_level.render("getting_deeper.avi")
```

**Quick guide to all available scenes with args and kwargs:**
```python
Image(filepath, duration=5)
HtmlPage(url_or_filepath_or_htmlstring, duration=5)
Tweet(url, duration=5)
load_tweets_from_file("path_to_text_file_with_urls", duration=5)
Video("filepath")
load_videos_from_folder("path_to_folder_full_of_videos")
Overlay(scene, "overlay_filepath", screen_color = [0, 255, 0])
Scene_sequence(list_of_scenes)
```


