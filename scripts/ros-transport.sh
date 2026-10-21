# Sourced after TROS setup by every launcher. Explicit environment wins over
# the installed common config; all processes must select the same mode.
muse_transport_override="${MUSE_PET_TRANSPORT:-}"
muse_transport_config="${MUSE_PET_TRANSPORT_CONFIG:-/etc/default/muse-pet-transport}"
if [[ -r "$muse_transport_config" ]]; then
    source "$muse_transport_config"
fi
export MUSE_PET_TRANSPORT="${muse_transport_override:-${MUSE_PET_TRANSPORT:-udp}}"
muse_transport_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
case "$MUSE_PET_TRANSPORT" in
    udp)
        muse_transport_profile="$muse_transport_dir/fastdds.xml"
        export ROS_DISABLE_LOANED_MESSAGES=1
        export MUSE_PET_IMAGE_TRANSPORT=ros
        export MUSE_PET_SUBSTREAM_ENABLED=false
        export ROS_LOCALHOST_ONLY="${MUSE_PET_ROS_LOCALHOST_ONLY:-0}"
        ;;
    shm)
        muse_transport_profile="$muse_transport_dir/fastdds-shm.xml"
        export ROS_DISABLE_LOANED_MESSAGES=0
        export MUSE_PET_IMAGE_TRANSPORT=shared_mem
        export ROS_LOCALHOST_ONLY="${MUSE_PET_ROS_LOCALHOST_ONLY:-1}"
        case "${MUSE_PET_SHM_SUBSTREAM:-false}" in
            true|1) export MUSE_PET_SUBSTREAM_ENABLED=true ;;
            false|0) export MUSE_PET_SUBSTREAM_ENABLED=false ;;
            *) echo 'MUSE_PET_SHM_SUBSTREAM must be true or false.' >&2; return 2 ;;
        esac
        ;;
    *) echo 'MUSE_PET_TRANSPORT must be udp or shm.' >&2; return 2 ;;
esac
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export FASTRTPS_DEFAULT_PROFILES_FILE="${MUSE_PET_DDS_PROFILE:-$muse_transport_profile}"
[[ -r "$FASTRTPS_DEFAULT_PROFILES_FILE" ]] || {
    echo "DDS profile not found: $FASTRTPS_DEFAULT_PROFILES_FILE" >&2; return 2;
}
export RMW_FASTRTPS_USE_QOS_FROM_XML=1
