from clipstitcher import *
default_options.resolution = (1920, 1080)
default_options.client_secrets = 'client_secrets.json' # google creds.

sequence = Scene_sequence([
    Overlay(Image("images/welcome.png"), "images/overlay.png"),
    Overlay(Video("videos/IG story OEI LAST.mp4"), "images/overlay.png"),
    Overlay(Image("images/stroj_schody.png"), "images/overlay.png"),
    #Tweet("https://twitter.com/jiri_skorpik/status/1593271304773304323", duration=10),
])

sequence.render(threads=4)

# upload to google
folder_id = '10twZxG4UYOhNvxGuwJpoWqZsvXwOaRoD'
sequence.update_broadcast(folder_id)
