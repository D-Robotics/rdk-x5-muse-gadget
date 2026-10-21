"""Shared parameters for foreground ROS launch and the fast page launcher."""
from pathlib import Path
import os


def stereo_parameters(share='/opt/tros/humble/share/hobot_stereonet'):
    model = Path(os.environ.get('MUSE_PET_DEPTH_MODEL', Path(share) / 'config/DStereoV2.4_int8.bin'))
    if not model.is_file():
        raise RuntimeError(f'StereoNet model missing: {model}')
    return {
        'stereonet_model_file_path': str(model),
        'stereo_image_topic': '/muse/depth/input',
        'camera_info_topic': '/hbmem_combine_img/right/camera_info',
        'left_camera_info_topic': '/hbmem_combine_img/left/camera_info',
        'publish_pcd_enabled': False, 'publish_origin_enable': False,
        'publish_rectify_bgr': False, 'publish_visual_enabled': True,
        'render_type': 'distance', 'render_perf': False,
        'infer_thread_num': 2, 'save_result_flag': False,
    }
