"""
Copyright (c) 2025 Nobuo Tsukamoto
This software is released under the MIT License.
See the LICENSE file in the project root for more information.
"""

import argparse
import sys
from gui_controller import GUIController
from config_manager import ConfigManager, EmptyConfigError
from logger import Logger


def main():
    """
    Main function to run the application.
    """
    parser = argparse.ArgumentParser(
        description="Object Detection and Tracking Application"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="../config/default.yaml",
        help="Path to the configuration file.",
    )
    args = parser.parse_args()

    try:
        # Initialize components
        config_manager = ConfigManager(args.config)
        logger = Logger(config_manager.get_config("logging"))

        # Create and run the GUI
        app = GUIController(config_manager, logger)
        app.run()

    except FileNotFoundError:
        print(f"Error: Configuration file not found at {args.config}", file=sys.stderr)
        sys.exit(1)
    except EmptyConfigError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
