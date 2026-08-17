Import("env")

board_config = env.BoardConfig()
board_config.update("upload.disable_flushing", True)
board_config.update("upload.use_1200bps_touch", False)
board_config.update("upload.wait_for_upload_port", False)