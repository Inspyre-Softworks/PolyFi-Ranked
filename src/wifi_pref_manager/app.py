"""
Author:
    Inspyre Softworks

Project:
    PolyFi: Ranked

File:
    app.py

Description:
    Main entry point for running PolyFi: Ranked either in console mode or as a
    system tray application.

Functions:
    main:
        CLI entry point.

Constants:
    None.

Dependencies:
    argparse
    sys
    wifi_pref_manager.config
    wifi_pref_manager.logging_utils
    wifi_pref_manager.netsh_wifi
    wifi_pref_manager.paths
    wifi_pref_manager.service
    wifi_pref_manager.ui.tray

Example Usage:
    poetry run polyfi-ranked
    poetry run polyfi-ranked --tray
"""

from __future__ import annotations

import argparse
import sys

from wifi_pref_manager.config import ConfigError, ConfigLoader
from wifi_pref_manager.logging_utils import configure_logging
from wifi_pref_manager.netsh_wifi import NetshWiFiApi
from wifi_pref_manager.paths import AppPaths
from wifi_pref_manager.service import WiFiPreferenceService
from wifi_pref_manager.ui.tray import TrayApplication


class Application:
    """
    Application bootstrapper.

    Methods:
        run:
            Start the application in console or tray mode.
    """

    def __init__(self) -> None:
        self.paths = AppPaths()
        self.argument_parser = self.build_argument_parser()

    def build_argument_parser(self) -> argparse.ArgumentParser:
        """
        Build the application CLI parser.

        Returns:
            Configured ArgumentParser.
        """
        parser = argparse.ArgumentParser(description='PolyFi: Ranked for Windows.')
        parser.add_argument(
            '--config',
            default=None,
            help='Optional path to the TOML configuration file. Defaults to the platform app-data config path.',
        )
        parser.add_argument(
            '--tray',
            action='store_true',
            help='Run as a system tray application.',
        )
        parser.add_argument(
            '--print-paths',
            action='store_true',
            help='Print the default config and log paths, then exit.',
        )
        return parser

    def on_config_reloaded(self, config) -> object:
        """
        Reconfigure logging when the config changes.

        Parameters:
            config:
                Newly loaded application config.

        Returns:
            Refreshed logger instance.
        """
        return configure_logging(config.log_level, config.log_file)

    def run(self, argv: list[str] | None = None) -> int:
        """
        Run the application.

        Parameters:
            argv:
                Optional CLI argument list.

        Returns:
            Process exit code.
        """
        args = self.argument_parser.parse_args(argv)

        if args.print_paths:
            print(f'Config file: {self.paths.config_file}')
            print(f'Example config: {self.paths.example_config_file}')
            print(f'Log file: {self.paths.log_file}')
            return 0

        loader = ConfigLoader(config_path=args.config)
        config_path = loader.ensure_default_config()

        try:
            config = loader.load()
        except ConfigError as exc:
            print(f'Configuration error: {exc}', file=sys.stderr)
            print(f'Config path: {config_path}', file=sys.stderr)
            return 1

        logger = configure_logging(config.log_level, config.log_file)
        logger.info('Using config file: %s', config_path)

        wifi_api = NetshWiFiApi(logger=logger)
        service = WiFiPreferenceService(
            config=config,
            wifi_api=wifi_api,
            logger=logger,
            config_loader=loader,
            on_config_reloaded=self.on_config_reloaded,
        )

        if args.tray or config.start_minimized_to_tray:
            tray_app = TrayApplication(service=service, logger=logger)
            tray_app.run()
            return 0

        try:
            service.run_forever()
        except KeyboardInterrupt:
            logger.info('Keyboard interrupt received. Stopping service.')
            service.stop()

        return 0


def main() -> int:
    """
    CLI entry point.

    Returns:
        Process exit code.
    """
    return Application().run()


if __name__ == '__main__':
    raise SystemExit(main())
