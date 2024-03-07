from clipstitcher import *
default_options.default_resolution = (1920, 1080)

sequence = Scene_sequence([
    Overlay(Image("images/welcome.png"), "images/overlay.png"),
    Overlay(Video("videos/IG story OEI LAST.mp4"), "images/overlay.png"),
    Overlay(Image("images/stroj_schody.png"), "images/overlay.png"),
    Tweet("https://twitter.com/jiri_skorpik/status/1593271304773304323", duration=10),
])

sequence.render(threads=4)


# upload to google
folder_id = 'None'
sequence.upload(folder_id)
sequence.set(folder_id)
