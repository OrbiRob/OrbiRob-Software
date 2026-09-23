


# OrbiRob Description

Initial ROS 2 Jazzy robot description for OrbiRob.

## Robot structure

- `base_footprint`
- `base_link`
- `left_wheel_link`
- `right_wheel_link`
- `front_passive_wheel_link`
- `rear_passive_wheel_link`
- `camera_link`
- `camera_color_frame`
- `camera_depth_frame`
- `laser_link`
- 3 front SHARP sensor frames
- 4 bottom SHARP sensor frames

## Important

The dimensions and sensor poses are temporary placeholders. They are intended
to be replaced from the actual FreeCAD design later.

The package deliberately does not contain Gazebo-specific plugins yet.
Gazebo and real-hardware implementations should be selected by the bringup
layer so that the common robot description remains shared.

## Build

From the workspace root:

```bash
colcon build --packages-select orbi_description
source install/setup.bash
```

## Check Xacro

```bash
ros2 run xacro xacro \
  $(ros2 pkg prefix orbi_description)/share/orbi_description/urdf/orbirob.urdf.xacro
```

The next package should provide:
- Gazebo Harmonic simulation
- `gz_ros2_control`
- differential-drive controller
- simulated RGB-D camera
- simulated RPLIDAR
- simulated SHARP range sensors
- real/simulation switching
