import os
import re
import subprocess

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    IncludeLaunchDescription,
    RegisterEventHandler,
    SetEnvironmentVariable,
)
from launch.event_handlers import OnProcessExit
from launch.conditions import IfCondition, UnlessCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    LaunchConfiguration,
    PathJoinSubstitution,
    PythonExpression,
)

from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():

    resources_package = 'orbirob_description'

    # ------------------------------------------------------------
    # Package paths
    # ------------------------------------------------------------

    package_share = get_package_share_directory(resources_package)

    path_to_share_dir_clipped = ''.join(
        package_share.rsplit('/' + resources_package, 1)
    )

    # AWS RoboMaker Small House
    aws_house_path = (
        '/home/bozma/Projects/Education/OrbiRob/'
        'aws-robomaker-small-house-world'
    )

    aws_house_models = os.path.join(
        aws_house_path,
        'models'
    )

    small_house_world = os.path.join(
        aws_house_path,
        'worlds',
        'small_house.world'
    )

    # ------------------------------------------------------------
    # Gazebo resource paths
    # ------------------------------------------------------------

    # Gazebo Fortress uses IGN_GAZEBO_RESOURCE_PATH.
    # GZ_SIM_RESOURCE_PATH is also set for Gazebo's newer naming.
    gazebo_resource_path = (
        path_to_share_dir_clipped
        + ':'
        + aws_house_models
    )

    os.environ['IGN_GAZEBO_RESOURCE_PATH'] = gazebo_resource_path
    os.environ['GZ_SIM_RESOURCE_PATH'] = gazebo_resource_path

    # sdformat_urdf may use SDF_PATH to resolve resources.
    if 'SDF_PATH' in os.environ:
        os.environ['SDF_PATH'] += ':' + gazebo_resource_path
    else:
        os.environ['SDF_PATH'] = gazebo_resource_path

    # ------------------------------------------------------------
    # Launch arguments
    # ------------------------------------------------------------

    gazebo_world = LaunchConfiguration('gazebo_world')

    gazebo_world_launch_arg = DeclareLaunchArgument(
        'gazebo_world',
        default_value=small_house_world,
        description='Gazebo world to launch'
    )

    use_sim_time = LaunchConfiguration('use_sim_time')

    use_sim_time_launch_arg = DeclareLaunchArgument(
        'use_sim_time',
        default_value='true',
        description='Use simulation time'
    )

    use_rviz = LaunchConfiguration('use_rviz')

    use_rviz_arg = DeclareLaunchArgument(
        'use_rviz',
        default_value='true',
        description='Launch RViz'
    )

    use_px4 = LaunchConfiguration('use_px4')

    use_px4_arg = DeclareLaunchArgument(
        'use_px4',
        default_value='false',
        description='Launch PX4'
    )

    use_sverk = LaunchConfiguration('use_sverk')

    use_sverk_arg = DeclareLaunchArgument(
        'use_sverk',
        default_value='false',
        description='Launch SVERK offboard control'
    )

    use_ros2_control = LaunchConfiguration('use_ros2_control')

    use_ros2_control_arg = DeclareLaunchArgument(
        'use_ros2_control',
        default_value='true',
        description='Include ros2_control configuration in URDF'
    )

    # ------------------------------------------------------------
    # Optional custom world through GZ_SIM_WORLD
    # ------------------------------------------------------------

    world_env = os.getenv('GZ_SIM_WORLD')

    if world_env:
        fly_world_path = (
            resources_package
            + '/worlds/'
            + world_env
            + '.sdf'
        )

        gz_version = subprocess.getoutput('gz sim --versions')
        match = re.search(r'^\d{1}', gz_version)

        if match:
            gz_version_major = match.group()
        else:
            gz_version_major = '6'

        launch_arguments = dict(
            gz_args='-r ' + fly_world_path + ' --verbose',
            gz_version=gz_version_major
        ).items()
    else:
        launch_arguments = {
        'gz_args': ['-r ', gazebo_world, ' --verbose'],
        }.items()

    # ------------------------------------------------------------
    # Gazebo Sim
    # ------------------------------------------------------------

    pkg_ros_gz_sim = get_package_share_directory(
        'ros_gz_sim'
    )

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                pkg_ros_gz_sim,
                'launch',
                'gz_sim.launch.py'
            )
        ),
        launch_arguments=launch_arguments,
    )

    # ------------------------------------------------------------
    # Robot State Publisher / RViz
    # ------------------------------------------------------------

    robot_state_publisher = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            PathJoinSubstitution([
                FindPackageShare(resources_package),
                'launch',
                'description.launch.py',
            ]),
        ]),
        launch_arguments=dict(
            use_sim_time=use_sim_time,
            use_ros2_control=use_ros2_control
        ).items(),
    )

    rviz = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            PathJoinSubstitution([
                FindPackageShare(resources_package),
                'launch',
                'display.launch.py',
            ]),
        ]),
        condition=IfCondition(use_rviz),
        launch_arguments=dict(
            use_sim_time=use_sim_time,
            use_ros2_control=use_ros2_control
        ).items(),
    )

    # ------------------------------------------------------------
    # Spawn OrbiRob
    # ------------------------------------------------------------

    spawn = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=[
            '-name', 'OrbiRob',

            # Initial position.
            '-x', '1.2',
            '-y', '3.4',
            '-z', '0.20',

            # Initial yaw.
            '-Y', '0.0',

            '-topic', '/robot_description',
        ],
        output='screen',
    )

    # ------------------------------------------------------------
    # ros2_control controllers
    #
    # These are started after the robot has been spawned and
    # gz_ros2_control has created /controller_manager.
    # ------------------------------------------------------------

    # joint_state_broadcaster_spawner = Node(
    #     package='controller_manager',
    #     executable='spawner',
    #     arguments=[
    #         'joint_state_broadcaster',
    #         '--controller-manager',
    #         '/controller_manager',
    #     ],
    #     condition=IfCondition(use_ros2_control),
    #     output='screen',
    # )

    # diff_drive_controller_spawner = Node(
    #     package='controller_manager',
    #     executable='spawner',
    #     arguments=[
    #         'diff_drive_controller',
    #         '--controller-manager',
    #         '/controller_manager',
    #     ],
    #     condition=IfCondition(use_ros2_control),
    #     output='screen',
    # )

    # Start controller spawners only after the robot has been spawned.
    #controller_spawners = RegisterEventHandler(
    #    OnProcessExit(
    #        target_action=spawn,
    #        on_exit=[
    #            joint_state_broadcaster_spawner,
    #            diff_drive_controller_spawner,
    #        ],
    #    )
    #)

    # ------------------------------------------------------------
    # ROS-Gazebo clock bridge
    # ------------------------------------------------------------

    gz_bridge_parameter = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        arguments=[
            '/clock@rosgraph_msgs/msg/Clock[ignition.msgs.Clock'
        ],
        output='screen',
        parameters=[
            {
                'use_sim_time': use_sim_time,
            }
        ],
    )

    # ------------------------------------------------------------
    # Camera bridge
    # ------------------------------------------------------------

    gz_bridge_camera = Node(
        package='ros_gz_image',
        executable='image_bridge',
        arguments=[],
        output='screen'
    )

    # ------------------------------------------------------------
    # SVERK offboard control
    # ------------------------------------------------------------

    offboard_control = Node(
        package='offboard_control',
        executable='offboard_control',
        name='offboard_control',
        condition=IfCondition(use_sverk),
        parameters=[
            {
                'simulator': True
            }
        ],
        output='screen'
    )

    # ------------------------------------------------------------
    # PX4
    # ------------------------------------------------------------

    px4_condition = PythonExpression([
        '"',
        use_px4,
        '" == "true" or "',
        use_sverk,
        '" == "true"'
    ])

    px4 = ExecuteProcess(
        cmd=['px4'],
        name='px4',
        output='screen',
        shell=True,
        condition=IfCondition(px4_condition),
        env={
            **os.environ,
            'PX4_GZ_STANDALONE': '1',
            'PX4_SYS_AUTOSTART': '104001',
            'PX4_GZ_MODEL_NAME': 'OrbiRob',
        }
    )

    # ------------------------------------------------------------
    # LaunchDescription
    # ------------------------------------------------------------

    return LaunchDescription([
        use_sim_time_launch_arg,
        use_rviz_arg,
        gazebo_world_launch_arg,
        use_px4_arg,
        use_sverk_arg,
        use_ros2_control_arg,
        robot_state_publisher,
        rviz,
        gazebo,
        spawn,

        #controller_spawners,

        gz_bridge_parameter,
        gz_bridge_camera,

        offboard_control,
        px4,
    ])
