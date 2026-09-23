cmake_minimum_required(VERSION 3.8)
project(orbirob_control)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(controller_manager_msgs REQUIRED)
find_package(Threads REQUIRED)

include_directories(include)

add_executable(orbirob_motion
  src/orbirob_control.cpp
  src/orbirob_motion.cpp
)

ament_target_dependencies(orbirob_motion
    rclcpp
    geometry_msgs
    controller_manager_msgs
)

target_link_libraries(orbirob_motion
  Threads::Threads
)

install(TARGETS
  orbirob_motion
  DESTINATION lib/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  # the following line skips the linter which checks for copyrights
  # comment the line when a copyright and license is added to all source files
  set(ament_cmake_copyright_FOUND TRUE)
  # the following line skips cpplint (only works in a git repo)
  # comment the line when this package is in a git repo and when
  # a copyright and license is added to all source files
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
