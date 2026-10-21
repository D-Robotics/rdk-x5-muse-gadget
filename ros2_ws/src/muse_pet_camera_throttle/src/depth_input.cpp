// Adapt the driver's calibrated combined HBM stream for the installed StereoNet.
// This process exists only while the Depth page has a viewer.
#include <algorithm>
#include <memory>
#include <sys/stat.h>
#include <ctime>
#include <cstdlib>
#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/image.hpp>
#include <hbm_img_msgs/msg/hbm_msg1080_p.hpp>
#include "stream_budget.hpp"
#include "view_demand.hpp"

class DepthInput : public rclcpp::Node {
 public:
  explicit DepthInput(const rclcpp::NodeOptions &options = {}) : Node("muse_depth_input", options),
      gate_(declare_parameter<double>("fps", 30.0)) {
    output_ = create_publisher<sensor_msgs::msg::Image>("/muse/depth/input", rclcpp::QoS(1));
    input_ = create_subscription<hbm_img_msgs::msg::HbmMsg1080P>(
        "/hbmem_combine_img", rclcpp::SensorDataQoS().keep_last(1),
        [this](const hbm_img_msgs::msg::HbmMsg1080P &source) {
      if (!muse::depth_requested()) return;
      if (output_->get_subscription_count() == 0 || !gate_.ready(muse::Clock::now())) return;
      // Fixed geometry is tied to the 640x352 V2.4 model and EEPROM GDC profile.
      if (source.width != 640 || source.height != 704 || source.step != 640 ||
          source.data_size != 640 * 704 * 3 / 2 ||
          !std::equal(source.encoding.begin(), source.encoding.begin() + 4, "nv12")) {
        RCLCPP_ERROR_THROTTLE(get_logger(), *get_clock(), 5000,
            "Depth requires calibrated 640x704 NV12; install the shared depth camera profile");
        return;
      }
      auto image = std::make_unique<sensor_msgs::msg::Image>();
      image->header.stamp = source.time_stamp;
      image->header.frame_id = "stereo";
      image->width = source.width; image->height = source.height;
      image->step = source.step; image->encoding = "nv12";
      image->data.assign(source.data.begin(), source.data.begin() + source.data_size);
      output_->publish(std::move(image));
    });
  }
 private:
  muse::RateGate gate_;
  rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr output_;
  rclcpp::Subscription<hbm_img_msgs::msg::HbmMsg1080P>::SharedPtr input_;
};

std::shared_ptr<rclcpp::Node> make_depth_input(const rclcpp::NodeOptions &options) {
  return std::make_shared<DepthInput>(options);
}

#ifndef MUSE_RUNTIME_EMBEDDED
int main(int argc, char **argv) {
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<DepthInput>());
  rclcpp::shutdown();
}

#endif
