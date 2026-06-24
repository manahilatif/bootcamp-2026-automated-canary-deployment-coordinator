import threading
import logging
import time

abort_flag = threading.Event()

def listen_for_abort():
    while True:
        user_input = input()
        if user_input.strip().upper() == "ABORT":
            logging.warning("ABORT received — stopping rollout...")
            abort_flag.set()
            break

def start_abort_listener():
    thread = threading.Thread(target=listen_for_abort, daemon=True)
    thread.start()
    return thread

def interruptible_sleep(seconds):
    logging.info(f"Sleeping for {seconds} seconds (type ABORT to cancel)...")
    for _ in range(seconds):
        if abort_flag.is_set():
            logging.warning("Sleep interrupted by ABORT")
            return True
        time.sleep(1)
    return False

def is_aborted():
    return abort_flag.is_set()