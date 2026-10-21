from glob import glob
from setuptools import find_packages, setup


package_name = "muse_pet_vision"


setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=("test",)),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        ("share/" + package_name + "/launch", glob("launch/*.launch.py")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="RDK X5 Muse Gadget contributors",
    maintainer_email="shockley6668@users.noreply.github.com",
    description="ROS 2 vision events for the RDK X5 Muse desktop pet.",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "muse_pet_vision_node = muse_pet_vision.node:main",
            "muse_pet_depth_frames = muse_pet_vision.depth_frames:main",
            "muse_pet_preview_frames = muse_pet_vision.preview_frames:main",
        ],
    },
)
