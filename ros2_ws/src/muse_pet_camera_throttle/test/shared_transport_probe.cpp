#include <algorithm>
#include <chrono>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <array>
#include <set>
#include <rclcpp/rclcpp.hpp>
#include <hbm_img_msgs/msg/hbm_msg1080_p.hpp>
#include <sensor_msgs/msg/camera_info.hpp>
#include <std_msgs/msg/bool.hpp>

using Frame = hbm_img_msgs::msg::HbmMsg1080P;
using Clock = std::chrono::steady_clock;

class Probe : public rclcpp::Node {
public:
  explicit Probe(bool producer) : Node(producer ? "muse_test_camera" : "muse_test_observer") {
    fast_preview_ = declare_parameter<bool>("fast_preview", false);
    started_ = Clock::now();
    if (producer) {
      for (int eye = 0; eye < 2; ++eye) {
        cameras_[eye] = create_publisher<Frame>(eye ? "/hbmem_right_img" : "/hbmem_left_img", 1);
        if (!cameras_[eye]->can_loan_messages()) throw std::runtime_error("Camera loan unavailable");
      }
      timer_ = create_wall_timer(std::chrono::milliseconds(33), [this] {
        for (auto &camera : cameras_) {
          auto loan = camera->borrow_loaned_message();
          auto &frame = loan.get();
          frame.index = sequence_;
          frame.time_stamp = now();
          frame.width = frame.step = 960;
          frame.height = 544;
          frame.data_size = 960 * 544 * 3 / 2;
          frame.encoding.fill(0);
          frame.encoding[0] = 'n'; frame.encoding[1] = 'v';
          frame.encoding[2] = '1'; frame.encoding[3] = '2';
          std::fill_n(frame.data.begin(), frame.data_size, static_cast<uint8_t>(sequence_));
          camera->publish(std::move(loan));
        }
        ++sequence_;
      });
    } else {
      demand_ = create_publisher<std_msgs::msg::Bool>("/muse/preview/demand", 1);
      image_ = create_subscription<Frame>("/muse/camera/left/hbmem", rclcpp::SensorDataQoS().keep_last(1),
          [this](const Frame &frame) { validate(frame, 0); });
      preview_ = create_subscription<Frame>("/muse/camera/preview/hbmem", rclcpp::SensorDataQoS().keep_last(1),
          [this](const Frame &frame) { validate(frame, 1); });
      for (int eye = 0; eye < 2; ++eye) {
        health_[eye] = create_subscription<sensor_msgs::msg::CameraInfo>(
            eye ? "/muse/camera/right/health" : "/muse/camera/left/health",
            rclcpp::SensorDataQoS().keep_last(1), [this, eye](const sensor_msgs::msg::CameraInfo &info) {
          if (info.width != 960 || info.height != 544 || !info.header.stamp.sec)
            throw std::runtime_error("Invalid compact health metadata");
          ++health_count_[eye];
        });
      }
      timer_ = create_wall_timer(std::chrono::milliseconds(200), [this] {
        double elapsed = std::chrono::duration<double>(Clock::now() - started_).count();
        if (elapsed < 2 && counts_[1]) throw std::runtime_error("Idle preview received frames");
        std_msgs::msg::Bool request;
        request.data = elapsed >= 2 && elapsed < 4;
        demand_->publish(request);
        if (elapsed >= 4.6 && stopped_count_ < 0) stopped_count_ = counts_[1];
        if (elapsed >= 7) {
          if (counts_[0] < 20 || counts_[0] > 85 ||
              counts_[1] < (fast_preview_ ? 35 : 5) || counts_[1] > (fast_preview_ ? 70 : 22) ||
              counts_[1] != stopped_count_ || health_count_[0] < 2 || health_count_[1] < 2)
            throw std::runtime_error("Delivery rate, compact health or preview stop check failed");
          if (!fast_preview_ && !std::includes(indices_[0].begin(), indices_[0].end(),
                             indices_[1].begin(), indices_[1].end()))
            throw std::runtime_error("Preview frame lacks a matching model-input frame");
          std::cout << "shared transport passed: inference=" << counts_[0]
                    << " preview=" << counts_[1] << " health="
                    << health_count_[0] << '/' << health_count_[1] << std::endl;
          rclcpp::shutdown();
        }
      });
    }
  }
private:
  void validate(const Frame &frame, size_t channel) {
    const auto pattern = static_cast<uint8_t>(frame.index);
    if (frame.width != 960 || frame.height != 544 || frame.step != 960 ||
        frame.data_size != 960 * 544 * 3 / 2 || frame.encoding[0] != 'n' ||
        !frame.time_stamp.sec || frame.data.front() != pattern ||
        frame.data[frame.data_size - 1] != pattern || frame.index <= last_[channel])
      throw std::runtime_error("Corrupted, repeated or reordered shared frame");
    last_[channel] = frame.index;
    indices_[channel].insert(frame.index);
    ++counts_[channel];
  }
  Clock::time_point started_{};
  int sequence_ = 0, stopped_count_ = -1;
  bool fast_preview_ = false;
  std::array<int, 2> counts_{}, health_count_{}, last_{{-1, -1}};
  std::array<std::set<int>, 2> indices_;
  std::array<rclcpp::Publisher<Frame>::SharedPtr, 2> cameras_;
  std::array<rclcpp::Subscription<sensor_msgs::msg::CameraInfo>::SharedPtr, 2> health_;
  rclcpp::Publisher<std_msgs::msg::Bool>::SharedPtr demand_;
  rclcpp::Subscription<Frame>::SharedPtr image_, preview_;
  rclcpp::TimerBase::SharedPtr timer_;
};

int main(int argc, char **argv) {
  rclcpp::init(argc, argv);
  try {
    rclcpp::spin(std::make_shared<Probe>(argc > 1 && std::string(argv[1]) == "producer"));
  } catch (const std::exception &error) {
    std::cerr << error.what() << std::endl;
    rclcpp::shutdown();
    return 1;
  }
  if (rclcpp::ok()) rclcpp::shutdown();
}
