# Sourced after TROS setup by camera and perception launchers.
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export FASTRTPS_DEFAULT_PROFILES_FILE="${MUSE_PET_DDS_PROFILE:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/fastdds.xml}"
export RMW_FASTRTPS_USE_QOS_FROM_XML=1
export ROS_DISABLE_LOANED_MESSAGES=1
