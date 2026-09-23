#ifndef ORBIROB_MOTION_HPP_
#define ORBIROB_MOTION_HPP_

#include <rclcpp/rclcpp.hpp>
#include <geometry_msgs/msg/twist.hpp>

#include <controller_manager_msgs/srv/load_controller.hpp>
#include <controller_manager_msgs/srv/configure_controller.hpp>
#include <controller_manager_msgs/srv/switch_controller.hpp>
#include <controller_manager_msgs/srv/list_controllers.hpp>

#include <atomic>
#include <mutex>
#include <thread>
#include <termios.h>

class OrbiRobMotion : public rclcpp::Node
{
public:
    OrbiRobMotion();
    ~OrbiRobMotion();

    bool startControllers();
    void startKeyboardControl();

private:
    void forward();
    void backward();
    void rotateLeft();
    void rotateRight();
    void stop();

    void publishCommand();
    void keyboardLoop();




    rclcpp::Publisher<geometry_msgs::msg::Twist>::SharedPtr cmd_vel_pub_;
    rclcpp::TimerBase::SharedPtr timer_;

    rclcpp::Client<controller_manager_msgs::srv::LoadController>::SharedPtr
        load_controller_client_;

    rclcpp::Client<controller_manager_msgs::srv::ConfigureController>::SharedPtr
        configure_controller_client_;

    rclcpp::Client<controller_manager_msgs::srv::SwitchController>::SharedPtr
        switch_controller_client_;

    rclcpp::Client<controller_manager_msgs::srv::ListControllers>::SharedPtr
        list_controllers_client_;

    rclcpp::TimerBase::SharedPtr controller_init_timer_;



    double linear_velocity_;
    double angular_velocity_;

    std::mutex velocity_mutex_;
    std::atomic<bool> running_;

    std::thread keyboard_thread_;

    struct termios original_terminal_;

private:

    void checkControllerState();
    void initializeDiffDriveController();


};

#endif  // ORBIROB_MOTION_HPP_
