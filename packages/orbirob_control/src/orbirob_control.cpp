#include "orbirob_motion.hpp"

#include <memory>

#include <rclcpp/rclcpp.hpp>

int main(int argc, char * argv[])
{
    rclcpp::init(argc, argv);

    auto robot = std::make_shared<OrbiRobMotion>();

    rclcpp::spin(robot);

    rclcpp::shutdown();

    return 0;
}
