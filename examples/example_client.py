from clipstitcher import *
# no credentials needed on hardware that 
# can be physicaly accessed by all people
# (Rassberry PIs etc.)

controller_id = '1wLaul1kKoj_R3oFv1KQE0WXVZnSI_QCu'
media_path = './loaded/sequence.mp4'

player = ClientPlayer(controller_id=controller_id, media_path=media_path)
player.play_content()
    