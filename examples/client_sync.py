from clipstitcher import *
import requests

folder_id = 'None'
api_key = 'None'
media_path = '/home/user/Videos/clipstitcher/sequence.mp4'

player = ClientPlayer(folder_id=folder_id, api_key=api_key, media_path=media_path)
player.play_content()
    