#include "orbirob_motion.hpp"

#include <unistd.h>

#include <chrono>
#include <functional>
#include <iostream>

using namespace std::chrono_literals;



OrbiRobMotion::OrbiRobMotion()
    : Node("orbirob_motion"),
    linear_velocity_(0.0),
    angular_velocity_(0.0),
    running_(true)
{
    // ------------------------------------------------------------
    // Controller manager service clients
    // ------------------------------------------------------------

    load_controller_client_ =
        this->create_client<
            controller_manager_msgs::srv::LoadController>(
            "/controller_manager/load_controller");

    configure_controller_client_ =
        this->create_client<
            controller_manager_msgs::srv::ConfigureController>(
            "/controller_manager/configure_controller");

    switch_controller_client_ =
        this->create_client<
            controller_manager_msgs::srv::SwitchController>(
            "/controller_manager/switch_controller");

    list_controllers_client_ =
        this->create_client<
            controller_manager_msgs::srv::ListControllers>(
            "/controller_manager/list_controllers");

    // ------------------------------------------------------------
    // Velocity command publisher
    // ------------------------------------------------------------

    cmd_vel_pub_ =
        this->create_publisher<geometry_msgs::msg::Twist>(
            "/diff_drive_controller/cmd_vel_unstamped",
            10);

    // Publish velocity commands at 30 Hz.
    timer_ = this->create_wall_timer(
        33ms,
        std::bind(
            &OrbiRobMotion::publishCommand,
            this));

    // ------------------------------------------------------------
    // Controller initialization/check timer
    //
    // This runs after rclcpp::spin() starts, so service requests
    // can be processed normally.
    // ------------------------------------------------------------

    controller_init_timer_ = this->create_wall_timer(
        100ms,
        std::bind(
            &OrbiRobMotion::checkControllerState,
            this));

    // ------------------------------------------------------------
    // Terminal configuration
    // ------------------------------------------------------------

    // Save original terminal settings.
    tcgetattr(
        STDIN_FILENO,
        &original_terminal_);

    // Put terminal into raw mode.
    struct termios raw = original_terminal_;

    raw.c_lflag &= ~(ICANON | ECHO);
    raw.c_cc[VMIN] = 0;
    raw.c_cc[VTIME] = 1;

    tcsetattr(
        STDIN_FILENO,
        TCSANOW,
        &raw);

    // ------------------------------------------------------------
    // Startup message
    // ------------------------------------------------------------

    RCLCPP_INFO(
        this->get_logger(),
        "OrbiRob motion controller started.");

    std::cout
        << "\n========================================\n"
        << "       OrbiRob Keyboard Control\n"
        << "========================================\n"
        << "   UP       : Forward\n"
        << "   DOWN     : Backward\n"
        << "   LEFT     : Rotate left\n"
        << "   RIGHT    : Rotate right\n"
        << "   SPACE    : Stop\n"
        << "   q        : Quit\n"
        << "========================================\n"
        << std::endl;
}


OrbiRobMotion::~OrbiRobMotion()
{
    running_ = false;

    if (keyboard_thread_.joinable()) {
        keyboard_thread_.join();
    }

    // Stop the robot.
    {
        std::lock_guard<std::mutex> lock(velocity_mutex_);
        linear_velocity_ = 0.0;
        angular_velocity_ = 0.0;
    }

    // Restore terminal settings.
    tcsetattr(
        STDIN_FILENO,
        TCSANOW,
        &original_terminal_);
}



    bool OrbiRobMotion::startControllers()
{
    RCLCPP_INFO(
        this->get_logger(),
        "Checking controller_manager...");

    // ------------------------------------------------------------
    // Wait for controller_manager
    // ------------------------------------------------------------

    if (!list_controllers_client_->wait_for_service(
            std::chrono::seconds(10)))
    {
        RCLCPP_ERROR(
            this->get_logger(),
            "controller_manager/list_controllers service "
            "not available.");

        return false;
    }

    // ------------------------------------------------------------
    // Query currently loaded controllers
    // ------------------------------------------------------------

    auto list_request =
        std::make_shared<
            controller_manager_msgs::srv::ListControllers::Request>();

    auto list_future =
        list_controllers_client_->async_send_request(list_request);

    if (rclcpp::spin_until_future_complete(
            this->get_node_base_interface(),
            list_future) !=
        rclcpp::FutureReturnCode::SUCCESS)
    {
        RCLCPP_ERROR(
            this->get_logger(),
            "Failed to query controller_manager.");

        return false;
    }

    auto list_response = list_future.get();

    bool jsb_loaded = false;
    bool jsb_active = false;

    bool diff_loaded = false;
    bool diff_active = false;

    // ------------------------------------------------------------
    // Inspect controller states
    // ------------------------------------------------------------

    for (const auto & controller : list_response->controller)
    {
        if (controller.name == "joint_state_broadcaster")
        {
            jsb_loaded = true;

            RCLCPP_INFO(
                this->get_logger(),
                "joint_state_broadcaster state: %s",
                controller.state.c_str());

            if (controller.state == "active")
            {
                jsb_active = true;
            }
        }

        else if (controller.name == "diff_drive_controller")
        {
            diff_loaded = true;

            RCLCPP_INFO(
                this->get_logger(),
                "diff_drive_controller state: %s",
                controller.state.c_str());

            if (controller.state == "active")
            {
                diff_active = true;
            }
        }
    }

    // ------------------------------------------------------------
    // Nothing to do if both controllers are already active.
    // ------------------------------------------------------------

    if (jsb_active && diff_active)
    {
        RCLCPP_INFO(
            this->get_logger(),
            "Both controllers are already active. "
            "Using existing controllers.");

        return true;
    }

    // ------------------------------------------------------------
    // Load joint_state_broadcaster only if it does not exist.
    // ------------------------------------------------------------

    if (!jsb_loaded)
    {
        RCLCPP_INFO(
            this->get_logger(),
            "joint_state_broadcaster is not loaded. Loading...");

        auto request =
            std::make_shared<
                controller_manager_msgs::srv::LoadController::Request>();

        request->name = "joint_state_broadcaster";

        auto future =
            load_controller_client_->async_send_request(request);

        if (rclcpp::spin_until_future_complete(
                this->get_node_base_interface(),
                future) !=
            rclcpp::FutureReturnCode::SUCCESS)
        {
            RCLCPP_ERROR(
                this->get_logger(),
                "Failed to load joint_state_broadcaster.");

            return false;
        }

        if (!future.get()->ok)
        {
            RCLCPP_ERROR(
                this->get_logger(),
                "controller_manager rejected "
                "joint_state_broadcaster.");

            return false;
        }

        RCLCPP_INFO(
            this->get_logger(),
            "Loaded joint_state_broadcaster.");

        jsb_loaded = true;
    }
    else
    {
        RCLCPP_INFO(
            this->get_logger(),
            "joint_state_broadcaster already loaded. "
            "Skipping load.");
    }

    // ------------------------------------------------------------
    // Load diff_drive_controller only if it does not exist.
    // ------------------------------------------------------------

    if (!diff_loaded)
    {
        RCLCPP_INFO(
            this->get_logger(),
            "diff_drive_controller is not loaded. Loading...");

        auto request =
            std::make_shared<
                controller_manager_msgs::srv::LoadController::Request>();

        request->name = "diff_drive_controller";

        auto future =
            load_controller_client_->async_send_request(request);

        if (rclcpp::spin_until_future_complete(
                this->get_node_base_interface(),
                future) !=
            rclcpp::FutureReturnCode::SUCCESS)
        {
            RCLCPP_ERROR(
                this->get_logger(),
                "Failed to load diff_drive_controller.");

            return false;
        }

        if (!future.get()->ok)
        {
            RCLCPP_ERROR(
                this->get_logger(),
                "controller_manager rejected "
                "diff_drive_controller.");

            return false;
        }

        RCLCPP_INFO(
            this->get_logger(),
            "Loaded diff_drive_controller.");

        diff_loaded = true;
    }
    else
    {
        RCLCPP_INFO(
            this->get_logger(),
            "diff_drive_controller already loaded. "
            "Skipping load.");
    }

    // ------------------------------------------------------------
    // Configure controllers that are not active.
    //
    // configure_controller is safe only for controllers that are
    // loaded but not yet configured/active.
    // ------------------------------------------------------------

    if (!jsb_active)
    {
        RCLCPP_INFO(
            this->get_logger(),
            "Configuring joint_state_broadcaster...");

        auto request =
            std::make_shared<
                controller_manager_msgs::srv::ConfigureController::Request>();

        request->name = "joint_state_broadcaster";

        auto future =
            configure_controller_client_->async_send_request(request);

        if (rclcpp::spin_until_future_complete(
                this->get_node_base_interface(),
                future) !=
            rclcpp::FutureReturnCode::SUCCESS)
        {
            RCLCPP_ERROR(
                this->get_logger(),
                "Failed to configure joint_state_broadcaster.");

            return false;
        }

        if (!future.get()->ok)
        {
            RCLCPP_ERROR(
                this->get_logger(),
                "Failed to configure joint_state_broadcaster.");

            return false;
        }
    }

    if (!diff_active)
    {
        RCLCPP_INFO(
            this->get_logger(),
            "Configuring diff_drive_controller...");

        auto request =
            std::make_shared<
                controller_manager_msgs::srv::ConfigureController::Request>();

        request->name = "diff_drive_controller";

        auto future =
            configure_controller_client_->async_send_request(request);

        if (rclcpp::spin_until_future_complete(
                this->get_node_base_interface(),
                future) !=
            rclcpp::FutureReturnCode::SUCCESS)
        {
            RCLCPP_ERROR(
                this->get_logger(),
                "Failed to configure diff_drive_controller.");

            return false;
        }

        if (!future.get()->ok)
        {
            RCLCPP_ERROR(
                this->get_logger(),
                "Failed to configure diff_drive_controller.");

            return false;
        }
    }

    // ------------------------------------------------------------
    // Activate controllers that are not already active.
    // ------------------------------------------------------------

    std::vector<std::string> controllers_to_activate;

    if (!jsb_active)
    {
        controllers_to_activate.push_back(
            "joint_state_broadcaster");
    }

    if (!diff_active)
    {
        controllers_to_activate.push_back(
            "diff_drive_controller");
    }

    if (!controllers_to_activate.empty())
    {
        RCLCPP_INFO(
            this->get_logger(),
            "Activating required controllers...");

        auto request =
            std::make_shared<
                controller_manager_msgs::srv::SwitchController::Request>();

        request->activate_controllers =
            controllers_to_activate;

        request->deactivate_controllers.clear();

        request->strictness =
            controller_manager_msgs::srv::SwitchController::Request::STRICT;

        request->start_asap = true;

        request->timeout.sec = 5;
        request->timeout.nanosec = 0;

        auto future =
            switch_controller_client_->async_send_request(request);

        if (rclcpp::spin_until_future_complete(
                this->get_node_base_interface(),
                future) !=
            rclcpp::FutureReturnCode::SUCCESS)
        {
            RCLCPP_ERROR(
                this->get_logger(),
                "Failed to activate controllers.");

            return false;
        }

        if (!future.get()->ok)
        {
            RCLCPP_ERROR(
                this->get_logger(),
                "controller_manager rejected controller activation.");

            return false;
        }
    }

    RCLCPP_INFO(
        this->get_logger(),
        "OrbiRob controllers are ready.");

    return true;
}


void OrbiRobMotion::checkControllerState()
{
    // ------------------------------------------------------------
    // Wait for controller_manager.
    // ------------------------------------------------------------

    if (!list_controllers_client_->service_is_ready())
    {
        RCLCPP_INFO_THROTTLE(
            this->get_logger(),
            *this->get_clock(),
            2000,
            "Waiting for controller_manager...");

        return;
    }

    // ------------------------------------------------------------
    // One-shot check.
    //
    // Cancel the timer before sending the request so that only
    // one controller-state query is active at a time.
    // ------------------------------------------------------------

    controller_init_timer_->cancel();

    auto request =
        std::make_shared<
            controller_manager_msgs::srv::ListControllers::Request>();

    list_controllers_client_->async_send_request(
        request,
        [this](
            rclcpp::Client<
                controller_manager_msgs::srv::ListControllers>::SharedFuture future)
        {
            auto response = future.get();

            bool joint_state_found = false;
            bool diff_drive_found = false;

            bool joint_state_active = false;
            bool diff_drive_active = false;

            // --------------------------------------------------------
            // Examine controller states.
            // --------------------------------------------------------

            for (const auto & controller : response->controller)
            {
                if (controller.name == "joint_state_broadcaster")
                {
                    joint_state_found = true;

                    RCLCPP_INFO(
                        this->get_logger(),
                        "joint_state_broadcaster state: %s",
                        controller.state.c_str());

                    if (controller.state == "active")
                    {
                        joint_state_active = true;
                    }
                }
                else if (controller.name == "diff_drive_controller")
                {
                    diff_drive_found = true;

                    RCLCPP_INFO(
                        this->get_logger(),
                        "diff_drive_controller state: %s",
                        controller.state.c_str());

                    if (controller.state == "active")
                    {
                        diff_drive_active = true;
                    }
                }
            }

            // --------------------------------------------------------
            // BOTH CONTROLLERS ARE ALREADY ACTIVE.
            //
            // Do not load, configure, or activate anything.
            // --------------------------------------------------------

            if (joint_state_active && diff_drive_active)
            {
                RCLCPP_INFO(
                    this->get_logger(),
                    "Both controllers are already active. "
                    "Using existing controllers.");

                startKeyboardControl();

                return;
            }

            // --------------------------------------------------------
            // At least one controller is missing or inactive.
            // --------------------------------------------------------

            RCLCPP_INFO(
                this->get_logger(),
                "Controller initialization is required.");

            initializeDiffDriveController();
        });
}



void OrbiRobMotion::forward()
{
    std::lock_guard<std::mutex> lock(velocity_mutex_);

    linear_velocity_ = 0.20;
    angular_velocity_ = 0.0;
}

void OrbiRobMotion::backward()
{
    std::lock_guard<std::mutex> lock(velocity_mutex_);

    linear_velocity_ = -0.20;
    angular_velocity_ = 0.0;
}

void OrbiRobMotion::rotateLeft()
{
    std::lock_guard<std::mutex> lock(velocity_mutex_);

    linear_velocity_ = 0.0;
    angular_velocity_ = 0.50;
}

void OrbiRobMotion::rotateRight()
{
    std::lock_guard<std::mutex> lock(velocity_mutex_);

    linear_velocity_ = 0.0;
    angular_velocity_ = -0.50;
}

void OrbiRobMotion::stop()
{
    std::lock_guard<std::mutex> lock(velocity_mutex_);

    linear_velocity_ = 0.0;
    angular_velocity_ = 0.0;
}

void OrbiRobMotion::publishCommand()
{
    double linear;
    double angular;

    {
        std::lock_guard<std::mutex> lock(velocity_mutex_);

        linear = linear_velocity_;
        angular = angular_velocity_;
    }

    geometry_msgs::msg::Twist cmd;

    cmd.linear.x = linear;
    cmd.linear.y = 0.0;
    cmd.linear.z = 0.0;

    cmd.angular.x = 0.0;
    cmd.angular.y = 0.0;
    cmd.angular.z = angular;

    cmd_vel_pub_->publish(cmd);
}

void OrbiRobMotion::keyboardLoop()
{
    char c;

    while (running_ && rclcpp::ok()) {

        int n = read(STDIN_FILENO, &c, 1);

        if (n != 1) {
            continue;
        }

        /*
         * Arrow keys:
         *
         * UP     = ESC [ A
         * DOWN   = ESC [ B
         * RIGHT  = ESC [ C
         * LEFT   = ESC [ D
         */

        if (c == '\033') {

            char seq[2] = {0, 0};

            if (read(STDIN_FILENO, &seq[0], 1) != 1) {
                continue;
            }

            if (read(STDIN_FILENO, &seq[1], 1) != 1) {
                continue;
            }

            if (seq[0] != '[') {
                continue;
            }

            switch (seq[1]) {

            case 'A':
                RCLCPP_INFO(
                    this->get_logger(),
                    "Forward");
                forward();
                break;

            case 'B':
                RCLCPP_INFO(
                    this->get_logger(),
                    "Backward");
                backward();
                break;

            case 'C':
                RCLCPP_INFO(
                    this->get_logger(),
                    "Rotate right");
                rotateRight();
                break;

            case 'D':
                RCLCPP_INFO(
                    this->get_logger(),
                    "Rotate left");
                rotateLeft();
                break;

            default:
                break;
            }
        }
        else if (c == ' ') {

            RCLCPP_INFO(
                this->get_logger(),
                "Stop");

            stop();
        }
        else if (c == 'q' || c == 'Q') {

            stop();
            running_ = false;
            rclcpp::shutdown();
        }
    }
}


void OrbiRobMotion::startKeyboardControl()
{
    if (keyboard_thread_.joinable())
    {
        RCLCPP_INFO(
            this->get_logger(),
            "Keyboard control is already running.");

        return;
    }

    keyboard_thread_ =
        std::thread(
            &OrbiRobMotion::keyboardLoop,
            this);

    RCLCPP_INFO(
        this->get_logger(),
        "Keyboard control started.");
}

void OrbiRobMotion::initializeDiffDriveController()
{
    // Existing load/configure/switch logic.
}
