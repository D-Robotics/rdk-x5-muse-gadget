#include <array>
#include <memory>
#include <string>
#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/image.hpp>
#include <sensor_msgs/msg/camera_info.hpp>
#include <std_msgs/msg/bool.hpp>
#include <hbm_img_msgs/msg/hbm_msg1080_p.hpp>
#include "stream_budget.hpp"
#include "view_demand.hpp"

using Image = sensor_msgs::msg::Image;
using SharedImage = hbm_img_msgs::msg::HbmMsg1080P;
using Clock = muse::Clock;

class CameraThrottle : public rclcpp::Node {
public:
  explicit CameraThrottle(const rclcpp::NodeOptions &options = {}) : Node("muse_camera_throttle", options),
      gates_{muse::RateGate(declare_parameter<double>("fps", 10.0)),
             muse::RateGate(get_parameter("fps").as_double())},
      preview_gate_(declare_parameter<double>("preview_fps", 8.0)),
      independent_preview_(get_parameter("preview_fps").as_double() > get_parameter("fps").as_double()) {
    const auto transport = declare_parameter<std::string>("image_transport", "ros");
    if (transport != "ros" && transport != "shared_mem")
      throw std::invalid_argument("image_transport must be ros or shared_mem");
    const bool shared = transport == "shared_mem";
    if (shared) {
      shared_preview_ = shared_publisher("/muse/camera/preview/hbmem");
      shared_objects_ = shared_publisher("/muse/camera/objects/hbmem");
    }
    else preview_ = create_publisher<Image>("/muse/camera/preview", rclcpp::QoS(1).reliable());
    demand_ = create_subscription<std_msgs::msg::Bool>("/muse/preview/demand",
        rclcpp::QoS(1).best_effort(), [this](const std_msgs::msg::Bool &demand) {
          preview_lease_.update(demand.data, Clock::now());
        });
    const std::array<std::string, 2> eyes{{"left", "right"}};
    for (size_t i = 0; i < eyes.size(); ++i) {
      const auto output = "/muse/camera/" + eyes[i];
      const auto input = declare_parameter<std::string>(eyes[i] + "_topic",
          shared ? "/hbmem_" + eyes[i] + "_img" : "/image_" + eyes[i] + "_raw");
      if (input == output || input == output + "/hbmem" ||
          input == "/muse/camera/preview" || input == "/muse/camera/preview/hbmem")
        throw std::invalid_argument("Throttle input must differ from its outputs");
      health_[i] = create_publisher<sensor_msgs::msg::CameraInfo>(
          output + "/health", rclcpp::QoS(1).best_effort());
      if (shared) {
        shared_outputs_[i] = shared_publisher(output + "/hbmem");
        shared_inputs_[i] = create_subscription<SharedImage>(input,
            rclcpp::SensorDataQoS().keep_last(1), [this, i](const SharedImage &msg) {
          if (!msg.width || !msg.height || !msg.data_size || msg.data_size > msg.data.size()) {
            RCLCPP_ERROR_THROTTLE(get_logger(), *get_clock(), 5000, "Invalid shared image size");
            return;
          }
          const auto now = Clock::now();
          ++received_[i];
          sensor_msgs::msg::CameraInfo info;
          info.header.stamp = msg.time_stamp;
          info.header.frame_id = i == 0 ? "left" : "right";
          info.width = msg.width;
          info.height = msg.height;
          publish_health(i, info, now);
          const bool model_consumer = shared_outputs_[i]->get_subscription_count() > 0;
          const bool model_sent = gates_[i].ready(now) && model_consumer &&
              publish_shared(shared_outputs_[i], msg);
          if (model_sent) ++published_[i];
          // Keep hand interaction available; give depth the YOLO budget on its page.
          if (i == 0 && !muse::depth_requested() &&
              shared_objects_->get_subscription_count() > 0 && object_gate_.ready(now))
            publish_shared(shared_objects_, msg);
          // At matched/slower rates, preview selects model-input frames. A
          // faster preview has its own budget; model delivery stays bounded.
          if (i == 0 && preview_lease_.active(now) &&
              (independent_preview_ || !model_consumer || model_sent) &&
              shared_preview_->get_subscription_count() > 0 && preview_gate_.ready(now) &&
              publish_shared(shared_preview_, msg)) ++preview_count_;
        });
      } else {
        outputs_[i] = create_publisher<Image>(output, rclcpp::QoS(1).reliable());
        inputs_[i] = create_subscription<Image>(input,
            rclcpp::SensorDataQoS().keep_last(1), [this, i](Image::ConstSharedPtr msg) {
          const auto now = Clock::now();
          ++received_[i];
          sensor_msgs::msg::CameraInfo info;
          info.header = msg->header;
          info.width = msg->width;
          info.height = msg->height;
          publish_health(i, info, now);
          const bool model_consumer = outputs_[i]->get_subscription_count() > 0;
          const bool model_sent = gates_[i].ready(now) && model_consumer;
          if (model_sent) {
            outputs_[i]->publish(*msg);
            ++published_[i];
          }
          if (i == 0 && preview_lease_.active(now) &&
              (independent_preview_ || !model_consumer || model_sent) &&
              preview_->get_subscription_count() > 0 && preview_gate_.ready(now)) {
            preview_->publish(*msg);
            ++preview_count_;
          }
        });
      }
    }
    last_report_ = Clock::now();
    report_ = create_wall_timer(std::chrono::seconds(5), [this] {
      const auto now = Clock::now();
      const double elapsed = std::chrono::duration<double>(now - last_report_).count();
      RCLCPP_INFO(get_logger(), "FPS input=%.1f/%.1f delivered=%.1f/%.1f preview=%.1f",
          received_[0] / elapsed, received_[1] / elapsed,
          published_[0] / elapsed, published_[1] / elapsed, preview_count_ / elapsed);
      received_ = {}; published_ = {}; preview_count_ = 0; last_report_ = now;
    });
  }
private:
  rclcpp::Publisher<SharedImage>::SharedPtr shared_publisher(const std::string &topic) {
    auto publisher = create_publisher<SharedImage>(topic, rclcpp::QoS(1).reliable());
    if (!publisher->can_loan_messages())
      throw std::runtime_error("Shared image loans unavailable; source scripts/ros-transport.sh "
                               "with MUSE_PET_TRANSPORT=shm, or select udp explicitly");
    return publisher;
  }

  bool publish_shared(const rclcpp::Publisher<SharedImage>::SharedPtr &publisher,
                      const SharedImage &source) {
    auto loan = publisher->borrow_loaned_message();
    if (!loan.is_valid() || !muse::copy_active_frame(source, loan.get())) {
      RCLCPP_ERROR_THROTTLE(get_logger(), *get_clock(), 5000, "Cannot fill shared image loan");
      return false;
    }
    publisher->publish(std::move(loan));
    return true;
  }

  void publish_health(size_t eye, const sensor_msgs::msg::CameraInfo &info, Clock::time_point now) {
    if (now < health_next_[eye]) return;
    // Zero intrinsics: frame liveness, never a calibration source.
    health_[eye]->publish(info);
    health_next_[eye] = now + std::chrono::milliseconds(250);
  }

  std::array<muse::RateGate, 2> gates_;
  muse::RateGate preview_gate_;
  muse::RateGate object_gate_{10.0};
  bool independent_preview_;
  muse::PreviewLease preview_lease_;
  std::array<Clock::time_point, 2> health_next_{};
  std::array<size_t, 2> received_{}, published_{};
  size_t preview_count_ = 0;
  Clock::time_point last_report_{};
  std::array<rclcpp::Publisher<Image>::SharedPtr, 2> outputs_;
  std::array<rclcpp::Subscription<Image>::SharedPtr, 2> inputs_;
  std::array<rclcpp::Publisher<SharedImage>::SharedPtr, 2> shared_outputs_;
  std::array<rclcpp::Subscription<SharedImage>::SharedPtr, 2> shared_inputs_;
  std::array<rclcpp::Publisher<sensor_msgs::msg::CameraInfo>::SharedPtr, 2> health_;
  rclcpp::Publisher<Image>::SharedPtr preview_;
  rclcpp::Publisher<SharedImage>::SharedPtr shared_preview_, shared_objects_;
  rclcpp::Subscription<std_msgs::msg::Bool>::SharedPtr demand_;
  rclcpp::TimerBase::SharedPtr report_;
};

std::shared_ptr<rclcpp::Node> make_camera_throttle(const rclcpp::NodeOptions &options) {
  return std::make_shared<CameraThrottle>(options);
}

#ifndef MUSE_RUNTIME_EMBEDDED
int main(int argc, char **argv) {
  rclcpp::init(argc, argv);
  try {
    rclcpp::spin(std::make_shared<CameraThrottle>());
  } catch (const std::exception &error) {
    RCLCPP_FATAL(rclcpp::get_logger("muse_camera_throttle"), "%s", error.what());
    rclcpp::shutdown();
    return 1;
  }
  rclcpp::shutdown();
}

#endif
