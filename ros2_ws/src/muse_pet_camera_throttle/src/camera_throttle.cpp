#include <array>
#include <chrono>
#include <cmath>
#include <memory>
#include <stdexcept>
#include <string>
#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/image.hpp>

using Image = sensor_msgs::msg::Image;
using Clock = std::chrono::steady_clock;

class CameraThrottle : public rclcpp::Node {
public:
  CameraThrottle() : Node("muse_camera_throttle") {
    const auto fps = declare_parameter<double>("fps", 10.0);
    if (!std::isfinite(fps) || fps <= 0 || fps > 30) {
      throw std::invalid_argument("fps must be in (0, 30]");
    }
    period_ = std::chrono::nanoseconds(static_cast<int64_t>(1e9 / fps));
    const std::array<std::string, 2> eyes{{"left", "right"}};
    for (size_t i = 0; i < eyes.size(); ++i) {
      const auto input = declare_parameter<std::string>(eyes[i] + "_topic",
          "/image_" + eyes[i] + "_raw");
      const auto output = "/muse/camera/" + eyes[i];
      if (input == output) throw std::invalid_argument("Throttle input must differ from output");
      // Reliable output matches the installed TROS model nodes. Depth one
      // keeps slow consumers from retaining a long history of raw frames.
      publishers_[i] = create_publisher<Image>(output, rclcpp::QoS(1).reliable());
      subscriptions_[i] = create_subscription<Image>(input,
          rclcpp::SensorDataQoS().keep_last(1), [this, i](Image::ConstSharedPtr msg) {
        const auto now = Clock::now();
        if (now < next_[i]) return;
        if (now - next_[i] > period_) next_[i] = now;
        next_[i] += period_;
        publishers_[i]->publish(*msg);  // Preserve sensor geometry and timestamp.
        ++published_[i];
      });
    }
    last_report_ = Clock::now();
    timer_ = create_wall_timer(std::chrono::seconds(5), [this] {
      const auto now = Clock::now();
      const double seconds = std::chrono::duration<double>(now - last_report_).count();
      RCLCPP_INFO(get_logger(), "Published FPS: left=%.1f right=%.1f",
                  published_[0] / seconds, published_[1] / seconds);
      published_ = {};
      last_report_ = now;
    });
  }
private:
  std::chrono::nanoseconds period_{};
  std::array<Clock::time_point, 2> next_{};
  std::array<size_t, 2> published_{};
  Clock::time_point last_report_{};
  std::array<rclcpp::Publisher<Image>::SharedPtr, 2> publishers_;
  std::array<rclcpp::Subscription<Image>::SharedPtr, 2> subscriptions_;
  rclcpp::TimerBase::SharedPtr timer_;
};

int main(int argc, char **argv) {
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<CameraThrottle>());
  rclcpp::shutdown();
}
