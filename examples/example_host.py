from clipstitcher import *
default_options.resolution = (1920, 1080)
default_options.client_secrets = 'client_secrets.json' # google creds.

sequence = Scene_sequence([
    LinearTransform(Image("images/welcome.png"), "overlays/fullscreen.png", "overlays/oei.png", transition_time=1, start_time=2),
    Overlay(LinearTransition(Image("images/stroj_schody.png"), Image("images/LU.png")), "overlays/oei.png"),
    Overlay(LinearTransform(Video("videos/growth.mp4"), "overlays/fullscreen.png", "overlays/centre.png", transition_time=1, start_time=2), "overlays/oei.png"),
    #Overlay(Video("videos/IG story OEI LAST.mp4"), "overlays/oei.png"),
    #Tweet("https://twitter.com/jiri_skorpik/status/1593271304773304323", duration=10),
])

sequence.render(threads=4)

# upload to google
folder_id = "None"
sequence.update_broadcast(folder_id)
